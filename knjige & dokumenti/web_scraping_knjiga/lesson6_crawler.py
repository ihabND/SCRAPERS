import requests
from bs4 import BeautifulSoup
import re
from collections import deque
import time

BASE_URL = "https://en.wikipedia.org/wiki/Cat"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "en",
}

exp = re.compile(
    r"^(?:https?:)?//en\.wikipedia\.org/wiki/(?!.*_\([^)]*\)$)[^:#]+$"
)

def normalize(url):
    if url.startswith("//"):
        return "https:" + url
    return url

visited = set()
found_links = set()
queue = deque([BASE_URL])
visited.add(BASE_URL)

max_iterations = 500
iterations = 0

last_log_time = time.time()

while queue and iterations < max_iterations:
    url = queue.popleft()
    iterations += 1

    print(f"[{iterations}/500] Fetching: {url}")
    print(f"Queue size: {len(queue)} | Unique links: {len(found_links)}")

    try:
        response = requests.get(url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"ERROR fetching {url}: {e}")
        continue

    links = soup.find_all("a", href=exp)

    for link in links:
        href = normalize(link.get("href"))
        if not href:
            continue

        if href not in visited:
            visited.add(href)
            queue.append(href)

        found_links.add(href)

    # heartbeat every ~10 seconds if stuck on heavy pages
    if time.time() - last_log_time > 10:
        print(f"[HEARTBEAT] Still running... iterations={iterations}")
        last_log_time = time.time()

with open("links.txt", "w", encoding="utf-8") as f:
    for link in sorted(found_links):
        f.write(link + "\n")

print(f"DONE. Visited: {iterations}, Unique links: {len(found_links)}")