from datetime import datetime, timedelta, time
from pathlib import Path
from logger_config import bot_logger
import pytz
import json
import asyncio

CONFIG_PATH = Path.cwd() / "config.json"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(new_config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(new_config, f, indent=2, ensure_ascii=False)


def parse_time(tstr):
    """Converte 'HH:MM:SS' → oggetto time."""
    h, m, s = map(int, tstr.split(":"))
    return time(h, m, s)


def in_work_window(cfg=None):
    if cfg is None:
        cfg = load_config()

    tz = pytz.timezone(cfg["timezone"])
    now = datetime.now(tz).time()

    start = parse_time(cfg["work_start"])
    end = parse_time(cfg["work_end"])

    # Fasce che attraversano la mezzanotte
    if start <= end:
        return start <= now <= end
    else:
        return now >= start or now <= end


def seconds_to_next_start(cfg=None):
    if cfg is None:
        cfg = load_config()

    tz = pytz.timezone(cfg["timezone"])
    now = datetime.now(tz)
    start_time = parse_time(cfg["work_start"])

    # Costruisci datetime per oggi
    start_dt = tz.localize(datetime.combine(now.date(), start_time))

    # se siamo già oltre la fascia, aggiungi un giorno
    if now.time() > start_time:
        start_dt += timedelta(days=1)

    delta = (start_dt - now).total_seconds()
    return int(delta)


def is_paused(cfg=None):
    """Controlla se il bot è in pausa tramite config.json"""
    if cfg is None:
        cfg = load_config()
    return cfg.get("bot_paused", False)


async def wait_until_ready():
    """
    Controlla se il bot è in pausa o fuori orario di lavoro,
    e dorme finché non può operare.
    """

    while True:
        cfg = load_config()

        # 🔹 Controllo pausa
        if is_paused(cfg):
            bot_logger.info("⏸️ Bot in pausa — dormo finché non viene riattivato...")
            while is_paused():
                await asyncio.sleep(10)
            bot_logger.info("▶️ Bot riattivato — riprendo l'attività!")
            continue  # ricarica cfg e ricontrolla fascia oraria

        # 🔹 Controllo orario di lavoro
        if not in_work_window(cfg):
            secs = seconds_to_next_start(cfg)
            hours = secs // 3600
            minutes = (secs % 3600) // 60
            seconds = secs % 60

            if hours > 0:
                bot_logger.info(f"🌙 Fuori orario di lavoro, dormo per {hours}h {minutes}m {seconds}s...")
            elif minutes > 0:
                bot_logger.info(f"🌙 Fuori orario di lavoro, dormo per {minutes}m {seconds}s...")
            else:
                bot_logger.info(f"🌙 Fuori orario di lavoro, dormo per {seconds}s...")

            await asyncio.sleep(secs + 5)
            bot_logger.info("☀️ Orario di lavoro, Gotta catch 'em all")
            continue

        # Se tutto ok (attivo e in orario), esci e lascia lavorare
        return