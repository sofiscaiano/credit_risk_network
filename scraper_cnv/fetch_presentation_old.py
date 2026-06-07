import asyncio
from playwright.async_api import async_playwright

URL = "https://aif2.cnv.gov.ar/Presentations/publicview/8a51ccc3-2463-4d23-a6a3-c7d0e1543e83"
OUT_XML = "/tmp/cnv_30500120882_old.xml"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(URL, wait_until="networkidle")
        presentation = await page.evaluate("""() => {
            try { return window.presentation; } catch(e) { return null; }
        }""")
        if presentation:
            with open(OUT_XML, "w", encoding="utf-8") as f:
                f.write(presentation)
            print("Saved old XML")
        else:
            print("No window.presentation")
        await browser.close()

asyncio.run(main())
