"""
setup_session.py — Opens a real Chrome window for you to log into Reddit manually.
Saves session cookies so post_comments.py can post without a login challenge.

Run once:
    python setup_session.py
"""

import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME_PATH  = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
COOKIES_FILE = "reddit_cookies.json"

print("=" * 60)
print("  Starting Chrome — please wait ...")
print("=" * 60)

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path=CHROME_PATH,
        headless=False,
        args=["--start-maximized"],
    )
    ctx  = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.goto("https://www.reddit.com/login/", wait_until="domcontentloaded")

    print("\n  Chrome is open at the Reddit login page.")
    print("  Please log in with:")
    print("    Username: aptoridemo")
    print("    Password: Demo@1234")
    print("\n  Waiting up to 10 minutes for you to log in ...")
    print("=" * 60)

    deadline = time.time() + 600  # 10 minutes
    tick = 0
    while time.time() < deadline:
        time.sleep(1)
        tick += 1
        try:
            url = page.url
            if "reddit.com" in url and "/login" not in url and "/register" not in url:
                print(f"\n  Login detected at: {url[:60]}")
                break
        except Exception:
            pass
        if tick % 15 == 0:
            remaining = int(deadline - time.time())
            print(f"  Waiting ... {remaining}s remaining. Please log in in the Chrome window.")
    else:
        print("\n  Timed out. Run this script again.")
        browser.close()
        sys.exit(1)

    time.sleep(3)
    cookies = ctx.cookies()
    reddit_cookies = [c for c in cookies if "reddit" in c.get("domain", "")]
    Path(COOKIES_FILE).write_text(json.dumps(reddit_cookies, indent=2))
    print(f"\n  Saved {len(reddit_cookies)} cookies to {COOKIES_FILE}")
    print("  Now run: python post_comments.py reddit_engagement_20260619_174219.json")
    browser.close()
