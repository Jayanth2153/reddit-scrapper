"""
create_reddit_app.py — Automates Reddit app creation via browser.
Creates a "script" type app named AptoriBot and saves credentials to .env
"""

import time
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from playwright_stealth import Stealth

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ENV_FILE    = Path(".env")


def update_env(client_id: str, client_secret: str):
    content = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    lines = content.splitlines()

    def set_key(lines, key, value):
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                return lines
        lines.append(f"{key}={value}")
        return lines

    lines = set_key(lines, "REDDIT_CLIENT_ID", client_id)
    lines = set_key(lines, "REDDIT_CLIENT_SECRET", client_secret)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK]  .env updated with REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET")


def main():
    print("[INFO]  Starting Reddit app creator ...")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=CHROME_PATH,
            headless=False,
            slow_mo=80,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            storage_state=None,   # no saved cookies / localStorage
        )
        ctx.clear_cookies()
        page = ctx.new_page()
        Stealth().apply_stealth_sync(page)

        # ── Step 1: Manual login ────────────────────────────────────────
        print("\n[1/4]  Opening Reddit ...")
        print("=" * 60)
        print("  ACTION REQUIRED:")
        print("  A Chrome window will open. Log in with any Reddit account.")
        print("  You have 3 minutes. Script continues automatically.")
        print("=" * 60)
        page.goto("https://old.reddit.com/login", wait_until="domcontentloaded")
        time.sleep(5)
        print("       Waiting for you to log in ...")

        def is_logged_in():
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
                result = page.evaluate(
                    "() => { try { return document.body.innerText.includes('logout') "
                    "|| document.body.innerText.includes('log out') "
                    "|| !!document.querySelector('.logout'); } catch(e) { return false; } }"
                )
                return bool(result)
            except Exception:
                return False

        deadline = time.time() + 180
        while time.time() < deadline:
            try:
                url = page.url
                if "login" not in url.lower() and "reddit.com" in url:
                    time.sleep(3)
                    if is_logged_in():
                        print("       Logged in!")
                        break
                remaining = int(deadline - time.time())
                if remaining % 30 == 0 and remaining < 180:
                    print(f"       Still waiting ... ({remaining}s left)")
            except Exception:
                pass
            time.sleep(2)
        else:
            print("[ERR]  Login timeout. Please re-run the script.")
            browser.close()
            return

        # ── Step 2: Go to apps page ─────────────────────────────────────
        print("\n[2/4]  Navigating to reddit.com/prefs/apps ...")
        page.goto("https://old.reddit.com/prefs/apps/", wait_until="domcontentloaded")
        time.sleep(4)

        # ── Step 3: Click "create app" button ───────────────────────────
        print("\n[3/4]  Creating app ...")
        try:
            # Try "create another app" button first (if apps exist)
            btn = page.locator("text=create another app").first
            if btn.is_visible(timeout=3000):
                btn.click()
            else:
                raise Exception("not visible")
        except Exception:
            try:
                btn = page.locator("text=are you a developer? create an app").first
                btn.click()
            except Exception:
                # Try generic button containing "create"
                page.locator("button:has-text('create')").first.click()

        time.sleep(2)

        # ── Fill the form ───────────────────────────────────────────────
        # Name
        page.locator('input[name="name"]').fill("AptoriBot")
        time.sleep(0.5)

        # Select "script" type
        try:
            page.locator('input[value="script"]').check()
        except Exception:
            page.locator('label:has-text("script")').click()
        time.sleep(0.5)

        # Description (optional but helps)
        try:
            page.locator('textarea[name="description"]').fill(
                "Aptori Reddit engagement bot for API security community"
            )
        except Exception:
            pass
        time.sleep(0.3)

        # Redirect URI (required)
        try:
            page.locator('input[name="redirect_uri"]').fill("http://localhost:8080")
        except Exception:
            page.locator('input[placeholder*="redirect"]').fill("http://localhost:8080")
        time.sleep(0.5)

        # Submit
        try:
            page.locator("button:has-text('create app')").click()
        except Exception:
            page.locator("input[value='create app']").click()
        time.sleep(4)

        print("       App form submitted.")

        # ── Step 4: Extract credentials ─────────────────────────────────
        print("\n[4/4]  Extracting client_id and client_secret ...")
        time.sleep(2)

        page_text = page.content()

        # client_id is the text under "personal use script" label
        # It appears as a short alphanumeric string in the app card
        client_id     = None
        client_secret = None

        # Try to find via DOM
        try:
            # The client_id is in a div with class containing "app-id" or similar
            # It appears right under the app name as plain text
            app_id_el = page.locator(".app .client-id, #developed-apps .developed-app .app-id").first
            if app_id_el.count() > 0:
                client_id = app_id_el.inner_text().strip()
        except Exception:
            pass

        # Fallback: use evaluate to search the DOM
        if not client_id:
            try:
                result = page.evaluate("""() => {
                    // Look for the personal use script label and grab nearby text
                    const labels = [...document.querySelectorAll('*')];
                    for (const el of labels) {
                        if ((el.textContent || '').includes('personal use script')) {
                            const parent = el.closest('.developed-app') || el.parentElement?.parentElement;
                            if (parent) {
                                // client_id is usually the first text node in a specific span
                                const idEl = parent.querySelector('.app .client-id') ||
                                             parent.querySelector('[class*="client"]') ||
                                             parent.querySelector('p');
                                if (idEl) return idEl.innerText.trim();
                            }
                        }
                    }
                    return null;
                }""")
                if result:
                    client_id = result
            except Exception:
                pass

        # Secret
        try:
            secret_el = page.locator("text=secret").locator("..").locator("input, span, td").first
            if secret_el.count() > 0:
                client_secret = secret_el.get_attribute("value") or secret_el.inner_text().strip()
        except Exception:
            pass

        if not client_secret:
            try:
                client_secret = page.evaluate("""() => {
                    const tables = [...document.querySelectorAll('table, tr, td')];
                    for (const el of tables) {
                        if ((el.textContent || '').trim().toLowerCase() === 'secret') {
                            const next = el.nextElementSibling;
                            if (next) return next.innerText.trim();
                        }
                    }
                    // Try inputs
                    const inputs = [...document.querySelectorAll('input')];
                    for (const inp of inputs) {
                        const label = inp.labels?.[0]?.textContent || '';
                        if (label.toLowerCase().includes('secret')) return inp.value;
                    }
                    return null;
                }""")
            except Exception:
                pass

        # Screenshot for manual inspection if extraction fails
        page.screenshot(path="app_created.png", full_page=True)
        print("       Screenshot saved to app_created.png")

        if client_id and client_secret:
            print(f"\n  client_id     = {client_id}")
            print(f"  client_secret = {client_secret}")
            update_env(client_id, client_secret)
        else:
            print("\n[WARN]  Could not auto-extract credentials from the page.")
            print("        Open app_created.png to see the app details.")
            print("        Then manually add to .env:")
            print("          REDDIT_CLIENT_ID=<id shown under app name>")
            print("          REDDIT_CLIENT_SECRET=<secret value>")
            print("\n        Browser will stay open for 60 seconds for you to copy values...")
            time.sleep(60)

        browser.close()
        print("\n[OK]  Done.")


if __name__ == "__main__":
    main()
