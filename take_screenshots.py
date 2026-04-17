from playwright.sync_api import sync_playwright
import time
import os

DOCS_DIR = "/Users/akritiiiy15/Documents"

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    # 1. Login Page Screenshot
    print("Navigating to Login Page...")
    page.goto("http://127.0.0.1:5003/login")
    time.sleep(1) # wait for animations if any
    page.screenshot(path=f"{DOCS_DIR}/site_screenshot_login.png", full_page=True)

    # 2. Registration Page Screenshot
    print("Navigating to Registration Page...")
    page.goto("http://127.0.0.1:5003/register")
    time.sleep(1)
    page.screenshot(path=f"{DOCS_DIR}/site_screenshot_register.png", full_page=True)

    # 3. Create an account to see the dashboard
    print("Registering test account...")
    page.fill('input[name="username"]', 'testuser')
    page.fill('input[name="email"]', 'testuser@example.com')
    page.fill('input[name="password"]', 'password123')
    # If there is a role field, we might need to select it, but we can just submit 
    # and hope it works if there's no mandatory role on register or it defaults.
    try:
        page.click('button[type="submit"]')
        time.sleep(2)
        
        # In case we need to log in after registration
        if "login" in page.url:
            page.fill('input[name="email"]', 'testuser@example.com')
            page.fill('input[name="password"]', 'password123')
            page.click('button[type="submit"]')
            time.sleep(2)
        
        # 4. Dashboard Screenshot
        print("Navigating to Dashboard...")
        page.goto("http://127.0.0.1:5003/dashboard")
        time.sleep(2) # wait for charts and data
        page.screenshot(path=f"{DOCS_DIR}/site_screenshot_dashboard.png", full_page=True)
        
        # 5. Members Page
        print("Navigating to Members...")
        page.goto("http://127.0.0.1:5003/members/")
        time.sleep(1)
        page.screenshot(path=f"{DOCS_DIR}/site_screenshot_members.png", full_page=True)

        print("Screenshots completed successfully!")

    except Exception as e:
        print(f"Encountered an issue but continuing... {e}")

    finally:
        browser.close()

with sync_playwright() as playwright:
    run(playwright)
