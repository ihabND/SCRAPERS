# using ATTRS

import requests
from bs4 import BeautifulSoup
import re

BASE_URL = "https://www.pythonscraping.com/pages/page3.html"
response = requests.get(BASE_URL, timeout=30)
content = BeautifulSoup(response.text, "html.parser")

element = content.find("img")
attributes = element.attrs

for key, value in attributes.items():
    print(key, " --- ",value)