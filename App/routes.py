from flask import Flask, render_template, request, redirect, url_for
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
    cur.execute("SELECT * FROM static_data")
    products = cur.fetchall()

    cur.execute("SELECT asin FROM bot_asins")
    active_asins = [row["asin"] for row in cur.fetchall()]

    conn.close()
    return render_template("index.html", products=products, active_asins=active_asins)


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
        image_url = request.form["image_url"].strip()
        price = request.form["price"].strip()
        detail_page_url = f"https://www.amazon.it/dp/{asin}/?tag=ggph-21&psc=1"
        offering_id = request.form["offering_id"].strip()

        now = datetime.now(timezone.utc).isoformat()
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO static_data (asin, title, image_url, price, detail_page_url, offering_id, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(asin) DO UPDATE SET
                title=excluded.title,
                image_url=excluded.image_url,
                price=excluded.price,
                detail_page_url=excluded.detail_page_url,
                offering_id=excluded.offering_id,
                last_updated=datetime('now')
        """, (asin, title, image_url, price, detail_page_url, offering_id))
        conn.commit()
        conn.close()

        return redirect(url_for("index"))

    return render_template("add_product.html")


@app.route("/delete_product/<asin>")
def delete_product(asin):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM static_data WHERE asin = ?", (asin,))
    cur.execute("DELETE FROM bot_asins WHERE asin = ?", (asin,))
    cur.execute("DELETE FROM dynamic_status WHERE asin = ?", (asin,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)