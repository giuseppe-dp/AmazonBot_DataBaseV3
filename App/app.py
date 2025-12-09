from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import json
import subprocess
import threading
import psutil
import os

DB_NAME = "Data/products.db"
CONFIG_PATH = Path.cwd() / "config.json"

app = Flask(__name__)
app.secret_key = "supersecret"


# ------------------------------
# Utility Functions
# ------------------------------
def connect_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row  # restituisce dict-like rows
    return conn


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# Variabile globale per salvare il processo in esecuzione
bot_process = None

def run_bot():
    """Esegue il bot in un thread separato"""
    global bot_process
    if bot_process is None or bot_process.poll() is not None:
        # Avvia il bot come processo separato
        bot_process = subprocess.Popen(["python", "./packages/main.py"], shell=True)
        print("✅ Bot avviato con PID:", bot_process.pid)
    else:
        print("⚠️ Bot già in esecuzione.")


@app.route("/run_bot")
def run_bot_route():
    """Endpoint per avviare il bot"""
    threading.Thread(target=run_bot, daemon=True).start()
    flash("🤖 Bot avviato in background!", "success")
    return redirect(url_for("home"))


@app.route("/stop_bot")
def stop_bot_route():
    """Endpoint per terminare il bot"""
    global bot_process
    if bot_process and bot_process.poll() is None:
        try:
            parent = psutil.Process(bot_process.pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
            bot_process = None
            flash("🛑 Bot terminato correttamente.", "info")
        except Exception as e:
            flash(f"❌ Errore durante l’arresto del bot: {e}", "danger")
    else:
        flash("⚠️ Nessun bot in esecuzione.", "warning")
    return redirect(url_for("home"))


@app.route("/status")
def status():
    """API per sapere se il bot è in esecuzione"""
    global bot_process
    running = bot_process is not None and bot_process.poll() is None
    return jsonify({"running": running})

        

# ------------------------------
# HOME PAGE (configurazioni)
# ------------------------------
@app.route("/")
@app.route("/home")
def home():
    cfg = load_config()
    return render_template('home.html', config=cfg)

@app.route('/update_config', methods=['POST'])
def update_config():
	cfg = load_config()
	cfg["work_start"] = request.form.get("work_start")
	cfg["work_end"] = request.form.get("work_end")
	cfg["timezone"] = request.form.get("timezone")

	cfg["boost_duration"] = int(request.form.get("boost_duration"))
	cfg["normal_interval"] = int(request.form.get("normal_interval"))
	cfg["boosted_interval"] = int(request.form.get("boosted_interval"))

	cfg["bot_paused"] = "bot_paused" in request.form
	cfg["scraping_on"] = "scraping_on" in request.form

	cfg["reset_time"] = int(request.form.get("reset_time"))

	save_config(cfg)
	return redirect(url_for('home'))


# ------------------------------
# DASHBOARD DATABASE
# ------------------------------
@app.route("/dashboard")
def dashboard():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT s.asin, s.title, d.image_url, d.price, d.detail_page_url, d.offering_id
        FROM static_data s
        LEFT JOIN dynamic_data d ON s.asin = d.asin
    """)
    products = cur.fetchall()

    cur.execute("SELECT asin FROM bot_asins")
    active_asins = [row["asin"] for row in cur.fetchall()]

    conn.close()

    asins_count = len(products)
    asins_active_count = len(active_asins)

    return render_template(
        "dashboard.html",
        products=products,
        active_asins=active_asins,
        asins_count=asins_count,
        asins_active_count=asins_active_count
    )


# ------------------------------
# Operazioni sul DB
# ------------------------------
@app.route("/add_to_bot/<asin>")
def add_to_bot(asin):
    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO bot_asins (asin) VALUES (?)", (asin,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/remove_from_bot/<asin>")
def remove_from_bot(asin):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM bot_asins WHERE asin = ?", (asin,))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/add_product", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        asin = request.form["asin"].strip()
        title = request.form["title"].strip()
        detail_page_url =  f"https://www.amazon.it/dp/{asin}/?tag=ggph-21&psc=1"
        offering_id = ''

        now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        conn = connect_db()
        cur = conn.cursor()

        # Inserisce o aggiorna static_data
        cur.execute("""
            INSERT INTO static_data (asin, title, last_updated)
            VALUES (?, ?, ?)
            ON CONFLICT(asin) DO UPDATE SET
                title=excluded.title,
                last_updated=excluded.last_updated
        """, (asin, title, now))

        # Inserisce la riga vuota in dynamic_data solo se non esiste già
        cur.execute("""
            INSERT OR IGNORE INTO dynamic_data 
            (asin, image_url, price, detail_page_url, offering_id, last_updated)
            VALUES (?, '', '', ?, ?, ?)
        """, (asin, detail_page_url, offering_id, now))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("add_product.html")


@app.route("/delete_product/<asin>")
def delete_product(asin):
    conn = connect_db()
    cur = conn.cursor()

    # Grazie al CASCADE basta eliminare solo da static_data
    cur.execute("DELETE FROM static_data WHERE asin = ?", (asin,))

    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/edit_dynamic/<asin>", methods=["GET", "POST"])
def edit_dynamic(asin):
    conn = connect_db()
    cur = conn.cursor()

    if request.method == "POST":
        # Prendi i valori dal form (se non forniti => stringa vuota)
        image_url = (request.form.get("image_url") or "").strip()
        price = (request.form.get("price") or "").strip()
        detail_page_url = (request.form.get("detail_page_url") or "").strip()
        offering_id = (request.form.get("offering_id") or "").strip()
        now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

        # Prende i dati da dynamic_data
        cur.execute("SELECT * FROM dynamic_data WHERE asin = ?", (asin,))
        existing = cur.fetchone()

        if existing:
            # Aggiorna solo i campi forniti
            updates = []
            params = []
            if image_url:
                updates.append("image_url = ?")
                params.append(image_url)
            if price:
                updates.append("price = ?")
                params.append(price)
            if detail_page_url:
                updates.append("detail_page_url = ?")
                params.append(detail_page_url)
            if offering_id:
                updates.append("offering_id = ?")
                params.append(offering_id)

            if updates:
                updates.append("last_updated = ?")
                params.append(now)
                params.append(asin)
                sql = f"UPDATE dynamic_data SET {', '.join(updates)} WHERE asin = ?"
                cur.execute(sql, params)
                conn.commit()
            else:
                print("Nessun valore fornito per la modifica")

        conn.close()
        return redirect(url_for("show_product", asin=asin))

    # GET -> mostra il form con i valori correnti (left join static + dynamic)
    cur.execute("""
        SELECT s.asin, s.title,
               d.image_url AS image_url,
               d.price AS price,
               d.detail_page_url AS detail_page_url,
               d.offering_id AS offering_id,
               d.last_updated AS last_updated
        FROM static_data s
        LEFT JOIN dynamic_data d ON s.asin = d.asin
        WHERE s.asin = ?
    """, (asin,))
    product = cur.fetchone()
    conn.close()

    return render_template("edit_dynamic.html", product=product)


@app.route("/show_product/<asin>")
def show_product(asin):
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT s.asin, s.title, d.image_url, d.price, d.detail_page_url, d.offering_id, d.last_updated
        FROM static_data s
        LEFT JOIN dynamic_data d ON s.asin = d.asin
        WHERE s.asin = ?
    """, (asin,))
    
    product = cur.fetchone()
    conn.close()

    conn.close()
    return render_template("show_product.html", asin=asin, product=product)

# ------------------------------
# Logs
# ------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # => App/
ROOT_DIR = os.path.dirname(BASE_DIR)                   # => progetto/
LOG_DIR = os.path.join(ROOT_DIR, "log")

@app.route("/logs")
def logs():
    bot_log_path = os.path.join(LOG_DIR, "bot.log")
    paapi_log_path = os.path.join(LOG_DIR, "paapi.log")

    bot_log = ""
    paapi_log = ""

    try:
        with open(bot_log_path, "r", encoding="utf-8") as f:
            bot_log = f.read()
    except FileNotFoundError:
        bot_log = "bot.log non trovato."

    try:
        with open(paapi_log_path, "r", encoding="utf-8") as f:
            paapi_log = f.read()
    except FileNotFoundError:
        paapi_log = "paapi.log non trovato."

    return render_template("logs.html", bot_log=bot_log, paapi_log=paapi_log)




if __name__ == "__main__":
    app.run(debug=True)