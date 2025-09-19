import sqlite3
from datetime import datetime, timezone


def connect_db():
    conn = sqlite3.connect("Data/products.db")
    conn.execute("PRAGMA foreign_keys = ON") # Importante! Attiva le foreign key in ogni connessione
    return conn


def count_asins():
    """Conta quanti ASIN sono presenti nella tabella static_data."""
    with connect_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM static_data")
        count = cur.fetchone()[0]
    return count


def insert_or_update_static_data():
    asin = input("Inserisci ASIN: ").strip()
    title = input("Titolo: ").strip()
    image_url = input("URL immagine: ").strip()
    price = input("Prezzo: ").strip()
    detail_page_url =  f"https://www.amazon.it/dp/{asin}/?tag=ggph-21&psc=1"
    offering_id = input("Offering_id: ").strip()

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
    print(f"\n✅ Inserito/aggiornato prodotto {asin} nel database.\n")



def remove_asin():
    asin = input("Inserisci ASIN da rimuovere: ").strip()

    with connect_db() as conn:
        cur = conn.cursor()

        # Controllo se l'ASIN esiste
        cur.execute("SELECT asin FROM static_data WHERE asin = ?", (asin,))
        result = cur.fetchone()
        if not result:
            print(f"\n❌ ASIN {asin} non trovato nel database.\n")
            return

        # Rimuove il record da static_data (dynamic_status si elimina da solo con ON DELETE CASCADE)
        cur.execute("DELETE FROM static_data WHERE asin = ?", (asin,))
        conn.commit()
        print(f"\n✅ Prodotto {asin} rimosso correttamente dal database.\n")



def view_all_products():
    conn = connect_db()
    c = conn.cursor()

    c.execute("SELECT * FROM static_data")
    rows = c.fetchall()

    if not rows:
        print("\nℹ️ Nessun prodotto nel database.\n")
    else:
        total_asins = count_asins()
        print(f"\n📦 {total_asins} prodotti nel database:\n")
        for row in rows:
            asin, title, image_url, price, detail_page_url, offering_id, last_updated = row
            print(f"- ASIN: {asin}")
            print(f"  Titolo: {title}")
            print(f"  Image: {image_url}")
            print(f"  Prezzo: {price}")
            print(f"  URL: {detail_page_url}")
            print(f"  Offering_id: {offering_id}")
            print(f"  Ultimo aggiornamento: {last_updated}\n\n")

    conn.close()



def menu():
    while True:
        print("======== Editor database prodotti ========")
        print("1. Inserisci o aggiorna un prodotto")
        print("2. Rimuovi un prodotto")
        print("3. Visualizza tutti i prodotti")
        print("4. Esci")
        scelta = input("Seleziona un'opzione: ").strip()

        if scelta == "1":
            insert_or_update_static_data()
        elif scelta == "2":
            remove_asin()
        elif scelta == "3":
            view_all_products()
        elif scelta == "4":
            break
        else:
            print("\n❌ Opzione non valida.\n")

if __name__ == "__main__":
    menu()