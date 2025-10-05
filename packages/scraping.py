import asyncio
from playwright.async_api import async_playwright
import re


async def scraping_data(asin: str, domain: str = "amazon.it"):
    url = f"https://www.{domain}/dp/{asin}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # True = headless
        page = await browser.new_page()
        await page.goto(url, timeout=5000)

        # Immagine principale
        image_url = await page.get_attribute("#landingImage", "data-old-hires")

        # OfferListingID (se disponibile)
        element = await page.query_selector("#offerListingID")
        offering_id = await element.get_attribute("value") if element else ""

        if not offering_id:
            # Fallback: cerca nel sorgente HTML
            html = await page.content()
            match = re.search(r'"offerListingID"\s*:\s*"([^"]+)"', html)
            if match:
                offering_id = match.group(1)

        # Prezzo
        price = await page.text_content("#corePrice_feature_div span.a-offscreen")

        await browser.close()

        data = {
            "image_url": image_url or "",
            "offering_id": offering_id or "",
            "price": price or ""
        }

        print(f"\n\nPer l'asin: \033[33m {asin} \033[0m sono stati trovati i seguenti parametri:\n")
        print(f"\nimage: {data['image_url']}")
        print(f"offering_id: {data['offering_id']}")
        print(f"price: {data['price']}\n\n")

        return data


if __name__ == "__main__":
    asin = "B0FB3JMXQ9"
    data = asyncio.run(scraping_data(asin))