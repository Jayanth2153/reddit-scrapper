from playwright.sync_api import sync_playwright
import time

pages_to_capture = [
    ("http://localhost:8501", "ss_overview.png", None),
]

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)

    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:8501", timeout=30000)

    # Wait for Streamlit content to appear
    page.wait_for_selector("div.stApp", timeout=20000)
    time.sleep(8)

    page.screenshot(path="ss_overview.png", full_page=False)
    print("Overview captured")

    # Navigate to Accounts page via sidebar
    try:
        page.get_by_text("Accounts").first.click()
        time.sleep(4)
        page.screenshot(path="ss_accounts.png", full_page=False)
        print("Accounts captured")
    except Exception as e:
        print(f"Accounts nav failed: {e}")

    # Navigate to Comments page
    try:
        page.get_by_text("Comments").first.click()
        time.sleep(4)
        page.screenshot(path="ss_comments.png", full_page=False)
        print("Comments captured")
    except Exception as e:
        print(f"Comments nav failed: {e}")

    # Navigate to Run History page
    try:
        page.get_by_text("Run History").first.click()
        time.sleep(4)
        page.screenshot(path="ss_history.png", full_page=False)
        print("Run History captured")
    except Exception as e:
        print(f"History nav failed: {e}")

    browser.close()
    print("All done")
