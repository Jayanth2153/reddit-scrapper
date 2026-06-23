"""
post_comments.py -- Auto-posts Claude-generated comments to Reddit
using real Chrome browser with stealth mode.
"""

import sys
import json
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from playwright_stealth import Stealth

CHROME_PATH         = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DELAY_BETWEEN_POSTS = 45
BUTTON_WAIT_SECS    = 20


def human_pause(a=1.5, b=3.0):
    time.sleep(random.uniform(a, b))


def human_type(locator, text: str):
    for char in text:
        locator.press(char)
        time.sleep(random.uniform(0.03, 0.09))


def wait_for_comment_button(page, timeout=BUTTON_WAIT_SECS):
    """Poll for an enabled Comment/Submit button (searches shadow DOM too)."""
    deadline = time.time() + timeout
    attempt  = 0
    while time.time() < deadline:
        attempt += 1
        result = page.evaluate('''() => {
            function deepFindBtn(root) {
                const btns = [...root.querySelectorAll("button")];
                const btn = btns.find(b => {
                    const t = (b.innerText || b.textContent || "").trim();
                    return (t === "Comment" || t === "Submit") && !b.disabled;
                });
                if (btn) return btn;
                for (const n of root.querySelectorAll("*")) {
                    if (n.shadowRoot) {
                        const f = deepFindBtn(n.shadowRoot);
                        if (f) return f;
                    }
                }
                return null;
            }
            const btn = deepFindBtn(document);
            if (btn) {
                btn.click();
                return (btn.innerText || btn.textContent || "Comment").trim();
            }
            return null;
        }''')
        if result:
            return result
        if attempt % 5 == 0:
            remaining = int(deadline - time.time())
            print(f"      [WAIT]  Comment button not ready yet ... ({remaining}s left)")
        time.sleep(1)
    return None


def verify_comment(page, post_url: str, comment_text: str) -> bool:
    """Revisit the post sorted by 'new' and check comment appears in rendered text."""
    snippet = comment_text[:80].lower()
    try:
        url = post_url.rstrip("/") + "?sort=new"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        human_pause(5, 7)
        for _ in range(12):
            page.evaluate("window.scrollBy(0, 300)")
            human_pause(0.3, 0.5)
        human_pause(3, 4)
        rendered = page.evaluate("document.body.innerText").lower()
        return snippet in rendered
    except Exception:
        return False


def post_comment(page, post_url: str, comment_text: str, title: str) -> bool:
    print(f"\n  [POST]  Opening post ...")
    print(f"          {title[:72]}")

    try:
        page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
        human_pause(5, 7)

        for _ in range(10):
            page.evaluate("window.scrollBy(0, 200)")
            human_pause(0.3, 0.5)

        human_pause(2, 3)

        box = page.evaluate('''() => {
            const selectors = [
                "faceplate-textarea-input",
                "comment-body-header",
                "comment-composer-host",
                "shreddit-composer",
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (!el) continue;
                const r = el.getBoundingClientRect();
                if (r.width > 100 && r.height > 10) {
                    return {sel, x: r.left + r.width/2, y: r.top + r.height/2, w: r.width, h: r.height};
                }
            }
            return null;
        }''')

        if not box:
            print("  [WARN]  No comment area found on page.")
            return False

        print(f"          Found '{box['sel']}' at y={box['y']:.0f} -- clicking ...")
        page.mouse.click(box['x'], box['y'])
        human_pause(2, 3)

        typed_via = page.evaluate("""(text) => {
            function deepFind(sel, root) {
                let el = root.querySelector(sel);
                if (el) return el;
                for (const n of root.querySelectorAll("*")) {
                    if (n.shadowRoot) {
                        const f = deepFind(sel, n.shadowRoot);
                        if (f) return f;
                    }
                }
                return null;
            }
            const ce = deepFind("[contenteditable=true]", document);
            const ta = deepFind("textarea", document);
            const el = ce || ta;
            if (!el) return null;

            el.focus();

            if (el.isContentEditable) {
                document.execCommand('insertText', false, text);
                return 'contenteditable+execCommand';
            } else {
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value'
                ).set;
                setter.call(el, text);
                el.dispatchEvent(new Event('input',  {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
                return 'textarea+nativeSetter';
            }
        }""", comment_text)

        if typed_via:
            print(f"          Typed via {typed_via}")
        else:
            print("          Shadow find missed -- falling back to keyboard.type()")
            page.keyboard.type(comment_text, delay=30)

        human_pause(2, 3)

        print(f"          Waiting for Comment button to enable ...")
        submitted = wait_for_comment_button(page, timeout=BUTTON_WAIT_SECS)

        if not submitted:
            print("  [FAIL]  Comment button never enabled -- skipping.")
            return False

        human_pause(4, 6)
        print(f"  [OK]    Submitted via '{submitted}' button -- verifying ...")

        verified = verify_comment(page, post_url, comment_text)
        if verified:
            print(f"  [OK]    Verified: comment is live on the post!")
            return True
        else:
            print(f"  [WARN]  Submitted but comment not found yet (may be in moderation).")
            return False

    except PWTimeout:
        print(f"  [WARN]  Timed out -- skipping.")
        return False
    except Exception as e:
        print(f"  [ERR]   Error: {e}")
        return False


def main():
    if len(sys.argv) != 4:
        print("Usage: python post_comments.py <json_file> <username> <password>")
        sys.exit(1)

    json_file, username, password = sys.argv[1], sys.argv[2], sys.argv[3]
    posts = json.loads(Path(json_file).read_text(encoding="utf-8"))
    total = len(posts)
    print(f"Reddit Comment Poster  ({total} comments)\n")

    posted, failed = 0, 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=CHROME_PATH,
            headless=False,
            slow_mo=50,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        Stealth().apply_stealth_sync(page)

        print("Logging in ...")
        page.goto("https://www.reddit.com/login/", wait_until="domcontentloaded")
        human_pause(3, 4)
        page.locator('input[name="username"]').fill(username)
        page.locator('input[name="password"]').fill(password)
        page.get_by_role("button", name="Log In").click()
        human_pause(5, 7)
        print(f"[OK]  Login done. URL: {page.url[:60]}")

        for i, p in enumerate(posts, 1):
            print(f"\n{'-'*60}")
            print(f"  [{i}/{total}]")
            ok = post_comment(
                page,
                post_url     = p["permalink"],
                comment_text = p["suggested_comment"],
                title        = p["post_title"],
            )
            if ok:
                posted += 1
            else:
                failed += 1

            if i < total:
                delay = DELAY_BETWEEN_POSTS + random.randint(0, 15)
                print(f"  Waiting {delay}s before next comment ...")
                time.sleep(delay)

        browser.close()

    print(f"\n{'='*60}")
    print(f"  Done!  {posted} posted & verified   {failed} failed/unverified")


if __name__ == "__main__":
    main()
