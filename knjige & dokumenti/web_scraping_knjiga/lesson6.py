import requests
from bs4 import BeautifulSoup
import re

BASE_URL = "https://en.wikipedia.org/wiki/Cat"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "en",
}

response = requests.get(BASE_URL, headers=headers, timeout=30)
content = BeautifulSoup(response.text, "html.parser")

exp = re.compile(r"^(?:https?:)?//en\.wikipedia\.org/wiki/(?!.*_\([^)]*\)$)[^:#]+$")
all_links = content.find_all("a", {"href" : exp})
all_links_text = [link["href"] for link in all_links]
for link in all_links_text:
    print(link)


