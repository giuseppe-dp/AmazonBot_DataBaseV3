import asyncio
import sqlite3
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
import os
from dotenv import load_dotenv

from database import (
    get_static_data, get_dynamic_data, upsert_scraping, upsert_dynamic_status, connect_db, get_active_asins, get_offering_id

)

from scraping import scraping_data

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


def was_previously_available(asin):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT available FROM dynamic_status WHERE asin = ?", (asin,))
    result = cursor.fetchone()
    conn.close()
    return bool(result and result[0] == 1)


def chunk_list(lst, n):
    # Divide una lista in sottoliste da massimo n elementi.
    for i in range(0, len(lst), n):
        yield lst[i:i+n]  # return parziale per ogni batch


# === CONTATORE RICHIESTE PAAPI ===
paapi_request_count = 0
paapi_request_window_start = datetime.now()
PAAPI_LIMIT_PER_HOUR = 3600
PAAPI_LIMIT_PER_DAY = 8640   # da usare se voglio impostare qualche limite di richieste
LOG_FILE = "paapi_log.txt"


def write_log(message: str):
    # Scrive una riga nel file di log con timestamp.
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {message}\n")


async def check_products():
    global paapi_request_count, paapi_request_window_start

    while True:
        try:
            asins = get_active_asins()
            if not asins:
                print("\n❌ Nessun ASIN nel database.\n")
                await asyncio.sleep(60)
                continue

            # Divisione in batch
            for batch in chunk_list(asins, 9):

                get_items_request = GetItemsRequest(
                    partner_tag=TAG,
                    partner_type=PartnerType.ASSOCIATES,
                    condition=Condition.NEW,
                    marketplace="www.amazon.it",
                    merchant="Amazon",
                    item_ids=batch,
                    resources=[
                        GetItemsResource.OFFERSV2_LISTINGS_AVAILABILITY,
                        GetItemsResource.OFFERSV2_LISTINGS_MERCHANTINFO
                    ]
                )

                try:
                    start_time = perf_counter()
                    response = default_api.get_items(get_items_request)
                    end_time = perf_counter()

                    # Count richieste
                    paapi_request_count += 1
                    elapsed_window = (datetime.now() - paapi_request_window_start).total_seconds()

                    # Reset automatico ogni ora
                    if elapsed_window > 3600:
                        msg = f"Nell'ultima ora sono state fatte {paapi_request_count} chiamate PAAPI."
                        print(f"\n🕒 {msg}\n")
                        write_log(msg)

                        # reset per l’ora successiva
                        paapi_request_count = 1
                        paapi_request_window_start = datetime.now()

                    # Avviso ogni tot chiamate
                    if paapi_request_count % 1000 == 0:
                        print(f"\n⚠️ Hai già fatto {paapi_request_count} chiamate PAAPI in questa sessione.\n")

                except ApiException as e:
                    error_message = str(e)

                    # Rileva errore "TooManyRequests" o simile
                    if "TooManyRequests" in error_message or "429" in error_message:
                        msg = (
                            f"🚫 Errore Too Many Requests su batch {batch}. "
                            f"Messa in pausa per 1 ora\n"
                            f"Sono state fatte {paapi_request_count} chiamate PAAPI prima dell'errore.\n"
                        )
                        print(msg)
                        write_log(msg)

                        # Pausa forzata di 1 ora
                        await asyncio.sleep(3600)

                        paapi_request_count = 0
                        paapi_request_window_start = datetime.now()

                        continue  # passa al batch successivo dopo la pausa
                    else:
                            # Altri errori API
                            msg = f"🚫 Errore API su batch {batch}: {error_message}"
                            print(msg)
                            write_log(msg)
                            continue  # passa comunque al prossimo batch


                # Processo ogni item nel batch
                for item in response.items_result.items:
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
                        print("\n❌ Nessuna offerta valida venduta da Amazon o manca Availability")

                    previously_available = was_previously_available(asin)
                    upsert_dynamic_status(asin, available, availability_type, merchant_name)


                    if available and not previously_available:
                        offering_id = get_offering_id(asin)

                        if offering_id in ("None", ""):
                            data = await scraping_data(asin)
                            upsert_scraping(asin, data["image_url"], data["price"], data["offering_id"],)

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
                            f"<b>🇮🇹{title}</b>\n\n"
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

                        await bot.send_message(
                            chat_id=CHAT_ID,
                            text=msg,
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=False, # False per mostrare l'anteprima
                            reply_markup=reply_markup
                        )
                        print(f"🤖​ Disponibile ora il prodotto: {asin}\n\n")
                    elif not available and previously_available:
                        print(f"\n❌ {asin} non più disponibile\n")

                    
                print(f"\n⏱️ Tempo risposta PAAPI: \033[35m {end_time - start_time:.2f} \033[0m secondi")
                print(f"\n⮞ Batch \033[33m {batch} \033[0m completato.\n")

                await asyncio.sleep(3)  # tempo prima del prossimo batch

            print("\n✔️ Batch completati.\n\n")
            #await asyncio.sleep(5)  # tempo prima del prossimo ciclo

        except ApiException as e:
            print("\n❌ Errore API:", e)
        except Exception as e:
            print("\n❌ Errore generale:", e)


async def auto_reset():
    while True:
        await asyncio.sleep(20 * 60)  # ogni 20 minuti
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
                    print(f"\n✅ Reset {len(asins)} prodotti disponibili ogni 20 minuti.\n")
                else:
                    print("\nℹ️ Nessun prodotto da resettare.\n")

        except Exception as e:
            print(f"\n❌ Errore durante il reset automatico: {e}\n")