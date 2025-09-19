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
    get_asins_from_db, get_static_data, upsert_static_data, upsert_dynamic_status, connect_db

)

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


async def check_products():
    while True:
        try:
            asins = get_asins_from_db()
            if not asins:
                print("\n❌ Nessun ASIN nel database.\n")
                await asyncio.sleep(20)
                continue

            # CHIAMATA RIDOTTA: solo dati dinamici
            get_items_request = GetItemsRequest(
                partner_tag=TAG,
                partner_type=PartnerType.ASSOCIATES,
                condition=Condition.NEW,
                marketplace="www.amazon.it",
                merchant="Amazon",
                item_ids=asins,
                resources=[
                    GetItemsResource.OFFERSV2_LISTINGS_AVAILABILITY,
                    GetItemsResource.OFFERSV2_LISTINGS_MERCHANTINFO
                ]
            )

            start_time = perf_counter()
            response = default_api.get_items(get_items_request)
            end_time = perf_counter()

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
                    # PRENDE I DATI STATICI DAL DB
                    title, image, price, detail_page_url, offering_id = get_static_data(asin)

                    fast_checkout_link_single = (
                        f"https://www.amazon.it/gp/checkoutportal/enter-checkout.html/ref=dp_mw_buy_now?"
                        f"asin={asin}&offeringID={offering_id}&buyNow=1&quantity=1&tag={TAG}"
                    )

                    fast_checkout_link_double = (
                        f"https://www.amazon.it/gp/checkoutportal/enter-checkout.html/ref=dp_mw_buy_now?"
                        f"asin={asin}&offeringID={offering_id}&buyNow=1&quantity=2&tag={TAG}"
                    )

                    msg = (
                        f"<a href='{image}'> </a>"  # link all'immagine per forzare l'anteprima
                        f"<b>{title}</b>\n\n"
                        f"<b>Prezzo: {price}</b>\n\n"
                        f"🔗 <a href='{detail_page_url}'>Pagina prodotto</a>\n"
                        f"⚡ <a href='{fast_checkout_link_single}'>Acquisto Lampo</a>\n"
                        f"💰 <a href='{fast_checkout_link_double}'>Acquisto Lampo x2</a>\n\n"
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
                    print(f"✅ Disponibile ora il prodotto: {asin}\n\n")
                elif not available and previously_available:
                    print(f"\n❌ {asin} non più disponibile\n")

            print(f"\n⏱️ Tempo risposta PAAPI: \033[35m {end_time - start_time:.2f} \033[0m secondi\n")

        except ApiException as e:
            print("\n❌ Errore API:", e)
        except Exception as e:
            print("\n❌ Errore generale:", e)

        await asyncio.sleep(5)


async def auto_reset():
    while True:
        await asyncio.sleep(1 * 60)  # ogni 20 minuti
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