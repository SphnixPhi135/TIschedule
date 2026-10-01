from playwright.sync_api import sync_playwright

def wake_up():
    with sync_playwright() as p:
        # Launch a hidden Chrome browser
        browser = p.chromium.launch(headless=True)
        
        # Add a real User-Agent so Streamlit treats this as a human visit
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Navigating to the schedule app...")
        page.goto("https://cnbxbsxr7ezak5cyfe4c5e.streamlit.app/", wait_until="domcontentloaded")

        # Wait 5 full seconds to guarantee the page (or sleep screen) completely loads
        page.wait_for_timeout(5000)

        # Scan the page for the specific Streamlit wake-up button
        button = page.locator("button:has-text('Yes, get this app back up!')")
        
        if button.is_visible():
            print("Sleep screen detected. Clicking the wake-up button...")
            button.click()
            # Wait 15 seconds to give Streamlit time to actually reboot the server
            page.wait_for_timeout(15000)  
            print("App successfully woken up!")
        else:
            print("App is already awake and running normally.")
            # Stay on the page for 10 seconds anyway so Streamlit logs the WebSocket heartbeat
            page.wait_for_timeout(10000)
            
        browser.close()

if __name__ == "__main__":
    wake_up()
