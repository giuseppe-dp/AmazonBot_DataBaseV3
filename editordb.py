import json
import os

DB_PATH = "packages/db.json"

def carica_db():
    if not os.path.exists(DB_PATH):
        return []
    with open(DB_PATH, "r") as f:
        return json.load(f)

def salva_db(data):
    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print("✅ Database aggiornato.")

def mostra_db(db):
    print("\n📦 ASIN nel database:")
    if not db:
        print("  (vuoto)")
    for item in db:
        stato = "🟢 Disponibile" if item["last_available"] else "🔴 Non disponibile"
        print(f"  - {item['asin']} ({stato})")
    print()

def aggiungi_asin(db):
    asin = input("Inserisci il nuovo ASIN: ").strip().upper()
    if any(item["asin"] == asin for item in db):
        print("⚠️  Questo ASIN è già presente.")
    else:
        db.append({"asin": asin, "last_available": False})
        print("✅ ASIN aggiunto.")

def rimuovi_asin(db):
    asin = input("Inserisci l'ASIN da rimuovere: ").strip().upper()
    original_len = len(db)
    db[:] = [item for item in db if item["asin"] != asin]
    if len(db) < original_len:
        print("✅ ASIN rimosso.")
    else:
        print("⚠️  ASIN non trovato.")

def main():
    while True:
        db = carica_db()
        mostra_db(db)
        print("Opzioni:")
        print("  1. Aggiungi ASIN")
        print("  2. Rimuovi ASIN")
        print("  3. Esci")

        scelta = input("Scegli un'opzione: ").strip()

        if scelta == "1":
            aggiungi_asin(db)
            salva_db(db)
        elif scelta == "2":
            rimuovi_asin(db)
            salva_db(db)
        elif scelta == "3":
            print("👋 Uscita.")
            break
        else:
            print("❌ Opzione non valida.")

if __name__ == "__main__":
    main()
