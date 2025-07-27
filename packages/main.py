import logging
import time

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

from watcher import check_products  # importa la funzione di watcher

import asyncio
import requests
import hashlib
import hmac
import base64
from urllib.parse import quote, urlencode
from datetime import datetime, timezone


#amazon import
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models.condition import Condition
from paapi5_python_sdk.models.get_items_request import GetItemsRequest
from paapi5_python_sdk.models.get_items_resource import GetItemsResource
from paapi5_python_sdk.models.partner_type import PartnerType
from paapi5_python_sdk.rest import ApiException

# Stati conversazione
ASIN = range(1)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

from dotenv import load_dotenv
import os

load_dotenv()  # Carica le variabili da .env

# Credenziali Amazon e Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
TAG = os.getenv("TAG")
ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")  # chiave privata
COUNTRY = 'IT'
ENDPOINT = 'webservices.amazon.it'
REGION = 'eu-west-1'
SERVICE = 'ProductAdvertisingAPI'
PARTNER_TYPE = 'Associates'

# Funzione per creare una richiesta firmata alla PA-API v5
def sign_request(params, secret_key):
    sorted_params = dict(sorted(params.items()))
    query_string = urlencode(sorted_params, quote_via=quote)
    method = 'GET'
    uri = '/paapi5/getitems'
    host = ENDPOINT
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    datestamp = timestamp[:8]

    headers = {
        'host': host,
        'x-amz-date': timestamp
    }

    canonical_headers = ''.join(f'{k}:{v}\n' for k, v in headers.items())
    signed_headers = ';'.join(headers.keys())
    payload_hash = hashlib.sha256(''.encode('utf-8')).hexdigest()

    canonical_request = f"{method}\n{uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    credential_scope = f"{datestamp}/{REGION}/{SERVICE}/aws4_request"
    string_to_sign = f"AWS4-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

    def sign(key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    kDate = sign(('AWS4' + secret_key).encode('utf-8'), datestamp)
    kRegion = sign(kDate, REGION)
    kService = sign(kRegion, SERVICE)
    kSigning = sign(kService, 'aws4_request')
    signature = hmac.new(kSigning, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    authorization_header = (
        f"AWS4-HMAC-SHA256 Credential={ACCESS_KEY}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers['Authorization'] = authorization_header
    headers['content-encoding'] = 'amz-1.0'
    headers['content-type'] = 'application/json; charset=utf-8'
    return headers

# COMANDI BOT

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *Comandi disponibili:*\n\n"
        "/start - Avvia il bot e crea un nuovo link affiliato\n"
        "/help - Mostra questo messaggio di aiuto\n"
        "/info - Mostra il tuo tag affiliato corrente\n"
        "/cancel - Annulla l’operazione in corso\n\n"
        "Con /start puoi inviare un ASIN (codice prodotto Amazon) per ricevere il link affiliato con nome e prezzo."
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

# /info
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tag = TAG
    if tag:
        await update.message.reply_text(f"🔖 Il tuo tag affiliato corrente è: `{tag}`", parse_mode="HTML")
    else:
        await update.message.reply_text("ℹ️ Non hai ancora impostato un tag affiliato.")

## Conversazione guidata ##
# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tag = TAG

    context.user_data['tag'] = tag
    await update.message.reply_text("👋 Inviami l'ASIN del prodotto Amazon.")
    return ASIN

# Ricezione ASIN
async def receive_asin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asin = update.message.text.strip().upper()
    tag = context.user_data.get('tag', 'TAG-MANCANTE')

    if len(asin) != 10:
        await update.message.reply_text("❌ L'ASIN deve essere di 10 caratteri.")
        return ASIN

    # Rispetta il rate limit
    time.sleep(1.1)

    default_api = DefaultApi(
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        host=ENDPOINT,
        region=REGION
    )

    try:
        get_items_request = GetItemsRequest(
            partner_tag=tag,
            partner_type=PartnerType.ASSOCIATES,
            marketplace="www.amazon.it",
            merchant="Amazon",
            condition=Condition.NEW,
            item_ids=[asin],
            resources=[
                GetItemsResource.ITEMINFO_TITLE,
                GetItemsResource.OFFERSV2_LISTINGS_PRICE,
                GetItemsResource.IMAGES_PRIMARY_LARGE,
            ]
        )

        response = default_api.get_items(get_items_request)

        if response.items_result and response.items_result.items:
            item = response.items_result.items[0]

            title = item.item_info.title.display_value if item.item_info and item.item_info.title else "Sconosciuto"
            price = item.offers_v2.listings[0]["Price"]["Money"]["DisplayAmount"] if item.offers_v2 else "Non disponibile"
            link = item.detail_page_url
            image = item.images.primary.large.url

            msg =  (
                f"<b>{title}</b>\n\n"
                f"<b>Prezzo: {price}</b>\n\n"
                f"🔗 <a href='{link}'>Pagina prodotto</a>\n"
            )

            # Pulsanti
            keyboard = [
                [InlineKeyboardButton("🇮🇹 ACQUISTA", url=link)],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Invia immagine + caption
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=image,
                caption=msg,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        else:
            await update.message.reply_text("❌ Prodotto non trovato o tag affiliato errato.")

    except ApiException as e:
        await update.message.reply_text(
            f"❌ Errore PA-API!\nCodice: {e.status}\nMessaggio: {e.body}"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Errore imprevisto: {e}")

    return ASIN

# /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Conversazione annullata.")
    return ConversationHandler.END

import nest_asyncio
nest_asyncio.apply() # Per evitare il problema dell’event loop già in esecuzione

# Avvio parallelo di bot + watcher
async def main():
    asyncio.create_task(check_products())  # parte il watcher
    await app.run_polling()

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_asin)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("info", info_command))

    asyncio.get_event_loop().run_until_complete(main())
    