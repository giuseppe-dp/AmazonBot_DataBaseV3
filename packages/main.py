import asyncio
import os
import nest_asyncio
import signal

from dotenv import load_dotenv
from datetime import datetime
import time
from telegram.ext import ApplicationBuilder, ContextTypes
from telegram.constants import ParseMode
from telegram.error import NetworkError, TelegramError
from telegram import Update

import httpx

from watcher import check_products, auto_reset

from logger_config import bot_logger

# nest_asyncio per evitare problemi con event loop già in esecuzione
nest_asyncio.apply()

# Carica variabili d'ambiente
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN mancante nel file .env")


# === COOLDOWN PER EVITARE SPAM DI ERRORI ===
last_network_error_time = 0
NETWORK_ERROR_COOLDOWN = 60  # secondi

# === HANDLER GLOBALE TELEGRAM ===
async def telegram_error_handler(update, context):
    global last_network_error_time
    error = context.error

    # Gestione problemi di rete (DNS, connessione, ecc.)
    if isinstance(error, NetworkError) and isinstance(error.__cause__, httpx.ConnectError):
        now = time.time()
        if now - last_network_error_time < NETWORK_ERROR_COOLDOWN:
            # Ignora errori ripetuti nello stesso intervallo
            return
        last_network_error_time = now

        bot_logger.warning("🌐 Errore di connessione Telegram (getaddrinfo failed).")
        bot_logger.info(f"🔁 Riprovo tra {NETWORK_ERROR_COOLDOWN} secondi...")
        await asyncio.sleep(NETWORK_ERROR_COOLDOWN)
        return

    elif isinstance(error, NetworkError) and isinstance(error.__cause__, httpx.ReadTimeout):
        bot_logger.warning("⏱️ Timeout nella connessione Telegram.")
        await asyncio.sleep(30)
        return

    bot_logger.exception("❌ Errore Telegram non gestito: %s", str(error))

# Creo l'app
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_error_handler(telegram_error_handler)


# === Funzione che gestisce l'avvio con retry in caso di NetworkError ===
async def run_bot_with_retry():
    max_retries = 20
    delay = 5  # secondi

    for attempt in range(1, max_retries + 1):
        try:
            bot_logger.info("Avvio telegram... (tentativo %d)", attempt)
            await app.run_polling()
            break
        except NetworkError as e:
            bot_logger.warning("🌐 Errore di rete: %s", str(e))
            if attempt == max_retries:
                bot_logger.error("❌ Numero massimo di tentativi raggiunto. Esco.")
                raise
            else:
                bot_logger.info("🔁 Riprovo tra %d secondi...", delay)
                await asyncio.sleep(delay)
        except TelegramError as e:
            bot_logger.error("💥 Errore Telegram irreversibile: %s", str(e))
            raise


async def main():
    
    # Avvia i task paralleli
    asyncio.create_task(check_products())
    asyncio.create_task(auto_reset())

    # Avvia il bot con gestione errori
    await run_bot_with_retry()

    bot_logger.info("=== Bot terminato ===")
    

# Entry point
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        bot_logger.info("🛑 Interruzione manuale (Ctrl+C) — chiusura sicura in corso...")
    except Exception as e:
        bot_logger.exception("❌ Errore critico: %s", e)
