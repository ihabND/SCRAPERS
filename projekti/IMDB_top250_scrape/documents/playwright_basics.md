# Playwright Basics (Python) — A Learning Guide

A hands-on cheat sheet for the **sync** Playwright API, built around your
`minimal.py` IMDB scraper. Read it top to bottom the first time; after that
use it as a reference.

> **Sync vs Async:** Playwright has two APIs. `sync_playwright` (blocking, no
> `await`) is the easy one to learn — that's what this guide uses. There's also
> `async_playwright` for `asyncio`. Everything here maps 1:1 to async by adding
> `await` and `async def`.

---

## 0. Setup

```bash
pip install playwright beautifulsoup4
playwright install chromium      # downloads the browser binary (one-time)
```

`playwright install` downloads a bundled browser — it does **not** use your
system Chrome. You can also `playwright install firefox webkit`.

---

## 1. The three core objects: Browser → Context → Page

Almost everything you do starts the same way. This is a nested hierarchy:

```
Browser        # the running Chromium process
 └─ Context    # an isolated session: its own cookies, cache, storage
     └─ Page   # a single tab
```

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)   # 1. process
    context = browser.new_context()              # 2. isolated session (cookie jar)
    page = context.new_page()                    # 3. a tab

    page.goto("https://example.com")
    print(page.title())

    browser.close()
```

**Why the layers matter:**
- **Context = one cookie jar.** In your scraper the `aws-waf-token` cookie the
  WAF hands out lives on the *context*, which is why every later
  `context.request.get()` call is already authenticated. Make a second context
  and it starts logged out / cookieless — like an incognito window.
- **Page = one tab.** You can open many pages in one context (they share
  cookies). You rarely need more than one to start.

The `with sync_playwright() as p:` block starts and stops the Playwright driver
for you. Always work inside it.

---

## 2. Launch options you'll actually use

```python
browser = p.chromium.launch(
    headless=False,     # False = watch a real window open (great for learning/debugging)
    slow_mo=500,        # add 500ms between actions so you can see what happens
)
```

```python
context = browser.new_context(
    locale="en-US",                       # language/region
    user_agent="Mozilla/5.0 ...",         # pretend to be a specific browser
    viewport={"width": 1280, "height": 800},
)
```

> **Tip while learning:** run with `headless=False, slow_mo=500` so you can
> literally watch the scroll and navigation happen. Switch back to
> `headless=True` for speed once it works.

---

## 3. Navigating: `goto` and wait strategies

```python
page.goto("https://www.imdb.com/chart/top/",
          wait_until="domcontentloaded",   # when to consider the load "done"
          timeout=60000)                   # give up after 60s (ms!)
```

`wait_until` options — pick based on how the page loads:

| Value                | Returns when…                                    | Use for |
|----------------------|--------------------------------------------------|---------|
| `"commit"`           | first bytes received                             | fastest, rarely enough |
| `"domcontentloaded"` | HTML parsed (no images/subframes)                | JS-driven pages (your IMDB case) |
| `"load"`             | the `load` event (images etc. done)              | simple static pages |
| `"networkidle"`      | no network activity for 500ms                    | SPAs; can be flaky, avoid if you can |

**Timeouts are in milliseconds.** `60000` = 60 seconds. This trips everyone up
once.

In your scraper `"domcontentloaded"` is right: IMDB serves a stub page, then
JavaScript runs the WAF challenge and swaps in the real chart. You don't wait
for the *load* event — you wait for a specific element to appear (next section).

---

## 4. The golden rule: wait for elements, not for time

The #1 beginner mistake is `time.sleep(3)` hoping content loaded. Instead, wait
for the thing you actually need:

```python
# Wait until at least one chart link is attached to the DOM.
page.wait_for_selector("a.ipc-title-link-wrapper",
                       state="attached",
                       timeout=60000)
```

This line is doing real work in your scraper: it blocks until the WAF challenge
resolves and the real chart links exist. That's your proof the page is ready.

`state=` options:

| State        | Means |
|--------------|-------|
| `"attached"` | element is in the DOM (may be invisible) |
| `"visible"`  | in the DOM **and** visible (default) |
| `"hidden"`   | not visible / removed |
| `"detached"` | gone from the DOM |

---

## 5. Selecting elements

Playwright selectors accept CSS by default. Two families of methods:

### `query_selector` / `query_selector_all` — snapshot, returns now

```python
# One element (or None):
el = page.query_selector("a.ipc-title-link-wrapper")

# All matching elements, as a list (empty list if none):
links = page.query_selector_all("a.ipc-title-link-wrapper")
count = len(links)          # how you count rows in minimal.py
```

These return immediately with whatever exists *right now* — no waiting. That's
exactly why the scroll loop uses `query_selector_all`: it wants an instant count
each pass, not to wait.

### `locator` — the modern, auto-waiting way

```python
links = page.locator("a.ipc-title-link-wrapper")
print(links.count())                 # how many match
print(links.first.inner_text())      # auto-waits for it to be ready
links.nth(2).click()                 # third match
```

`locator` is lazy (it re-queries when used) and **auto-waits** — prefer it for
clicking/reading. Use `query_selector_all` when you just want a raw snapshot
count like the scroll loop does.

### Handy selector syntaxes

```python
page.locator("text=Sign in")             # by visible text
page.get_by_role("button", name="Next")  # by ARIA role (robust)
page.get_by_text("Top 250")              # by text
page.get_by_placeholder("Search")        # form fields
page.locator("#id .class > a")           # plain CSS
```

---

## 6. Reading data off the page

```python
page.title()                       # <title> text
page.url                           # current URL
page.content()                     # the full rendered HTML (what you hand to BeautifulSoup)

el = page.query_selector("h1")
el.inner_text()                    # visible text
el.text_content()                  # all text incl. hidden
el.get_attribute("href")           # an attribute
el.inner_html()                    # inner HTML
```

Your scraper uses `page.content()` to get the fully-rendered HTML *after*
scrolling, then parses it with BeautifulSoup:

```python
soup = BeautifulSoup(page.content(), "html.parser")
for a in soup.find_all("a", {"class": "ipc-title-link-wrapper"}):
    href = a.get("href", "")
    ...
```

> **When to use BeautifulSoup vs Playwright selectors?** Both work. Playwright's
> `locator` reads live from the browser; BeautifulSoup parses a static HTML
> string. For bulk extraction from a page you've finished loading, grabbing
> `page.content()` once and using BeautifulSoup (as you do) is clean and fast.

---

## 7. Running JavaScript in the page: `evaluate`

`page.evaluate()` runs JS *inside the browser* and returns the result to Python.

```python
# Scroll to the bottom to trigger lazy-loading (straight from minimal.py):
page.evaluate("window.scrollBy(0, document.body.scrollHeight)")

# Return a value back to Python:
height = page.evaluate("document.body.scrollHeight")

# Pass an argument in:
page.evaluate("(n) => window.scrollBy(0, n)", 1000)
```

This is your escape hatch when a built-in method doesn't cover what you need —
like triggering IMDB's infinite scroll.

---

## 8. The scroll-until-loaded pattern

Lazy-loaded lists (infinite scroll) only put a few rows in the DOM at first.
Keep scrolling until you have enough. Your scraper:

```python
while len(page.query_selector_all("a.ipc-title-link-wrapper")) < 250:
    page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
    page.wait_for_timeout(400)     # let the new rows fetch + render
```

Notes:
- `page.wait_for_timeout(400)` is Playwright's sleep (ms). It's fine *here*
  because you're deliberately pacing lazy-load network calls — this is the one
  legitimate use of a fixed wait.
- **Always cap the loop in real code.** The above trusts 250 exists. A safer
  version adds a max-iterations guard so a site change can't loop forever:

```python
for _ in range(40):                                  # safety cap
    if len(page.query_selector_all("a.ipc-title-link-wrapper")) >= 250:
        break
    page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
    page.wait_for_timeout(400)
```

(That's exactly what the original `scrape_movies.py` does in
`_scroll_until_loaded`.)

---

## 9. Interactions (not used in the scraper, but core skills)

```python
page.click("text=Sign in")
page.fill("#username", "elvir")           # clears then types
page.type("#search", "imdb", delay=100)   # keystroke by keystroke
page.press("#search", "Enter")
page.check("#agree")                       # checkbox
page.select_option("#country", "US")       # dropdown
page.hover(".menu")
page.set_input_files("#upload", "poster.png")
```

All of these **auto-wait** for the element to be actionable (visible, enabled,
stable) before acting — so you usually don't need an explicit
`wait_for_selector` before a click.

---

## 10. The fast path: `context.request` (HTTP without rendering)

This is the clever bit in your scraper. Once the browser context holds the WAF
cookie, you can make plain HTTP requests that **reuse those cookies and the
browser's TLS fingerprint** — no page rendering, much faster:

```python
resp = context.request.get(url, timeout=30000)
resp.status          # 200
resp.text()          # body as string
resp.json()          # parsed JSON (for APIs)
resp.headers         # dict
```

```python
# minimal.py: fetch 250 pages fast, without opening 250 tabs.
html = context.request.get(url, timeout=30000).text()
```

Why this works when plain `requests` fails: the WAF checks both a JS-solved
cookie **and** the TLS handshake fingerprint. `context.request` runs through the
browser stack, so it passes both. `requests` has neither.

Use `context.request` for bulk fetching once you're past a challenge; use full
`page.goto()` navigation only when you need JavaScript to actually run.

---

## 11. Cookies, storage, and reusing sessions

```python
cookies = context.cookies()                     # read all cookies
context.add_cookies([{"name": "x", "value": "y", "url": "https://imdb.com"}])

# Save a whole logged-in session to disk...
context.storage_state(path="state.json")
# ...and reuse it next run (skip login / re-solving a challenge):
context = browser.new_context(storage_state="state.json")
```

This is how you'd avoid re-solving the WAF on every run — persist the state,
reload it next time.

---

## 12. Debugging toolkit

```python
page.screenshot(path="debug.png", full_page=True)   # see what the bot sees
print(page.content())                               # dump current HTML
page.pause()                                        # opens Playwright Inspector (headed)
```

- **Run headed:** `launch(headless=False, slow_mo=500)` and watch it live.
- **`page.screenshot`** is your best friend when a selector "doesn't exist" —
  usually the page looks different than you assume (a cookie banner, a
  challenge, wrong region).
- **Trace viewer** (advanced, records everything for replay):

```python
context.tracing.start(screenshots=True, snapshots=True)
# ... do stuff ...
context.tracing.stop(path="trace.zip")
# then: playwright show-trace trace.zip
```

---

## 13. Errors and timeouts

```python
from playwright.sync_api import TimeoutError as PlaywrightTimeout

try:
    page.wait_for_selector(".missing", timeout=5000)
except PlaywrightTimeout:
    print("Element never showed up — take a screenshot and investigate")
```

Set a default so you don't repeat `timeout=` everywhere:

```python
page.set_default_timeout(30000)          # applies to actions & waits
page.set_default_navigation_timeout(60000)   # goto specifically
```

---

## 14. Always clean up

```python
with sync_playwright() as p:
    browser = p.chromium.launch()
    try:
        # ... your work ...
    finally:
        browser.close()      # close even if something above throws
```

Your `scrape_movies.py` wraps the work in `try/finally: browser.close()` for
exactly this reason. `minimal.py` skips it for brevity, but `try/finally` is the
right habit — an unclosed browser leaks a background process.

---

## 15. Putting it together — the minimal scraper, annotated

The whole flow you now understand, in order:

```python
with sync_playwright() as p:                       # §1  start driver
    browser = p.chromium.launch(headless=True)     # §1  process
    context = browser.new_context(locale="en-US")  # §1  cookie jar
    page = context.new_page()                      # §1  tab

    page.goto(URL, wait_until="domcontentloaded")  # §3  navigate (solves WAF)
    page.wait_for_selector("a.ipc-title-link-wrapper", state="attached")  # §4 ready

    while len(page.query_selector_all(SEL)) < 250: # §8  scroll to lazy-load all
        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")   # §7
        page.wait_for_timeout(400)

    soup = BeautifulSoup(page.content(), ...)      # §6  grab rendered HTML
    links = [...]                                  #     extract + dedupe

    for url in links:
        html = context.request.get(url).text()     # §10 fast fetch, reuse cookies
        data = json.loads(...)                      #     parse JSON-LD
        # save incrementally

    browser.close()                                 # §14 clean up
```

---

## 16. Quick reference card

| Task | Call |
|------|------|
| Start | `with sync_playwright() as p:` |
| Launch | `p.chromium.launch(headless=True)` |
| New session | `browser.new_context()` |
| New tab | `context.new_page()` |
| Go to URL | `page.goto(url, wait_until="domcontentloaded")` |
| Wait for element | `page.wait_for_selector(sel, state="attached")` |
| Count elements | `len(page.query_selector_all(sel))` |
| One element | `page.query_selector(sel)` |
| Auto-waiting handle | `page.locator(sel)` |
| Get text | `el.inner_text()` |
| Get attribute | `el.get_attribute("href")` |
| Rendered HTML | `page.content()` |
| Run JS | `page.evaluate("...")` |
| Click / type | `page.click(sel)` / `page.fill(sel, text)` |
| Fast HTTP (reuse cookies) | `context.request.get(url).text()` |
| Screenshot | `page.screenshot(path="x.png")` |
| Sleep (ms) | `page.wait_for_timeout(400)` |
| Close | `browser.close()` |

---

### Next steps to practice
1. Run `minimal.py` with `headless=False, slow_mo=300` and watch it work.
2. Add a `page.screenshot("chart.png")` right after the scroll loop.
3. Replace `query_selector_all` with a `locator` and use `.count()`.
4. Try `context.storage_state()` to save the WAF session and reuse it.
5. Graduate to `scrape_movies.py` to see the same ideas wrapped in functions,
   with error handling and self-healing.
