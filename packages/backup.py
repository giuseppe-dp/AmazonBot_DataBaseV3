import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler,
    filters, ConversationHandler
)

# Configura il logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Stati della conversazione
TAG, ASIN = range(2)

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Benvenuto! Inviami il tuo *tag affiliato Amazon* per iniziare.", parse_mode="Markdown")
    return TAG

# Ricezione del tag affiliato
async def receive_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tag = update.message.text.strip()
    if len(tag) == 0:
        await update.message.reply_text("❌ Il tag affiliato non può essere vuoto. Riprova:")
        return TAG
    context.user_data['tag'] = tag
    await update.message.reply_text("Perfetto ✅! Ora inviami l'ASIN del prodotto Amazon.")
    return ASIN

# Ricezione dell'ASIN e generazione del link
async def receive_asin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asin = update.message.text.strip().upper()
    if len(asin) != 10:
        await update.message.reply_text("❌ L'ASIN deve essere lungo esattamente 10 caratteri. Riprova:")
        return ASIN
    tag = context.user_data.get('tag', 'TAG-MANCANTE')
    affiliate_link = f"https://www.amazon.it/dp/{asin}/?tag={tag}"
    await update.message.reply_text(
        f"🔗 *Il tuo link affiliato è:*\n{affiliate_link}\n\nInviami un altro ASIN o digita /cancel per uscire.",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    return ASIN

# Comando /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Conversazione annullata. Torna con /start quando vuoi.")
    return ConversationHandler.END

# Main
if __name__ == '__main__':
    application = ApplicationBuilder().token('7922127429:AAE7c31VvTThvOfHdOpw7gZqF1-zz4JjNhg').build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            TAG: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tag)],
            ASIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_asin)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()




#VERSIONE 2

#telegram import
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler,
    filters, ConversationHandler
)

#amazon import
from amazon.paapi import AmazonAPI

# Configura il logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Stati della conversazione
TAG, ASIN = range(2)
# Credenziali Amazon PAAPI
ACCESS_KEY = 'AKPAZ0CLMX1752770669'
SECRET_KEY = '25zLMhg8tVdFkzxG5r/RzcaQoBmh9hgvCppUKuB7'
COUNTRY = 'IT'


# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Benvenuto! Inviami il tuo *tag affiliato Amazon* per iniziare.", parse_mode="Markdown")
    return TAG


# Ricezione del tag affiliato
async def receive_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tag = update.message.text.strip()
    if len(tag) == 0:
        await update.message.reply_text("❌ Il tag affiliato non può essere vuoto. Riprova:")
        return TAG
    context.user_data['tag'] = tag
    await update.message.reply_text("Perfetto ✅! Ora inviami l'ASIN del prodotto Amazon.")
    return ASIN


# Ricezione dell'ASIN e generazione del link + info prodotto
async def receive_asin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asin = update.message.text.strip().upper()
    if len(asin) != 10:
        await update.message.reply_text("❌ L'ASIN deve essere lungo esattamente 10 caratteri. Riprova:")
        return ASIN

    tag = context.user_data.get('tag', 'ggph-21')
    print("DEBUG - Tag:", tag)
    print("DEBUG - ASIN:", asin)

    try:
        # Interrogazione API Amazon
        amazon = AmazonAPI(ACCESS_KEY, SECRET_KEY, tag, COUNTRY)
        item = amazon.get_items(asin)[0]

        title = item.title
        price = item.prices.amount if item.prices else "Prezzo non disponibile"
        currency = item.prices.currency if item.prices else ""
        url = item.detail_page_url

        msg = (
            f"📦 *{title}*\n"
            f"💰 Prezzo: {price} {currency}\n"
            f"🔗 [Link affiliato]({url})\n\n"
            "Inviami un altro ASIN o digita /cancel per uscire."
        )

        await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=False)

    except Exception as e:
        await update.message.reply_text(f"❌ Errore nel recupero del prodotto: {e}")
    
    return ASIN


# Comando /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Conversazione annullata. Torna con /start quando vuoi.")
    return ConversationHandler.END


# Comando /cerca
async def cerca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tag = context.user_data.get('tag')
    if not tag:
        await update.message.reply_text("❗ Prima usa /start e fornisci il tuo tag affiliato.")
        return

    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text("❗ Usa il comando così: /cerca auricolari bluetooth")
        return

    try:
        amazon = AmazonAPI(ACCESS_KEY, SECRET_KEY, tag, COUNTRY)
        products = amazon.search_items(keywords=query, search_index='All', item_count=3)

        if not products:
            await update.message.reply_text("❌ Nessun prodotto trovato.")
            return

        for p in products:
            msg = (
                f"📦 *{p.title}*\n"
                f"💰 Prezzo: {p.prices.amount if p.prices else 'N/D'} {p.prices.currency if p.prices else ''}\n"
                f"🔗 [Acquista su Amazon]({p.detail_page_url})"
            )
            await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=False)

    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante la ricerca: {e}")


# Main
if __name__ == '__main__':
    application = ApplicationBuilder().token('7922127429:AAE7c31VvTThvOfHdOpw7gZqF1-zz4JjNhg').build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            TAG: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tag)],
            ASIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_asin)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("cerca", cerca))
    application.run_polling()




#VERSIONE 3
import logging
import time
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
import requests
import hashlib
import hmac
import base64
from urllib.parse import quote, urlencode
from datetime import datetime, timezone


#amazon import
from amazon.paapi import AmazonAPI

# Stati conversazione
TAG, ASIN = range(2)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Credenziali Amazon (sostituisci con le tue)
ACCESS_KEY = 'AKPAZ0CLMX1752770669'
SECRET_KEY = '25zLMhg8tVdFkzxG5r/RzcaQoBmh9hgvCppUKuB7'  # chiave privata
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

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Inviami il tuo *tag affiliato Amazon* per iniziare.", parse_mode="Markdown")
    return TAG

# Ricezione tag
async def receive_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tag = update.message.text.strip()
    if not tag:
        await update.message.reply_text("❌ Il tag affiliato non può essere vuoto.")
        return TAG
    context.user_data['tag'] = tag
    await update.message.reply_text("Perfetto ✅! Ora inviami l'ASIN del prodotto Amazon.")
    return ASIN

# Ricezione ASIN
async def receive_asin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asin = update.message.text.strip().upper()
    tag = context.user_data.get('tag', 'TAG-MANCANTE')
    if len(asin) != 10:
        await update.message.reply_text("❌ L'ASIN deve essere di 10 caratteri.")
        return ASIN

    url = f"https://{ENDPOINT}/paapi5/getitems"
    payload = {
        "ItemIds": [asin],
        "Resources": ["ItemInfo.Title", "Offers.Listings.Price", "Images.Primary.Small", "DetailPageURL"],
        "PartnerTag": tag,
        "PartnerType": PARTNER_TYPE,
        "Marketplace": f"www.amazon.{COUNTRY.lower()}"
    }
    headers = sign_request({}, SECRET_KEY)

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        if 'ItemsResult' in data:
            item = data['ItemsResult']['Items'][0]
            title = item['ItemInfo']['Title']['DisplayValue']
            url = item['DetailPageURL']
            price = item['Offers']['Listings'][0]['Price']['DisplayAmount']

            msg = f"📦 *{title}*\n💰 Prezzo: {price}\n🔗 [Link affiliato]({url})"
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Prodotto non trovato o tag non valido.")

    except Exception as e:
        await update.message.reply_text(f"❌ Errore: {e}")

    time.sleep(1.1)  # Rispetta rate limit
    return ASIN

# /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Conversazione annullata.")
    return ConversationHandler.END

if __name__ == '__main__':
    app = ApplicationBuilder().token("7922127429:AAE7c31VvTThvOfHdOpw7gZqF1-zz4JjNhg").build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TAG: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tag)],
            ASIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_asin)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv)
    app.run_polling()



#VERSIONE 4

import logging
import time
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
import requests
import hashlib
import hmac
import base64
from urllib.parse import quote, urlencode
from datetime import datetime, timezone


#amazon import
from amazon.paapi import AmazonAPI

# Stati conversazione
TAG, ASIN = range(2)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Credenziali Amazon (sostituisci con le tue)
ACCESS_KEY = 'AKPAEJNYHX1753276095'
SECRET_KEY = 'ISXkWA/Ifazsn+stcK6ViK0OXt/Bk8bUpdJ4wOIa'  # chiave privata
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

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Inviami il tuo *tag affiliato Amazon* per iniziare.", parse_mode="Markdown")
    return TAG

# Ricezione tag
async def receive_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tag = update.message.text.strip()
    if not tag:
        await update.message.reply_text("❌ Il tag affiliato non può essere vuoto.")
        return TAG
    context.user_data['tag'] = tag
    await update.message.reply_text("Perfetto ✅! Ora inviami l'ASIN del prodotto Amazon.")
    return ASIN

# Ricezione ASIN
async def receive_asin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asin = update.message.text.strip().upper()
    tag = context.user_data.get('tag', 'TAG-MANCANTE')
    if len(asin) != 10:
        await update.message.reply_text("❌ L'ASIN deve essere di 10 caratteri.")
        return ASIN

    url = f"https://{ENDPOINT}/paapi5/getitems"
    payload = {
        "ItemIds": [asin],
        "Resources": ["ItemInfo.Title", "Offers.Listings.Price", "Images.Primary.Small", "DetailPageURL"],
        "PartnerTag": tag,
        "PartnerType": PARTNER_TYPE,
        "Marketplace": f"www.amazon.{COUNTRY.lower()}"
    }
    headers = sign_request({}, SECRET_KEY)

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        if 'ItemsResult' in data:
            item = data['ItemsResult']['Items'][0]
            title = item['ItemInfo']['Title']['DisplayValue']
            url = item['DetailPageURL']
            price = item['Offers']['Listings'][0]['Price']['DisplayAmount']

            msg = f"📦 *{title}*\n💰 Prezzo: {price}\n🔗 [Link affiliato]({url})"
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Prodotto non trovato o tag non valido.")

    except Exception as e:
        await update.message.reply_text(f"❌ Errore: {e}")

    time.sleep(1.1)  # Rispetta rate limit
    return ASIN

# /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Conversazione annullata.")
    return ConversationHandler.END

if __name__ == '__main__':
    app = ApplicationBuilder().token("7922127429:AAE7c31VvTThvOfHdOpw7gZqF1-zz4JjNhg").build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TAG: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tag)],
            ASIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_asin)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv)
    app.run_polling()
