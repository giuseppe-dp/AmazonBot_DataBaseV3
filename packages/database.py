import sqlite3
from datetime import datetime, timezone, timedelta


def connect_db():
    conn = sqlite3.connect("Data/products.db")
    conn.execute("PRAGMA foreign_keys = ON") # Importante! Attiva le foreign key in ogni connessione
    return conn


def init_db():
    with connect_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS static_data (
                asin TEXT PRIMARY KEY,
                title TEXT,
                image_url TEXT,
                price TEXT,
                detail_page_url TEXT,
                offering_id TEXT,
                last_updated TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dynamic_status (
                asin TEXT PRIMARY KEY,
                available INTEGER,
                availability_type TEXT,
                merchant_name TEXT,
                last_checked TEXT,
                FOREIGN KEY (asin) REFERENCES static_data(asin)
                FOREIGN KEY (asin) REFERENCES static_data(asin) ON DELETE CASCADE
            )
        """)
        # Tabella prodotti usati dal bot
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_asins (
                asin TEXT PRIMARY KEY,
                FOREIGN KEY (asin) REFERENCES static_data(asin)
                FOREIGN KEY (asin) REFERENCES static_data(asin) ON DELETE CASCADE
            )
        """)
        conn.commit()


def get_asins_from_db():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT asin FROM static_data")
    asins = [row[0] for row in cursor.fetchall()]
    conn.close()
    return asins


def get_active_asins():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT asin FROM bot_asins")
    asins = [row[0] for row in cursor.fetchall()]
    conn.close()
    return asins


def upsert_static_data(asin, title, image_url, price, detail_page_url, offering_id):
    now = datetime.now(timezone.utc).isoformat()
    with connect_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO static_data (asin, title, image_url, price, detail_page_url, offering_id, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asin) DO UPDATE SET
                title=excluded.title,
                image_url=excluded.image_url,
                price=excluded.price,
                detail_page_url=excluded.detail_page_url,
                offering_id=excluded.offering_id,
                last_updated=excluded.last_updated
        """, (asin, title, image_url, price, detail_page_url, offering_id, now))
        conn.commit()


def upsert_dynamic_status(asin, available, availability_type, merchant_name):
    now = datetime.now(timezone.utc).isoformat()
    with connect_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO dynamic_status (asin, available, availability_type, merchant_name, last_checked)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(asin) DO UPDATE SET
                available=excluded.available,
                availability_type=excluded.availability_type,
                merchant_name=excluded.merchant_name,
                last_checked=excluded.last_checked
        """, (asin, available, availability_type, merchant_name, now))
        conn.commit()


def get_static_data(asin):
    with connect_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT title, image_url, price, detail_page_url, offering_id FROM static_data WHERE asin = ?", (asin,))
        return cur.fetchone()  # ritorna una tupla o None   


def needs_static_update(asin):
    with connect_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT last_updated FROM static_data WHERE asin = ?", (asin,))
        result = cur.fetchone()
        if not result:
            return True
        last_updated = datetime.fromisoformat(result[0])
        return datetime.now(timezone.utc) - last_updated > timedelta(hours=24)
    

def add_to_bot(asin):
    # Aggiunge un ASIN alla lista dei prodotti monitorati dal bot
    with connect_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO bot_asins (asin) VALUES (?)", (asin,))
            conn.commit()
            print(f"✅ ASIN {asin} aggiunto alla lista del bot.")
        except sqlite3.IntegrityError:
            print(f"⚠️ ASIN {asin} già presente nella lista del bot.")


def remove_from_bot(asin):
    # Rimuove un ASIN dalla lista dei prodotti monitorati dal bot
    with connect_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM bot_asins WHERE asin = ?", (asin,))
        conn.commit()
        if cur.rowcount > 0:
            print(f"❌ ASIN {asin} rimosso dalla lista del bot.")
        else:
            print(f"⚠️ ASIN {asin} non trovato nella lista del bot.")


if __name__ == '__main__':
    init_db()

    print("📌 Lista ASIN attivi nel bot:", get_active_asins())
