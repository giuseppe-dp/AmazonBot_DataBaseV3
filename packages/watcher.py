import asyncio
import json
from datetime import datetime

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
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
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

async def check_products():
    while True:
        
        default_api = DefaultApi(
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        host=ENDPOINT,
        region=REGION
        )

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
                    GetItemsResource.OFFERS_LISTINGS_AVAILABILITY_MESSAGE,
                    GetItemsResource.ITEMINFO_TITLE,
                    GetItemsResource.OFFERSV2_LISTINGS_PRICE,
                    GetItemsResource.IMAGES_PRIMARY_LARGE,
                ]
            )

            response = default_api.get_items(get_items_request)

            changed = False
            for i, item in enumerate(response.items_result.items):
                asin = item.asin
                availability_msg = (
                    item.offers.listings[0].availability.message if item.offers and item.offers.listings else ""
                ).lower()

                available = any(keyword in availability_msg for keyword in ["disponibile", "disponibilità", "in stock"])
                print(f"{asin} è disponibile? {available} \n")

                if available and not products[i]["last_available"]:

                    title = item.item_info.title.display_value if item.item_info and item.item_info.title else "Sconosciuto"
                    price = item.offers_v2.listings[0]["Price"]["Money"]["DisplayAmount"] if item.offers_v2 else "Non disponibile"
                    link = item.detail_page_url
                    image = item.images.primary.large.url
                    offering_id = item.offers.listings[0].id

                    # 🔗 Costruzione del link Fast Checkout
                    fast_checkout_link = f"https://www.amazon.it/gp/checkoutportal/enter-checkout.html/ref=dp_mw_buy_now?asin={asin}&offeringID={offering_id}&buyNow=1&quantity=1&tag={TAG}"

                    msg =  (
                        f"✅ *Disponibile ora!*\n\n"
                        f"<b>{title}</b>\n\n"
                        f"<b>Prezzo: {price}</b>\n\n"
                        f"🔗 <a href='{link}'>Pagina prodotto</a>\n"
                        f"⚡ <a href='{fast_checkout_link}'>Acquisto Lampo</a> - <b>#affiliate</b>\n\n"
                    )

                    # Pulsanti
                    keyboard = [
                        [InlineKeyboardButton("🇮🇹 ACQUISTA", url=link)],
                        [InlineKeyboardButton("⚡ Fast Checkout", url=fast_checkout_link)],
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    # Invia immagine + caption
                    await bot.send_photo(
                        chat_id=CHAT_ID,
                        photo=image,
                        caption=msg,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )

                    products[i]["last_available"] = True
                    changed = True
                    print(f"Disponibile ora il prodotto: {asin}\n\n")
                elif not available and products[i]["last_available"]:
                    products[i]["last_available"] = False
                    changed = True
                    print(f"Non più disponibile il prodotto: {asin}\n\n")

            if changed:
                with open("packages/db.json", "w") as f:
                    json.dump(products, f, indent=4)

        except ApiException as e:
            print("Errore API:", e)
        except Exception as e:
            print("Errore generale:", e)

        await asyncio.sleep(15)  # controlla ogni 15 secondi

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
