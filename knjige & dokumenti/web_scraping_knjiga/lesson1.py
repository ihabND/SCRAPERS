# TRY - CATCH for safer scrape

import requests
from bs4 import BeautifulSoup

def getTitle(url):
    try:
        html = requests.get(url)
    except Exception as e:
        return None
    try:
        bs = BeautifulSoup(html.text, 'html.parser')
        title = bs.body.h1
    except AttributeError as e:
        return None
    return title

title = getTitle('http://www.pythonscraping.com/pages/page1.html')
if title == None:
    print("Title could not be found!")
else:
    print(f"Title: {title}.")