import asyncio
import json
from datetime import datetime
from time import perf_counter

#amazon import
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models.condition import Condition
from paapi5_python_sdk.models.get_items_request import GetItemsRequest
from paapi5_python_sdk.models.get_items_resource import GetItemsResource
from paapi5_python_sdk.models.partner_type import PartnerType
from paapi5_python_sdk.rest import ApiException

#telegram import
from telegram import Bot
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.constants import ParseMode

from dotenv import load_dotenv
import os

load_dotenv()  # Carica le variabili da .env

# Credenziali Amazon e Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
TAG = os.getenv("TAG")
ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
CHAT_ID = os.getenv("CHAT_ID")
COUNTRY = 'IT'
ENDPOINT = 'webservices.amazon.it'
REGION = 'eu-west-1'
SERVICE = 'ProductAdvertisingAPI'
PARTNER_TYPE = 'Associates'

bot = Bot(token=BOT_TOKEN)

default_api = DefaultApi(
    access_key=ACCESS_KEY,
    secret_key=SECRET_KEY,
    host=ENDPOINT,
    region=REGION
)

async def check_products():
    while True:

        try:
            with open("packages/db.json", "r") as f:
                products = json.load(f)

            asins = [item["asin"] for item in products]
            get_items_request = GetItemsRequest(
                partner_tag=TAG,
                partner_type=PartnerType.ASSOCIATES,
                condition=Condition.NEW,
                marketplace="www.amazon.it",
                merchant="Amazon",
                item_ids=asins,
                resources=[
                    GetItemsResource.OFFERSV2_LISTINGS_AVAILABILITY,
                    GetItemsResource.OFFERSV2_LISTINGS_MERCHANTINFO,
                    GetItemsResource.OFFERSV2_LISTINGS_PRICE,
                    GetItemsResource.ITEMINFO_TITLE,
                    GetItemsResource.IMAGES_PRIMARY_LARGE,
                    GetItemsResource.OFFERS_LISTINGS_AVAILABILITY_MESSAGE
                ]
            )

            #check sulla durata della chiamata a paapi
            start_time = perf_counter()

            response = default_api.get_items(get_items_request)

            end_time = perf_counter()
            elapsed = end_time - start_time


            changed = False
            for i, item in enumerate(response.items_result.items):
                
                asin = item.asin
                print(f"\n\nValuto \033[33m {asin}\033[0m")

                print(f"\nitem.offers: {item.offers}")

                # Accesso a offers_v2
                try:
                    offers_v2 = item.offers_v2
                    listing = None

                    # Seleziona solo le offerte vendute da Amazon
                    if offers_v2 and offers_v2.listings:
                        for l in offers_v2.listings:
                            merchant_info = l.get("MerchantInfo", {})
                            merchant_name = merchant_info.get("Name", "")
                            if merchant_name.strip().lower() == "amazon":
                                listing = l
                                break

                    print("\nOffersV2:\n", offers_v2)
                    print("\nListing selezionato (venduto da Amazon):\n", listing)

                    available = False

                    if listing and "Availability" in listing:
                        availability = listing["Availability"]
                        availability_type = availability.get("Type", "").lower()

                        # Lista dei tipi considerati "disponibili"
                        acceptable_types = ["in_stock", "in_stock_scarce", "available_date", "leadtime"]
                        available = availability_type in acceptable_types

                        print("\n✅ Availability Type:", availability_type)
                    else:
                        print("\n❌ Nessuna offerta valida venduta da Amazon o manca Availability")

                except Exception as e:
                    print(f"\n❌ Errore accesso availability: {e}\n")
                    available = False

                if available and not products[i]["last_available"]:
                    title = item.item_info.title.display_value if item.item_info and item.item_info.title else "Sconosciuto"
                    price = item.offers_v2.listings[0]["Price"]["Money"]["DisplayAmount"] if item.offers_v2 else "Non disponibile"
                    image = item.images.primary.large.url if item.images and item.images.primary and item.images.primary.large else ""
                    offering_id = item.offers.listings[0].id if item.offers else ""
                    print(f"\noffering id: {offering_id}\n")

                    fast_checkout_link = (
                        f"https://www.amazon.it/gp/checkoutportal/enter-checkout.html/ref=dp_mw_buy_now?"
                        f"asin={asin}&offeringID={offering_id}&buyNow=1&quantity=1&tag={TAG}"
                    )

                    msg = (
                        f"<a href='{image}'> </a>"  # link all'immagine per forzare l'anteprima
                        f"<b>{title}</b>\n\n"
                        f"<b>Prezzo: {price}</b>\n\n"
                        f"🔗 <a href='{item.detail_page_url}'>Pagina prodotto</a>\n"
                        f"⚡ <a href='{fast_checkout_link}'>Acquisto Lampo</a>\n\n"
                        f"Inviate qui i vostri successi @pokedetective\n"
                    )

                    keyboard = [
                        [InlineKeyboardButton("⚡ Fast Checkout", url=fast_checkout_link)]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await bot.send_message(
                        chat_id=CHAT_ID,
                        text=msg,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=False,  # False per mostrare l'anteprima
                        reply_markup=reply_markup
                    )

                    products[i]["last_available"] = True
                    changed = True
                    print(f"✅ Disponibile ora il prodotto: {asin}\n\n")

                elif not available and products[i]["last_available"]:
                    products[i]["last_available"] = False
                    changed = True
                    print(f"❌ Non più disponibile il prodotto: {asin}\n\n")

            # Stampa durata chiamata a paapi
            print(f"\n⏱️ Tempo risposta PAAPI: \033[35m {elapsed:.2f} \033[0m secondi\n")

            if changed:
                with open("packages/db.json", "w") as f:
                    json.dump(products, f, indent=4)

        except ApiException as e:
            print("❌ Errore API:", e)
        except Exception as e:
            print("❌ Errore generale:", e)

        await asyncio.sleep(5)  # controlla ogni 5 secondi

# Reset dei prodotti ancora disponibili
async def auto_reset():
    while True:
        await asyncio.sleep(20 * 60)  # 20 minuti
        try:
            with open("packages/db.json", "r") as f:
                data = json.load(f)

            updated = False
            for item in data:
                if item.get("last_available"):
                    item["last_available"] = False
                    updated = True

            if updated:
                with open("packages/db.json", "w") as f:
                    json.dump(data, f, indent=2)
                print("\n✅ Database reset ogni 20 minuti.\n")
            else:
                print("\nℹ️ Nessun prodotto da resettare.\n")

        except Exception as e:
            print(f"Errore durante il reset automatico: {e}")
