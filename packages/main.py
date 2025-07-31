import logging
import asyncio
import os
import nest_asyncio

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, ContextTypes
from telegram.constants import ParseMode
from telegram.error import NetworkError, TelegramError
from telegram import Update

from watcher import check_products, auto_reset

# nest_asyncio per evitare problemi con event loop già in esecuzione
nest_asyncio.apply()

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Carica variabili d'ambiente
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN mancante nel file .env")

# Creo l'app
app = ApplicationBuilder().token(BOT_TOKEN).build()


# Handler globale degli errori
async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("\nErrore gestito dal bot:", exc_info=context.error)


# Funzione che gestisce l'avvio con retry in caso di NetworkError
async def run_bot_with_retry():
    max_retries = 12
    delay = 5  # secondi

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("\nAvvio bot... (tentativo %d)", attempt)
            await app.run_polling()
            break  # esce dal ciclo se avvio riuscito
        except NetworkError as e:
            logger.warning("\nErrore di rete: %s", str(e))
            if attempt == max_retries:
                logger.error("\nNumero massimo di tentativi raggiunto. Esco.")
                raise
            else:
                logger.info("Riprovo tra %d secondi...", delay)
                await asyncio.sleep(delay)
        except TelegramError as e:
            logger.error("\nErrore Telegram irreversibile: %s", str(e))
            raise


# Main
async def main():
    # Avvia i task paralleli
    asyncio.create_task(check_products())
    asyncio.create_task(auto_reset())

    # Aggiunge l'handler di errore globale
    app.add_error_handler(error_handler)

    # Avvia il bot con gestione errori
    await run_bot_with_retry()


# Entry point
if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
