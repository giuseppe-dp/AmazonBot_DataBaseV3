import asyncio
import sqlite3
import urllib3
from datetime import datetime, timezone
from time import perf_counter

from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models.condition import Condition
from paapi5_python_sdk.models.get_items_request import GetItemsRequest
from paapi5_python_sdk.models.get_items_resource import GetItemsResource
from paapi5_python_sdk.models.partner_type import PartnerType
from paapi5_python_sdk.rest import ApiException

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import NetworkError, TimedOut
from requests.exceptions import ConnectionError, ReadTimeout, RequestException
import httpx
import os
from dotenv import load_dotenv

from database import (
    get_static_data, get_dynamic_data, upsert_scraping, upsert_dynamic_status, connect_db,
    get_active_asins, get_offering_id, was_previously_available
)

from scraping import scraping_data

from logger_config import paapi_logger, bot_logger

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TAG = os.getenv("TAG")
ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
CHAT_ID = os.getenv("CHAT_ID")
ENDPOINT = "webservices.amazon.it"
REGION = "eu-west-1"
DB_PATH = "products.db"

bot = Bot(token=BOT_TOKEN)

default_api = DefaultApi(
    access_key=ACCESS_KEY,
    secret_key=SECRET_KEY,
    host=ENDPOINT,
    region=REGION
)


def chunk_list(lst, n):
    # Divide una lista in sottoliste da massimo n elementi.
    for i in range(0, len(lst), n):
        yield lst[i:i+n]  # return parziale per ogni batch


# - CONTATORE RICHIESTE PAAPI -
paapi_request_count = 0
paapi_request_window_start = datetime.now()

async def safe_paapi_request(batch, tag, merchant="Amazon", marketplace="www.amazon.it"):

    """
    Esegue una chiamata PAAPI per un batch di ASIN.
    Gestisce rate limit, errori e logging.
    Restituisce la risposta (oppure None in caso di errore bloccante).
    --> return response
    """

    global paapi_request_count, paapi_request_window_start

    get_items_request = GetItemsRequest(
        partner_tag=tag,
        partner_type=PartnerType.ASSOCIATES,
        condition=Condition.NEW,
        marketplace=marketplace,
        merchant=merchant,
        item_ids=batch,
        resources=[
            GetItemsResource.OFFERSV2_LISTINGS_AVAILABILITY,
            GetItemsResource.OFFERSV2_LISTINGS_MERCHANTINFO
        ]
    )

    try:
        response = default_api.get_items(get_items_request)

        paapi_request_count += 1
        elapsed_window = (datetime.now() - paapi_request_window_start).total_seconds()

        # Reset ogni ora
        if elapsed_window > 3600:
            msg = f"🕒 Nell'ultima ora sono state fatte {paapi_request_count} chiamate PAAPI."
            paapi_logger.info(msg)
            paapi_request_count = 1
            paapi_request_window_start = datetime.now()

        return response

    except ApiException as e:
        error_message = str(e)

        if "TooManyRequests" in error_message or "429" in error_message:
            msg = (
                f"🚫 Errore Too Many Requests su batch {batch}. "
                f"Messa in pausa per 1 ora"
                f"--> Sono state fatte {paapi_request_count} chiamate PAAPI prima dell'errore."
            )
            paapi_logger.error(msg)
            await asyncio.sleep(3600)
            msg = "🔁 Restart dopo Errore Too Many Requests..."
            paapi_logger.info(msg)
            paapi_request_count = 0
            paapi_request_window_start = datetime.now()
            return None  # salta batch

        else:
            msg = f"🚫 Errore API su batch {batch}: {error_message}"
            paapi_logger.error(msg)
            return None
        
    # Errori di rete / DNS / Timeout
    except (urllib3.exceptions.NewConnectionError,
            urllib3.exceptions.NameResolutionError,
            urllib3.exceptions.MaxRetryError,
            httpx.ReadTimeout, 
            httpx.ConnectError,
            ConnectionError,
            ReadTimeout) as e:
        paapi_logger.warning(f"🌐 Errore di connessione PAAPI: {type(e).__name__} — {e}")
        paapi_logger.info("🔁 Attendo 1 minuto prima di riprovare...")
        await asyncio.sleep(60)
        return None
    
    except Exception as e:
        msg = f"❌ Errore generale durante PAAPI batch {batch}: {e}"
        paapi_logger.error(msg)
        return None
    

async def send_message(asin):

    """
    Prende i dati di asin nel database e invia il messaggio su telegram.
    """
    
    # PRENDE I DATI STATICI DAL DB
    title = get_static_data(asin)
    image, price, detail_page_url, offering_id = get_dynamic_data(asin)

    fast_checkout_link_single = (
        f"https://www.amazon.it/checkout/entry/buynow?"
        f"asin={asin}&offeringID={offering_id}&quantity=1&tag={TAG}"
    )

    fast_checkout_link_double = (
        f"https://www.amazon.it/checkout/entry/buynow?"
        f"asin={asin}&offeringID={offering_id}&quantity=2&tag={TAG}"
    )

    msg = (
        f"<a href='{image}'> </a>"  # link all'immagine per forzare l'anteprima
        f"<b>🇮🇹 {title}</b>\n\n"
        f"<b>💵 Prezzo: {price}</b>\n\n"

        f"🔗 <a href='{detail_page_url}'>Pagina prodotto</a>\n"
        f"⚡ <a href='{fast_checkout_link_single}'>Acquisto Lampo</a>\n\n"

        f"Inviate qui i vostri successi @pokedetective  -  #affiliate\n"
    )

    keyboard = [
        [InlineKeyboardButton("⚡ Fast Checkout", url=fast_checkout_link_single)],
        [InlineKeyboardButton("💰 Fast Checkout x2", url=fast_checkout_link_double)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=msg,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
            reply_markup=reply_markup
        )
    except (httpx.ConnectError, httpx.ReadTimeout, NetworkError, TimedOut) as e:
        bot_logger.warning(f"⚠️ Errore di rete durante l'invio del messaggio Telegram, pausa di 60 secondi: {e}")
        await asyncio.sleep(60)
    except Exception as e:
        bot_logger.exception(f"❌ Errore imprevisto nell'invio messaggio Telegram: {e}")


async def merchant_check(item):

    """ 
    Prende le offerte per l'asin e controlla se tra queste c'è una fatta da amazon.
    Restituisce poi due variabili bool che rappresentano se prima della ricerca era disponibile e se ora lo è.
    --> return previously_available, available
    """

    asin = item.asin
    available = False
    availability_type = ""
    merchant_name = ""

    print(f"\nValuto \033[33m {asin}\033[0m")

    # Seleziona solo le offerte vendute da Amazon
    listing = None
    if item.offers_v2 and item.offers_v2.listings:
        for l in item.offers_v2.listings:
            merchant_info = l.get("MerchantInfo", {})
            merchant_name = merchant_info.get("Name", "")
            if merchant_name.strip().lower() == "amazon":
                listing = l
                break

    print("\nOffersV2:\n", item.offers_v2)
    print("\nListing selezionato (venduto da Amazon):\n", listing)


    if listing and "Availability" in listing:
        availability = listing["Availability"]
        availability_type = availability.get("Type", "").lower()
        # Lista dei tipi considerati "disponibili"
        acceptable_types = ["in_stock", "in_stock_scarce", "available_date", "leadtime"]
        available = availability_type in acceptable_types

        print("\n✅ Availability Type:", availability_type)
    else:
        print("\n❌ Nessuna offerta valida venduta da Amazon o manca Availability.")

    previously_available = was_previously_available(asin)
    upsert_dynamic_status(asin, available, availability_type, merchant_name)

    return previously_available, available


async def check_products():

    """ 
    Prende degli asin dal database e li divide in batch.
    Per ogni batch fa una richiesta Paapi e con il risultato controlla per ogni asin nel batch se è disponibile e venduto da amazon.
    Se lo è invia un messaggio su Telegram per quel asin.... continua cosi per ogni batch.
    """

    # Variabili per il boost
    normal_interval = 5    # quando nessun prodotto trovato
    boosted_interval = 3   # quando trova disponibilità
    boost_duration = 5     # minuti
    boost_active = False
    boost_start_time = None

    while True:
        try:
            asins = get_active_asins()
            if not asins:
                msg = "\n❌ Nessun ASIN nel database.\n"
                paapi_logger.error(msg)
                await asyncio.sleep(1800)
                continue

            # Divisione in batch
            for batch in chunk_list(asins, 10):

                found_available = False  # flag per capire se attivare il boost

                start_time = perf_counter()
                response = await safe_paapi_request(batch, TAG) # richiesta paapi
                end_time = perf_counter()

                if not response:
                    continue  # passa al batch successivo se c’è stato errore


                # Processo ogni item nel batch
                for item in response.items_result.items:
                    asin = item.asin
                    
                    previously_available, available = await merchant_check(item) # controlla se c'è un offerta fatta da amazon per l'asin

                    if available and not previously_available:
                        found_available = True  # attiva modalità boost

                        offering_id = get_offering_id(asin)

                        if offering_id in ("None", ""):
                            data = await scraping_data(asin)
                            upsert_scraping(asin, data["image_url"], data["price"], data["offering_id"],)
                            if data["offering_id"] in ("None", ""):
                                upsert_dynamic_status(asin, False, None, None)

                        await send_message(asin) # invio il messaggio su telegram

                        msg = f"🤖​ Disponibile ora il prodotto: {asin}"
                        paapi_logger.info(msg)

                    elif not available and previously_available:

                        msg = f"❌ {asin} non più disponibile."
                        paapi_logger.info(msg)

                print(f"\n⏱️ Tempo risposta PAAPI: \033[35m {end_time - start_time:.2f} \033[0m secondi.")
                print(f"\n⮞ Batch \033[33m {batch} \033[0m completato.\n")

                # - Gestione dinamica velocità richieste -
                if found_available:
                    boost_active = True
                    boost_start_time = datetime.now()
                    paapi_logger.info(f"⚡ Modalità veloce attivata per {boost_duration} minuti.")

                elif boost_active:
                    elapsed = (datetime.now() - boost_start_time).total_seconds()
                    print(f"\nBoost attivo per {(boost_duration*60)-elapsed} secondi.")

                    if elapsed > (boost_duration*60):
                        boost_active = False
                        paapi_logger.info("🐢 Ritorno alla modalità normale.")

                interval = boosted_interval if boost_active else normal_interval
                print(f"\n⏱️ Attesa di {interval} secondi prima del prossimo ciclo...\n")
                await asyncio.sleep(interval)

            print("\n✔️ Batch completati.\n\n")

        except Exception as e:
            print("\n❌ check_products:", e)


reset_time = 10 * 60  # ogni 10 minuti
async def auto_reset():

    """
    Fa un reset della disponibilità dei prodotti nel database, ogni reset_time minuti.
    """

    while True:
        await asyncio.sleep(reset_time)
        try:
            now = datetime.now(timezone.utc).isoformat()
            with connect_db() as conn:
                cur = conn.cursor()

                # Verifica e reset dei prodotti disponibili
                cur.execute("SELECT asin FROM dynamic_status WHERE available = 1")
                results = cur.fetchall()

                if results:
                    asins = [row[0] for row in results]
                    cur.executemany("""
                        UPDATE dynamic_status
                        SET available = 0,
                            last_checked = ?
                        WHERE asin = ?
                    """, [(now, asin) for asin in asins])
                    conn.commit()
                    paapi_logger.info(f"✅ Reset di {len(asins)} prodotti.")
                else:
                    print("\nℹ️ Nessun prodotto da resettare.\n")

        except Exception as e:
            print(f"\n❌ Errore durante il reset automatico: {e}\n")