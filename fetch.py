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
NAV_WAIT_TIMEOUT_MS = 45000  # Increased from 30000
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
        for _ in range(random.randint(2, 4)):
            page.evaluate(
                """() => { window.scrollBy(0, Math.floor(Math.random()*400)+100); }""")
            time.sleep(random.uniform(0.3, 0.8))
    except Exception:
        pass


def scrape_page(browser, url, ticker):
    """Create a fresh context for each page to avoid resource issues"""
    context = None
    page = None
    try:
        # Create new context for each scrape
        ua = os.environ.get("USER_AGENT", DEFAULT_USER_AGENT)
        context = browser.new_context(
            user_agent=ua,
            viewport=DEFAULT_VIEWPORT,
            locale=os.environ.get("LOCALE", DEFAULT_LOCALE),
            timezone_id=os.environ.get("TIMEZONE", DEFAULT_TIMEZONE),
        )
        context.add_init_script(make_stealth_script())

        page = context.new_page()

        print(f"Loading {ticker}...", file=sys.stderr)

        # Navigate with retry logic
        try:
            page.goto(url, wait_until="domcontentloaded",
                      timeout=NAV_WAIT_TIMEOUT_MS)
        except PWTimeoutError:
            print(
                f"WARNING: {ticker} initial load timeout, retrying...", file=sys.stderr)
            page.goto(url, wait_until="domcontentloaded",
                      timeout=NAV_WAIT_TIMEOUT_MS)

        # Wait for network to be idle OR specific element
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PWTimeoutError:
            print(
                f"WARNING: {ticker} networkidle timeout, continuing...", file=sys.stderr)

        # Extra wait for JS-rendered content
        time.sleep(random.uniform(3.0, 5.0))

        human_scroll(page)

        # Give more time after scroll
        time.sleep(random.uniform(1.0, 2.0))

        # Try to find element with explicit wait
        try:
            element = page.wait_for_selector(XPATH_TO_EXTRACT, timeout=5000)
            if element:
                value = element.inner_text().strip()
                print(f"SUCCESS: {ticker} -> {value}", file=sys.stderr)
                return value
        except PWTimeoutError:
            print(
                f"WARNING: {ticker} element not found after wait", file=sys.stderr)

        # Fallback: try query_selector
        element = page.query_selector(XPATH_TO_EXTRACT)
        if element:
            value = element.inner_text().strip()
            print(f"SUCCESS (fallback): {ticker} -> {value}", file=sys.stderr)
            return value
        else:
            print(f"ERROR: {ticker} element not found in DOM", file=sys.stderr)
            # Debug: save screenshot if in CI
            if os.environ.get("CI"):
                try:
                    page.screenshot(path=f"/tmp/{ticker}_debug.png")
                    print(
                        f"DEBUG: Screenshot saved for {ticker}", file=sys.stderr)
                except:
                    pass
            return "N/A"

    except Exception as e:
        print(f"ERROR: {ticker} -> {str(e)}", file=sys.stderr)
        return "N/A"
    finally:
        # Clean up resources
        if page:
            try:
                page.close()
            except:
                pass
        if context:
            try:
                context.close()
            except:
                pass
        # Small delay between tickers to avoid rate limiting
        time.sleep(random.uniform(2.0, 4.0))


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: docker run --rm <image> TICKER=URL [TICKER=URL ...]  > output.html", file=sys.stderr)
        sys.exit(2)

    args = sys.argv[1:]
    proxy_url = os.environ.get("PROXY")  # optional

    try:
        with sync_playwright() as p:
            launch_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",  # Better for headless
                "--disable-software-rasterizer",
            ]
            browser_launch_kwargs = {
                "headless": True,
                "args": launch_args,
                "slow_mo": 100,  # Add 100ms delay between operations
            }
            if proxy_url:
                browser_launch_kwargs["proxy"] = {"server": proxy_url}

            browser = p.chromium.launch(**browser_launch_kwargs)

            # Start HTML
            print("<html><body>")

            for arg in args:
                if '=' not in arg:
                    print(f"Skipping invalid argument: {arg}", file=sys.stderr)
                    continue
                ticker, url = arg.split('=', 1)
                value = scrape_page(browser, url, ticker)
                # Changed this line to include ticker in the visible text
                print(f'<div id="{ticker}">{ticker}: {value}</div>')

            print("</body></html>")

            browser.close()

    except Exception as e:
        print("FATAL ERROR: " + str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
