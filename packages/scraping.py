import asyncio
from playwright.async_api import async_playwright
import re

async def scraping_data(asin: str, domain: str = "amazon.it"):
    url = f"https://www.{domain}/dp/{asin}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=True se vuoi senza finestra
        page = await browser.new_page()

        try:
            await page.goto(url, timeout=5000)
        except Exception as e:
            print(f"Errore nel caricamento della pagina {url}: {e}")
            await browser.close()
            return {"image_url": "", "offering_id": "", "price": ""}


        # Immagine principale
        image_url = await page.get_attribute("#landingImage", "data-old-hires")
        if not image_url:  # prova attributo alternativo
            image_url = await page.get_attribute("#landingImage", "src") or ""


        # Cerca il merchant nella pagina
        m_element = await page.query_selector("#merchantInfoFeature_feature_div .offer-display-feature-text-message")
        merchant_name = (await m_element.inner_text()).strip().lower() if m_element else ""

        # Controlla se è Amazon
        is_amazon = "amazon" in merchant_name

        offering_id = ""
        price = ""

        if is_amazon:
            # OfferListingID - ricerca multipla
            selectors = [
                "#offerListingID",
                "#offeringID",
                "#oid",
            ]

            for selector in selectors:
                element = await page.query_selector(selector)
                if element:
                    offering_id = await element.get_attribute("value")
                    if offering_id:
                        break

            # Prezzo
            price_elem = await page.query_selector("#corePrice_feature_div span.a-offscreen")
            price = await price_elem.text_content() if price_elem else ""


        await browser.close()

        data = {
            "image_url": image_url or "",
            "offering_id": offering_id or "",
            "price": price or ""
        }

        print(f"\n\nPer l'asin: \033[33m {asin} \033[0m sono stati trovati i seguenti parametri:\n")
        print(f"image: {data['image_url']}")
        print(f"offering_id: {data['offering_id']}")
        print(f"price: {data['price']}\n\n")

        return data


if __name__ == "__main__":
    asin = "B0FB3JMXQ9"
    data = asyncio.run(scraping_data(asin))