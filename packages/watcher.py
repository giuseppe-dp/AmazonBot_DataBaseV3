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

# Inserisci qui i tuoi dati
BOT_TOKEN = os.getenv("BOT_TOKEN")
TAG = os.getenv("TAG")
ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)

async def check_products():
    while True:
        try:
            with open("packages/db.json", "r") as f:
                products = json.load(f)

            api_instance = DefaultApi()
            asins = [item["asin"] for item in products]
            request = GetItemsRequest(
                partner_tag=TAG,
                partner_type=PartnerType.ASSOCIATES,
                condition=Condition.NEW,
                marketplace="www.amazon.it",
                item_ids=asins,
                resources=[
                    GetItemsResource.OFFERS_LISTINGS_AVAILABILITY_MESSAGE,
                    GetItemsResource.ITEMINFO_TITLE,
                    GetItemsResource.OFFERSV2_LISTINGS_PRICE,
                    GetItemsResource.IMAGES_PRIMARY_LARGE,
                ]
            )

            response = api_instance.get_items(
                request=request,
                access_key=ACCESS_KEY,
                secret_key=SECRET_KEY,
                region='eu-west-1'
            )

            changed = False
            for i, item in enumerate(response.items_result.items):
                asin = item.asin
                available = "Disponibile" in (item.offers.listings[0].availability.message.text if item.offers and item.offers.listings else "")

                if available and not products[i]["last_available"]:
                    title = item.item_info.title.display_value if item.item_info and item.item_info.title else "Sconosciuto"
                    price = item.offers_v2.listings[0]["Price"]["Money"]["DisplayAmount"] if item.offers_v2 else "Non disponibile"
                    link = item.detail_page_url
                    image = item.images.primary.large.url

                    msg =  (
                        f"✅ *Disponibile ora!*\n\n"
                        f"<b>{title}</b>\n\n"
                        f"<b>Prezzo: {price}</b>\n\n"
                        f"🔗 <a href='{link}'>Pagina prodotto</a>\n"
                        f"⚡ <a href='{link}'>Acquisto Lampo</a> - <b>#affiliate</b>\n\n"
                    )

                    # 🔗 Costruzione del link Fast Checkout
                    fast_checkout_link = f"https://www.amazon.it/gp/aws/cart/add.html?ASIN1={asin}&Quantity1=1&tag={TAG}"

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

        await asyncio.sleep(300)  # controlla ogni 5 minuti
