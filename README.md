# 🛒 Amazon Restock Tracker & Telegram Notifier

This project is a high-performance automated system designed to monitor the availability of highly sought-after products on Amazon (such as trading card sets) and instantly notify a Telegram community.

## 🎯 Project Purpose
The main objective is to provide a time advantage during "drops" of hard-to-find products. When an item becomes available again and is officially sold by Amazon, reaction time is everything. 

The system continuously checks a custom list of ASINs. As soon as it detects a restock, it sends a formatted alert on Telegram containing details, price, and, most importantly, **Fast Checkout** links. These links bypass the normal cart steps, allowing for 1-click purchases.

## 🌟 How It Works (Main Features)

* **Web Control Panel (Dashboard):** The system features a complete UI to manage operations without touching the code. From the dashboard, you can:
  * Start/Stop the bot and set specific working hours.
  * Add, remove, or suspend products (ASINs) from the monitoring cycle.
  * Adjust latency times and view system logs in real-time.

* **Dynamic "Boost" Mode (Smart Polling):** The strategic core of the bot. During quiet periods, the system performs checks at regular intervals. However, as soon as a restock is detected on any product, the bot automatically enters "Boost Mode": it drastically reduces the waiting seconds between cycles to intercept the classic rapid restock "waves" typical of Amazon, before returning to normal after the event.

* **Dual Search Engine (API + Scraping):**
  * *Primary Engine:* Uses official APIs (Amazon PAAPI v5) for massive, fast, and low-resource checks.
  * *Secondary Engine (Fallback):* If the APIs do not return the `offering_id` (the vital code to generate the Fast Checkout link), the bot activates an invisible browser (via Playwright) to physically navigate the Amazon page and extract the data directly from the HTML code.

* **Local Relational Database:** Utilizes SQLite to maintain an accurate history. It stores not only the product registry but also tracks status changes (availability and prices), autonomously managing periodic cache resets.

## 🛠️ Architecture and Local Deployment
Being entirely based on asynchronous Python (`asyncio`), the project is highly optimized for networking I/O. This makes it the perfect candidate to run 24/7 locally on low-power devices, such as a Raspberry Pi or a home server. 

Simply prepare an isolated virtual environment (`python3 -m venv venv`), install the dependencies, and the bot will autonomously handle disconnection issues, rate-limiting (Too Many Requests), or network drops without ever crashing, thanks to a robust retry logic.

## Important ==> You must create an .env file with the following parameters: (Without valid keys, the Bot will not work!) 
  * BOT_TOKEN=
  * ACCESS_KEY=
  * SECRET_KEY=
  * TAG=
  * CHAT_ID=

## 📂 Main Components
* `main.py`: The main daemon that starts the Telegram listener and launches the background tasks in parallel.
* `watcher.py`: The core algorithm. Performs batch calls, evaluates product availability, calculates Boost timings, and formats messages for Telegram.
* `scraping.py`: The emergency module for extracting data from the page's DOM (Document Object Model).
* `database.py`: The data persistence layer that executes queries to update the status of ASINs.
* `App`: The folder containing the entire Web interface.

## 🚧 Work in Progress / Known Issues
* **Asyncio Optimization (Ongoing):**


# 🛒 Amazon Restock Tracker & Telegram Notifier

Questo progetto è un sistema automatizzato ad alte prestazioni nato per monitorare la disponibilità di prodotti molto richiesti su Amazon (come i set di carte collezionabili) e notificare istantaneamente una community su Telegram.

## 🎯 Scopo del Progetto
L'obiettivo principale è fornire un vantaggio temporale durante i "drop" di prodotti difficili da trovare. Quando un articolo torna disponibile ed è venduto ufficialmente da Amazon, il tempo di reazione è tutto. 

Il sistema verifica continuamente una lista di ASIN personalizzata. Appena rileva un ritorno in stock, invia un alert formattato su Telegram contenente dettagli, prezzo e, soprattutto, link di **Acquisto Lampo (Fast Checkout)**. Questi link bypassano i normali passaggi del carrello, permettendo l'acquisto in 1-click.

## 🌟 Come Funziona (Le Feature Principali)

* **Pannello di Controllo Web (Dashboard):** Il sistema è dotato di un'interfaccia UI completa per gestire le operazioni senza toccare il codice. Dalla dashboard è possibile:
  * Avviare/Fermare il bot e impostare specifiche fasce orarie di lavoro.
  * Aggiungere, rimuovere o sospendere i prodotti (ASIN) dal ciclo di monitoraggio.
  * Regolare i tempi di latenza e visualizzare i log di sistema in tempo reale.

* **Modalità "Boost" Dinamica (Smart Polling):** Il cuore strategico del bot. Durante i periodi di calma, il sistema effettua controlli a intervalli regolari. Tuttavia, appena viene rilevato un restock su un qualsiasi prodotto, il bot entra automaticamente in "Boost Mode": riduce drasticamente i secondi di attesa tra un ciclo e l'altro per intercettare le classiche "ondate" di restock ravvicinate tipiche di Amazon, per poi tornare alla normalità a fine evento.

* **Doppio Motore di Ricerca (API + Scraping):**
  * *Motore Primario:* Utilizza le API ufficiali (Amazon PAAPI v5) per controlli massivi, veloci e a basso consumo di risorse.
  * *Motore Secondario (Fallback):* Qualora le API non restituiscano l'`offering_id` (il codice vitale per generare il link di Fast Checkout), il bot attiva un browser invisibile (tramite Playwright) per navigare fisicamente sulla pagina Amazon ed estrarre il dato direttamente dal codice HTML.

* **Database Locale Relazionale:** Sfrutta SQLite per mantenere uno storico accurato. Memorizza non solo l'anagrafica dei prodotti, ma traccia anche le variazioni di stato (disponibilità e prezzi), gestendo in autonomia i reset periodici delle cache.

## 🛠️ Architettura e Deploy Locale
Essendo basato interamente su Python asincrono (`asyncio`), il progetto è estremamente ottimizzato per il networking I/O. Questo lo rende il candidato perfetto per girare H24 in locale su dispositivi a basso consumo, come un Raspberry Pi o un server domestico. 

È sufficiente preparare un ambiente virtuale isolato (`python3 -m venv venv`), installare le dipendenze, e il bot gestirà autonomamente problemi di disconnessione, rate-limiting (Too Many Requests) o drop di rete senza mai crashare, grazie a una robusta logica di retry.
## Importante ==> Bisogna creare un file .env con i seguenti parametri: (Senza delle key valide il Bot non funziona!) 
  * BOT_TOKEN=
  * ACCESS_KEY=
  * SECRET_KEY=
  * TAG=
  * CHAT_ID=

## 📂 Componenti Principali
* `main.py`: Il demone principale che avvia il listener Telegram e lancia i task di background in parallelo.
* `watcher.py`: L'algoritmo centrale. Effettua le chiamate batch, valuta la disponibilità dei prodotti, calcola le temporizzazioni del Boost e formatta i messaggi per Telegram.
* `scraping.py`: Il modulo di emergenza per l'estrazione dati dal DOM (Data Object Model) della pagina.
* `database.py`: Il layer di persistenza dati che esegue le query per aggiornare lo stato degli ASIN.
* `App`: La cartella contenente l'intera interfaccia Web.

## 🚧 Work in Progress / Known Issues
* **Ottimizzazione Asyncio (In corso):**
