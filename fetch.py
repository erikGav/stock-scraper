#!/usr/bin/env python3
import sys
import os
import random
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

# ---------- Configuration ----------
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}
DEFAULT_LOCALE = "en-US"
DEFAULT_TIMEZONE = "Europe/London"
NAV_WAIT_TIMEOUT_MS = 30000
XPATH_TO_EXTRACT = '//*[@id="performance"]/div/div/div[2]/div[3]/div/div[7]/span[2]/p'
# -----------------------------------

def make_stealth_script():
    return r"""
(() => {
  Object.defineProperty(navigator, 'webdriver', { get: () => false });
  Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
  Object.defineProperty(navigator, 'plugins', { get: () => ({ length: 3, 0:{},1:{},2:{} }) });
  window.chrome = window.chrome || { runtime:{} };
})();
"""

def human_scroll(page):
    try:
        for _ in range(random.randint(2, 5)):
            page.evaluate("""() => { window.scrollBy(0, Math.floor(Math.random()*400)+100); }""")
            time.sleep(random.uniform(0.2, 1.0))
    except Exception:
        pass

def scrape_page(page, url):
    try:
        page.goto(url, wait_until="networkidle", timeout=NAV_WAIT_TIMEOUT_MS)
    except PWTimeoutError:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

    human_scroll(page)
    time.sleep(random.uniform(0.2, 0.8))

    element = page.query_selector(XPATH_TO_EXTRACT)
    if element:
        return element.inner_text()
    else:
        return "N/A"

def main():
    if len(sys.argv) < 2:
        print("Usage: docker run --rm <image> TICKER=URL [TICKER=URL ...]  > output.html", file=sys.stderr)
        sys.exit(2)

    args = sys.argv[1:]
    proxy_url = os.environ.get("PROXY")  # optional

    try:
        with sync_playwright() as p:
            launch_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
            browser_launch_kwargs = {"headless": True, "args": launch_args}
            if proxy_url:
                browser_launch_kwargs["proxy"] = {"server": proxy_url}

            browser = p.chromium.launch(**browser_launch_kwargs)

            ua = os.environ.get("USER_AGENT", DEFAULT_USER_AGENT)
            context = browser.new_context(
                user_agent=ua,
                viewport=DEFAULT_VIEWPORT,
                locale=os.environ.get("LOCALE", DEFAULT_LOCALE),
                timezone_id=os.environ.get("TIMEZONE", DEFAULT_TIMEZONE),
            )

            context.add_init_script(make_stealth_script())
            page = context.new_page()

            extra_headers = {}
            if "ACCEPT_LANGUAGE" in os.environ:
                extra_headers["accept-language"] = os.environ["ACCEPT_LANGUAGE"]
            if extra_headers:
                page.set_extra_http_headers(extra_headers)

            # Start HTML
            print("<html><body>")

            for arg in args:
                if '=' not in arg:
                    print(f"Skipping invalid argument: {arg}", file=sys.stderr)
                    continue
                ticker, url = arg.split('=', 1)
                value = scrape_page(page, url)
                print(f'<div id="{ticker}">{value}</div>')

            print("</body></html>")
            browser.close()

    except Exception as e:
        print("ERROR: " + str(e), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

