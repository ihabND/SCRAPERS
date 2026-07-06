"""
Minimal IMDB Top 250 scraper -- title + year -> movies_minimal.json

Same idea as scrape_movies.py but flat: no functions, no self-healing,
minimal fields. Good for learning the Playwright basics step by step.

    pip install playwright beautifulsoup4
    playwright install chromium
    python minimal.py
"""

import json
import time

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # 1. Launch a real (headless) browser -- needed to pass IMDB's WAF challenge.
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(locale="en-US")
    page = context.new_page()

    # 2. Open the chart. This navigation solves the WAF and stores the token.
    print("Opening chart and solving WAF...")
    page.goto("https://www.imdb.com/chart/top/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("a.ipc-title-link-wrapper", state="attached", timeout=60000)

    # 3. Scroll to the bottom until all 250 rows have lazy-loaded.
    while len(page.query_selector_all("a.ipc-title-link-wrapper")) < 250:
        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        page.wait_for_timeout(400)

    # 4. Collect the movie links out of the chart HTML (dedupe, keep order).
    soup = BeautifulSoup(page.content(), "html.parser")
    links = []
    seen = set()
    for a in soup.find_all("a", {"class": "ipc-title-link-wrapper"}):
        href = a.get("href", "")
        if not href.startswith("/title/tt"):
            continue
        title_id = href.split("?", 1)[0]
        if title_id in seen:
            continue
        seen.add(title_id)
        links.append("https://www.imdb.com" + href)

    print(f"Collected {len(links)} links.")

    # 5. Fetch each movie page (fast path: reuses cookies + TLS, no rendering).
    results = []
    for i, url in enumerate(links, start=1):
        html = context.request.get(url, timeout=30000).text()

        # 6. Parse title + year from the JSON-LD block.
        tag = BeautifulSoup(html, "html.parser").find("script", {"type": "application/ld+json"})
        data = json.loads(tag.string) if tag else {}
        title = data.get("name")
        year = (data.get("datePublished") or "")[:4] or None

        results.append({"rank": i, "title": title, "year": year})
        print(f"[{i}/{len(links)}] {title} ({year})")

        # 7. Save after every movie so progress survives interruptions.
        with open("movies_minimal.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        time.sleep(0.5)

    browser.close()
    print(f"Done. Saved {len(results)} movies to movies_minimal.json")
