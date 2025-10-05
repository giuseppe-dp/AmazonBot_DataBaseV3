from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3

from datetime import datetime, timezone


DB_NAME = "Data/products.db"

app = Flask(__name__)


def connect_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row  # restituisce dict-like rows
    return conn


@app.route("/")
def index():
    conn = connect_db()
    cur = conn.cursor()

    # Join per avere static + dynamic insieme
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
    
    return render_template("index.html", products=products, active_asins=active_asins, asins_count=asins_count, asins_active_count=asins_active_count)


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
    return redirect(url_for("index"))


@app.route("/remove_from_bot/<asin>")
def remove_from_bot(asin):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM bot_asins WHERE asin = ?", (asin,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


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

        return redirect(url_for("index"))

    return render_template("add_product.html")


@app.route("/delete_product/<asin>")
def delete_product(asin):
    conn = connect_db()
    cur = conn.cursor()

    # Grazie al CASCADE basta eliminare solo da static_data
    cur.execute("DELETE FROM static_data WHERE asin = ?", (asin,))

    conn.commit()
    conn.close()
    return redirect(url_for("index"))


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
 

if __name__ == "__main__":
    app.run(debug=True)