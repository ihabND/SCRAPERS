# SIBLING method

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.pythonscraping.com/pages/page3.html"
response = requests.get(BASE_URL, timeout=30)
content = BeautifulSoup(response.text, "html.parser")

articles = content.find("table", {"id" : "giftList"}).tr.next_siblings
for article in articles:
    print(article.getText())