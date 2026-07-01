# using REGEX

import requests
from bs4 import BeautifulSoup
import re

BASE_URL = "https://www.pythonscraping.com/pages/page3.html"
response = requests.get(BASE_URL, timeout=30)
content = BeautifulSoup(response.text, "html.parser")

exp = re.compile(r"^\.\./img/gifts/img.*\.jpg$")
images = content.find_all('img', {'src' : exp})

for image in images:
    print(image['src'])    