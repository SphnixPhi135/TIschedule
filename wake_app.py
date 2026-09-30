from playwright.sync_api import sync_playwright

def wake_up():
    with sync_playwright() as p:
        # Launch a hidden Chrome browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Navigating to Tumor Immunology schedule...")
        page.goto("https://cnbxbsxr7ezak5cyfe4c5e.streamlit.app/", wait_until="domcontentloaded")

        # Scan the page for the specific Streamlit wake-up button
        button = page.locator("button:has-text('Yes, get this app back up!')")
        
        try:
            # Wait up to 5 seconds to see if the button appears
            if button.is_visible(timeout=5000):
                print("Sleep screen detected. Clicking the wake-up button...")
                button.click()
                page.wait_for_timeout(10000)  # Give Streamlit 10 seconds to process the wake command
                print("App successfully woken up!")
            else:
                print("App is already awake and running normally.")
        except Exception as e:
            print(f"App is awake. (No button found: {e})")
            
        browser.close()

if __name__ == "__main__":
    wake_up()
