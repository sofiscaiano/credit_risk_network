import asyncio
from playwright.async_api import async_playwright

URL = "https://aif2.cnv.gov.ar/Presentations/publicview/c9a06555-e84f-414b-a1b6-18b609eb42d5"
OUT_HTML = "/tmp/cnv_30500120882.html"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(URL, wait_until="networkidle")
        # Try to get the variable via page.evaluate
        presentation = await page.evaluate("""() => {
            try { return window.presentation; } catch(e) { return null; }
        }""")
        if presentation:
            print("Got presentation via evaluate")
            with open("/tmp/cnv_30500120882_presentation.xml", "w", encoding="utf-8") as f:
                f.write(presentation)
        else:
            print("window.presentation not available")
            html = await page.content()
            with open(OUT_HTML, "w", encoding="utf-8") as f:
                f.write(html)
            # Print any script lines mentioning presentation
            for line in html.splitlines():
                if "presentation" in line.lower():
                    print(line[:500])
        await browser.close()

asyncio.run(main())
