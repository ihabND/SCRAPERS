# selecting by CLASS

import requests
from bs4 import BeautifulSoup

url = 'https://www.pythonscraping.com/pages/warandpeace.html'
response = requests.get(url, timeout=30)
content = BeautifulSoup(response.text, 'html.parser')
names = content.find_all("span", {"class" : "green"})
names_unique = list(set([name.getText().title() for name in names]))
for name in names_unique:
    print(name)