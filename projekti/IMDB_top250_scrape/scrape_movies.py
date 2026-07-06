"""
================================================================================
IMDB Top 250 scraper  --  title + year  ->  movies.json
================================================================================

WHAT THIS SCRIPT DOES (high-level flow, in the order it runs)
--------------------------------------------------------------------------------
1. LAUNCH BROWSER
   Start one headless Chromium via Playwright. We need a *real* browser because
   IMDB sits behind an AWS WAF (Web Application Firewall) "JavaScript challenge".
   A plain HTTP client like `requests` can't get past it (see WHY below).

2. SOLVE THE WAF CHALLENGE + COLLECT LINKS
   Navigate to the Top 250 chart page. The WAF first serves a stub page whose
   JavaScript runs a proof-of-work puzzle; when it passes, the browser is given
   an `aws-waf-token` cookie and the real chart loads. The chart lazy-loads its
   rows (only ~25 exist in the DOM at first), so we scroll to the bottom until
   all 250 movie links are present, then read them out of the HTML.

3. FETCH EACH MOVIE PAGE (fast path)
   For all 250 links we call `context.request.get()` -- Playwright's own HTTP
   client. Crucially it reuses the browser's cookies (incl. `aws-waf-token`) AND
   the browser's TLS fingerprint, so it clears the WAF *without* rendering each
   page. That makes it much faster than navigating a full page 250 times.

4. PARSE title + year
   Each movie page embeds its data server-side as JSON-LD inside a
   <script type="application/ld+json"> tag. We grab that tag with BeautifulSoup
   and read `name` (title) and `datePublished` (year) out of the JSON. JSON-LD
   is far more stable than scraping CSS classes, which IMDB changes often.

5. SELF-HEAL IF RE-CHALLENGED
   If the WAF ever re-challenges a request (token expired), we fall back to a
   full browser navigation to re-mint the token, then carry on.

6. SAVE INCREMENTALLY
   After every movie we rewrite movies.json, so if the run is interrupted or
   blocked partway, whatever we've scraped so far is already on disk.

WHY A BROWSER AND NOT `requests`?
--------------------------------------------------------------------------------
The AWS WAF blocks bots two ways: (a) it requires JavaScript execution to solve
the challenge and obtain the `aws-waf-token` cookie, and (b) it fingerprints the
TLS handshake -- so even *with* the cookie, plain `requests` gets a
"405 Human Verification" response because its TLS signature isn't a browser's.
Playwright is a real browser engine, so it satisfies both.

HOW TO RUN
--------------------------------------------------------------------------------
    pip install playwright beautifulsoup4
    playwright install chromium

    python scrape_movies.py        # scrape all 250 movies
    python scrape_movies.py 20     # scrape only the first 20 (handy for testing)
================================================================================
"""

import json      # to read the JSON-LD blob and to write movies.json
import random    # to jitter the delay between requests (look less bot-like)
import re        # to parse the ISO-8601 runtime (e.g. "PT2H22M")
import sys       # to read an optional "limit" argument from the command line
import time      # to sleep between requests

from bs4 import BeautifulSoup          # HTML parsing (find the JSON-LD tag)
from playwright.sync_api import sync_playwright   # drives headless Chromium

# --- Constants ---------------------------------------------------------------

URL_TOP = "https://www.imdb.com/chart/top/"   # the Top 250 chart page
OUTPUT_FILE = "movies.json"                    # where results are saved

# CSS selector for the chart's movie-title links. Each row's title is an
# <a class="ipc-title-link-wrapper" href="/title/tt...."> element.
LINK_SELECTOR = "a.ipc-title-link-wrapper"

# CSS selector for the JSON-LD data block present on every movie detail page.
LDJSON_SELECTOR = 'script[type="application/ld+json"]'

# IMDB hrefs already start with "/title/...", so we only prepend the origin
# to turn them into absolute URLs.
IMDB_ORIGIN = "https://www.imdb.com"

# A real Chrome User-Agent string. Cosmetic on its own (it does NOT defeat the
# WAF), but we keep the browser and its HTTP client presenting consistently.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# How many movies we expect in the chart (used to know when scrolling is done).
EXPECTED_COUNT = 250


# --- Chart page: solve WAF, scroll, collect the 250 links --------------------

def _scroll_until_loaded(page, target=EXPECTED_COUNT, max_scrolls=40):
    """Scroll to the bottom repeatedly until `target` chart links exist.

    The chart lazy-loads rows as you scroll, so only ~25 links are in the DOM
    initially. We keep scrolling (up to a safety cap) until at least `target`
    links are present, then stop.
    """
    for _ in range(max_scrolls):
        # Count how many title links are currently in the DOM.
        count = len(page.query_selector_all(LINK_SELECTOR))
        if count >= target:
            break  # all rows loaded -> done scrolling
        # Jump to the current bottom of the page to trigger the next lazy load.
        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        # Give the newly-triggered rows a moment to fetch and render.
        page.wait_for_timeout(400)


def get_all_links(soup):
    """Pull the unique, absolute movie URLs out of the chart HTML, in order.

    We dedupe on the "/title/ttNNNNNNN" path because the chart sometimes has a
    stray extra anchor with the same class, and we want exactly 250 movies.
    """
    links = []
    seen = set()
    for a in soup.find_all("a", {"class": "ipc-title-link-wrapper"}):
        href = a.get("href", "")
        # Skip anything that isn't a real "/title/tt..." movie link.
        if not href.startswith("/title/tt"):
            continue
        # The stable identifier is the "/title/ttNNNNNNN" prefix (before "?ref=").
        title_id = href.split("?", 1)[0].rstrip("/")
        if title_id in seen:
            continue  # already have this movie -> skip the duplicate anchor
        seen.add(title_id)
        links.append(IMDB_ORIGIN + href)  # make it an absolute URL
    return links


def collect_links(context):
    """Open the chart in a real page (solving the WAF) and return the 250 links.

    This first navigation is what triggers and solves the WAF challenge; the
    resulting `aws-waf-token` cookie is stored on the browser `context` and is
    then automatically reused by every later `context.request.get()` call.
    """
    page = context.new_page()
    try:
        # Load the chart. "domcontentloaded" returns once the HTML is parsed;
        # the WAF challenge JS then runs and swaps in the real chart.
        page.goto(URL_TOP, wait_until="domcontentloaded", timeout=60000)
        # Wait until the real movie links exist -> proof the WAF has resolved.
        page.wait_for_selector(LINK_SELECTOR, state="attached", timeout=60000)
        # Lazy-load the rest of the rows by scrolling.
        _scroll_until_loaded(page)
        # Hand the fully-loaded HTML to BeautifulSoup and extract the links.
        return get_all_links(BeautifulSoup(page.content(), "html.parser"))
    finally:
        page.close()  # always close the page, even if something above throws


# --- Movie pages: fetch + parse ----------------------------------------------

def is_real_page(status, html):
    """Return True if this is a real movie page, not a WAF challenge stub.

    A genuine page is HTTP 200, contains no "awswaf" markers, and has the
    JSON-LD data block we need.
    """
    return status == 200 and "awswaf" not in html and "application/ld+json" in html


def _as_list(value):
    """Normalize a JSON-LD field that may be a single item or a list.

    schema.org allows a field like `director` to be either one object or a
    list of objects. This always hands back a list so callers can iterate.
    """
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _names(value):
    """Given a JSON-LD person/thing (or list of them), return their names.

    Used for actor / director / creator, which are lists of {"name": ...}
    objects. Entries without a name (e.g. Organizations) are skipped.
    """
    return [item["name"] for item in _as_list(value) if item.get("name")]


def _iso_duration_to_minutes(iso):
    """Convert an ISO-8601 duration like 'PT2H22M' into total minutes (142).

    Returns None if the value is missing or unparseable.
    """
    if not iso:
        return None
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not match:
        return None
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 60 + minutes + round(seconds / 60)


def parse_movie(html):
    """Extract every readily-available field from a movie page's JSON-LD.

    Returns a dict of the movie's data, or an empty dict if the JSON-LD block
    is missing so the caller can still record the row without crashing.
    """
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", {"type": "application/ld+json"})
    if tag is None:
        return {}
    data = json.loads(tag.string)   # parse the JSON-LD blob into a dict

    # datePublished is like "1994-10-14"; the year is its first 4 digits.
    date_published = data.get("datePublished") or ""
    year = date_published[:4] if date_published[:4].isdigit() else None

    # aggregateRating is a nested object holding the score and vote count.
    rating = data.get("aggregateRating") or {}

    # keywords is a single comma-separated string; split it into a clean list.
    keywords_raw = data.get("keywords") or ""
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

    # trailer is a nested object; we just keep its watch URL if present.
    trailer = data.get("trailer") or {}

    return {
        "title": data.get("name"),                     # primary title
        "alternate_title": data.get("alternateName"),  # localized/alt title
        "year": year,
        "date_published": date_published or None,
        "content_rating": data.get("contentRating"),   # e.g. "R", "PG-13"
        "genres": _as_list(data.get("genre")),          # list of genre strings
        "rating": rating.get("ratingValue"),            # e.g. 9.3
        "rating_count": rating.get("ratingCount"),      # number of votes
        "runtime_minutes": _iso_duration_to_minutes(data.get("duration")),
        "directors": _names(data.get("director")),
        "writers": _names(data.get("creator")),         # creator = writers/orgs
        "actors": _names(data.get("actor")),            # top-billed cast
        "keywords": keywords,
        "description": data.get("description"),         # short plot summary
        "poster": data.get("image"),                    # poster image URL
        "trailer": trailer.get("url"),                  # trailer watch URL
        "imdb_url": data.get("url"),                    # canonical movie URL
    }


def refresh_token(context, url):
    """Fall back to a full browser navigation to re-mint the WAF token.

    Used when a fast `context.request.get()` gets challenged. Navigating a real
    page re-solves the WAF; the fresh cookie is stored back on the context, so
    subsequent fast requests work again. Returns this page's HTML.
    """
    page = context.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # Wait for the JSON-LD block -> the real page (not the challenge) loaded.
        page.wait_for_selector(LDJSON_SELECTOR, state="attached", timeout=60000)
        return page.content()
    finally:
        page.close()


def fetch(context, url):
    """Fetch one movie page's HTML, using the fast path with a browser fallback.

    Fast path: `context.request.get()` reuses the browser's cookies + TLS
    fingerprint, so it clears the WAF without rendering. If that comes back
    challenged, we re-mint the token via a full navigation.
    """
    resp = context.request.get(url, timeout=30000)   # fast, no rendering
    html = resp.text()
    if is_real_page(resp.status, html):
        return html
    # Token expired / re-challenged -> re-solve via a real page navigation.
    print("    challenge hit, refreshing token via browser...")
    return refresh_token(context, url)


# --- Persistence -------------------------------------------------------------

def save(results):
    """Write the results list to movies.json (called after every movie)."""
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        # ensure_ascii=False keeps non-English titles readable; indent=2 = pretty.
        json.dump(results, f, ensure_ascii=False, indent=2)


# --- Entry point -------------------------------------------------------------

def main():
    # Optional command-line arg: scrape only the first N movies (for testing).
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    # `sync_playwright()` context manager starts/stops the Playwright driver.
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)   # no visible window
        # One context = one cookie jar. The WAF token lives here and is shared
        # by every page and every context.request call we make below.
        context = browser.new_context(user_agent=USER_AGENT, locale="en-US")
        try:
            # STEP 1+2: solve the WAF and read the 250 links off the chart.
            print("Solving WAF challenge and collecting links...")
            links = collect_links(context)
            print(f"Collected {len(links)} links.")
            if limit:
                links = links[:limit]   # trim to the requested count if testing

            results = []
            # STEP 3-6: for each movie, fetch -> parse -> record -> save.
            for i, url in enumerate(links, start=1):
                html = fetch(context, url)          # fast path (+ browser fallback)
                movie = parse_movie(html)           # extract all JSON-LD fields
                # "rank" is the chart position; then spread in every parsed field.
                results.append({"rank": i, **movie})
                print(f"[{i}/{len(links)}] {movie.get('title')} "
                      f"({movie.get('year')})  rating={movie.get('rating')}")

                save(results)   # write after every movie -> crash-safe progress
                # Polite, randomized pause so we don't hammer IMDB / trip the WAF.
                time.sleep(random.uniform(0.3, 0.9))

            print(f"\nDone. Saved {len(results)} movies to {OUTPUT_FILE}")
        finally:
            browser.close()   # always shut the browser down cleanly


# Standard Python guard: only run main() when executed directly, not on import.
if __name__ == "__main__":
    main()
