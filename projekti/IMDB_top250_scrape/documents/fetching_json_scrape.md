# Scraping with JSON-LD instead of selecting from HTML

A practical guide, using the IMDB scraper (`minimal.py`) as the running example.

---

## The line, piece by piece

```python
tag = BeautifulSoup(html, "html.parser").find("script", {"type": "application/ld+json"})
```

This does two separate things at once:

1. **`BeautifulSoup(html, "html.parser")`** — takes the raw HTML string (the whole
   movie page you fetched) and parses it into a navigable tree of Python objects.
   `"html.parser"` is just *which* parser engine to use (Python's built-in one;
   alternatives are `lxml`, `html5lib`).

2. **`.find("script", {"type": "application/ld+json"})`** — searches that tree for the
   **first** `<script>` tag whose `type` attribute equals `application/ld+json`. The dict
   `{"type": "application/ld+json"}` is an attribute filter: "find a `<script>` where the
   attribute `type` has this value."

So `tag` becomes that one `<script>` element (or `None` if it doesn't exist — which is why
the next line guards with `if tag else {}`).

Then the actual extraction:

```python
data = json.loads(tag.string) if tag else {}
```

- `tag.string` is the **text content inside** the `<script>...</script>` tag — a big JSON string.
- `json.loads(...)` turns that string into a Python dict you can `.get("name")` from.

---

## What is JSON-LD?

`application/ld+json` is **JSON-LD** (JSON for Linking Data) — a structured-data block many
sites embed for Google / SEO / rich search results. It follows the
[schema.org](https://schema.org) vocabulary, so a movie is a `Movie`, a product is a
`Product`, an article is an `Article`, each with predictable fields.

IMDB conveniently stuffs the movie's title, year, rating, genre, director, etc. into it.
That's why scraping it is **much more reliable** than hunting for CSS classes.

### Why prefer JSON-LD over CSS/HTML selection

| HTML/CSS selection | JSON-LD |
| --- | --- |
| Class names like `ipc-title-link-wrapper` change on every redesign | Schema.org field names (`name`, `datePublished`) are stable for years |
| One selector per field, easy to break | One parse gives you every field at once |
| You reverse-engineer the layout | The site hands you clean, typed data |
| Whitespace / nested tags to clean up | Already-typed strings, numbers, arrays |

**Rule of thumb:** if the page has a JSON-LD block with the fields you need, use it.
Fall back to CSS selectors only for fields JSON-LD doesn't expose.

---

## Finding it manually in the browser

On any IMDB movie page (e.g. `https://www.imdb.com/title/tt0111161/`):

### Method A — DevTools Elements (the rendered DOM)
1. Press **F12** -> **Elements** tab.
2. **Ctrl+F** inside the inspector, search for: `application/ld+json`
3. You land on a `<script type="application/ld+json">` element. Expand it to see the JSON.

### Method B — View source (what your scraper actually sees) ← preferred
1. Press **Ctrl+U**, or go to `view-source:https://www.imdb.com/title/tt0111161/`
2. **Ctrl+F** for `application/ld+json`.

**Why the distinction matters:** the Python code parses the **raw HTML the server sends**
(`context.request.get(url).text()`), *not* the JavaScript-rendered DOM. The Elements tab
shows the DOM *after* JS runs, which can differ. For JSON-LD on IMDB the two match (it ships
in the initial HTML), but on JS-heavy sites always confirm with **view-source** so you're
looking at the same bytes your scraper receives.

### Make the JSON readable
- Select the script node in DevTools, then in the **Console** run:
  ```js
  JSON.parse($0.textContent)   // $0 = currently selected element
  ```
- Or copy the text into any JSON formatter / prettifier.

---

## Reading fields out of the JSON

Once parsed into `data`, it's a normal Python dict:

```python
data = json.loads(tag.string)

title    = data.get("name")
year     = (data.get("datePublished") or "")[:4] or None
rating   = data.get("aggregateRating", {}).get("ratingValue")
votes    = data.get("aggregateRating", {}).get("ratingCount")
genres   = data.get("genre")                 # str or list depending on page
duration = data.get("duration")              # ISO 8601, e.g. "PT2H22M"
director = data.get("director")              # dict or list of {name, url}
poster   = data.get("image")
plot     = data.get("description")
```

**Defensive habits:**
- Always use `.get(...)` (not `data["x"]`) — fields vary per page and missing keys shouldn't crash.
- A field can be a **single object OR a list** (e.g. `director`). Normalize:
  ```python
  def as_list(x):
      if x is None:
          return []
      return x if isinstance(x, list) else [x]

  directors = [d.get("name") for d in as_list(data.get("director"))]
  ```
- `duration` is ISO-8601 (`PT2H22M`). Parse with a regex or `isodate` if you need minutes.

---

## Dumping the full JSON-LD to inspect everything a page offers

Drop this in to see every field IMDB exposes for one movie:

```python
import json
from bs4 import BeautifulSoup

html = context.request.get("https://www.imdb.com/title/tt0111161/", timeout=30000).text()
tag  = BeautifulSoup(html, "html.parser").find("script", {"type": "application/ld+json"})
data = json.loads(tag.string)

with open("one_movie_ld.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(json.dumps(data, ensure_ascii=False, indent=2))   # or just print it
```

Open `one_movie_ld.json` and you'll see rating, genre, actors, duration, content rating,
trailer, etc. — pick whatever fields you want to add to your scraper.

---

## Handling multiple / missing JSON-LD blocks

- Some pages have **several** JSON-LD scripts (one for the site, one for a breadcrumb, one
  for the item). Grab them all and pick by `@type`:
  ```python
  scripts = BeautifulSoup(html, "html.parser").find_all("script", {"type": "application/ld+json"})
  blocks = []
  for s in scripts:
      try:
          obj = json.loads(s.string)
      except (TypeError, json.JSONDecodeError):
          continue
      # a block can itself be a list
      blocks.extend(obj if isinstance(obj, list) else [obj])

  movie = next((b for b in blocks if b.get("@type") == "Movie"), None)
  ```
- If `json.loads` fails, the block may contain stray characters or be split — wrap in
  `try/except json.JSONDecodeError` and skip.
- If there's **no** JSON-LD at all, look for other structured data before falling back to CSS:
  - `<script type="application/json">` (e.g. Next.js `__NEXT_DATA__`, Nuxt, Redux state)
  - `<meta property="og:...">` Open Graph tags (`og:title`, `og:image`, ...)
  - Microdata attributes: `itemscope` / `itemprop`

---

## Going one level deeper: skip HTML entirely, hit the JSON API

JSON-LD lives *inside* HTML. Often a site also has a **JSON endpoint** the page calls in the
background — the cleanest source of all. To find it:

1. Open **DevTools -> Network** tab, filter by **Fetch/XHR**.
2. Reload the page and watch the requests.
3. Look for responses that return JSON (click one -> **Preview** / **Response**).
4. Copy the request URL and headers; replay it directly with `requests` / `httpx` /
   Playwright's `context.request.get(...)`.

This avoids parsing HTML altogether — you request JSON and read it straight. Caveats:

- These endpoints are often **undocumented and unstable** (can change without notice).
- May require headers/cookies/tokens the page sets first (which is why `minimal.py` visits
  the chart page once to solve the WAF and store the token before making direct requests).
- Respect `robots.txt`, rate limits, and Terms of Service.

**Data-source preference, best to worst:**
1. Official/public **API** (if one exists) — most stable, intended for this.
2. Background **JSON/XHR endpoint** the page itself calls.
3. **JSON-LD** / embedded JSON in the HTML.
4. **CSS/HTML** selectors — last resort, most fragile.

---

## TL;DR

- `.find("script", {"type": "application/ld+json"})` grabs the one structured-data script;
  `json.loads(tag.string)` turns its contents into a dict.
- JSON-LD is stable schema.org data — prefer it over brittle CSS class selectors.
- Inspect it via **view-source** (matches what your scraper sees) rather than only the
  Elements tab (post-JS DOM).
- Always `.get(...)`, normalize object-or-list fields, guard `json.loads` with try/except.
- If you can find a direct JSON/XHR endpoint, that's even cleaner than parsing HTML at all.
