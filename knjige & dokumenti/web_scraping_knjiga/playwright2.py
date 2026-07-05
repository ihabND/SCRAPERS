from playwright.sync_api import sync_playwright

BASE_URL = "https://qalb-blog.fly.dev/"

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=False,
                                         slow_mo=250)
    page = browser.new_page()
    page.goto(BASE_URL)
    print(page.title())
    page.locator("[class='theme-toggle']").click()
    page.locator("[class='theme-toggle']").click()
    page.locator("[class='theme-toggle']").click()
    page.locator("[class='theme-toggle']").click()
    page.locator("[class='theme-toggle']").click()
    page.locator("[class='theme-toggle']").click()
    browser.close()

