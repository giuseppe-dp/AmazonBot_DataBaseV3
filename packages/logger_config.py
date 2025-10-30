import logging
from pathlib import Path

# === CARTELLA LOG ===
LOG_DIR = Path.cwd() / "log"
LOG_DIR.mkdir(exist_ok=True)

# === FILE DI LOG ===
BOT_LOG_PATH = LOG_DIR / "bot.log"
PAAPI_LOG_PATH = LOG_DIR / "paapi.log"

# === FORMATTO COMUNE ===
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DATE_FORMAT = "[%Y-%m-%d %H:%M:%S]"

# === LOGGER BOT ===
bot_logger = logging.getLogger("bot")
bot_logger.setLevel(logging.INFO)

bot_file_handler = logging.FileHandler(BOT_LOG_PATH, encoding="utf-8", mode="w")
bot_console_handler = logging.StreamHandler()

bot_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
bot_file_handler.setFormatter(bot_formatter)
bot_console_handler.setFormatter(bot_formatter)

bot_logger.addHandler(bot_file_handler)    # scrive in file
bot_logger.addHandler(bot_console_handler) # scrive in chat


# === LOGGER TELEGRAM ===
# Inoltra i log di PTB al nostro bot_logger
telegram_logger = logging.getLogger("telegram")
telegram_logger.setLevel(logging.INFO)

# Rimuove eventuali handler predefiniti
telegram_logger.handlers = []

# Aggiunge gli stessi handler del bot_logger
for handler in bot_logger.handlers:
    telegram_logger.addHandler(handler)
    
# si potrebbe reinderizare ache le richeste https...

# === LOGGER PAAPI ===
paapi_logger = logging.getLogger("paapi")
paapi_logger.setLevel(logging.INFO)

paapi_file_handler = logging.FileHandler(PAAPI_LOG_PATH, encoding="utf-8", mode="w")
paapi_console_handler = logging.StreamHandler()

paapi_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
paapi_file_handler.setFormatter(paapi_formatter)
paapi_console_handler.setFormatter(paapi_formatter)

paapi_logger.addHandler(paapi_file_handler)
paapi_logger.addHandler(paapi_console_handler)


# === DISATTIVA LOG RUMOROSI DI LIBRERIE ESTERNE ===
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext._application").setLevel(logging.WARNING)