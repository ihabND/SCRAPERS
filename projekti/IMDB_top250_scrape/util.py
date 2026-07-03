import requests
from bs4 import BeautifulSoup
from info import headers

BASE_URL = "https://www.imdb.com/title/"
URL_TOP = "https://www.imdb.com/chart/top/"

def get_page(url):
    try:
        response = requests.get(url, 
                                headers=headers, 
                                timeout=60)
        content = BeautifulSoup(response.text, 
                                "html.parser")
        return content
    except Exception as e:
        print(e)
        return None

def get_all_links(content):
    BASE_URL = "https://www.imdb.com/title/"
    all_links = content.find_all("a", {"class" : "ipc-title-link-wrapper"})
    all_links_list = [BASE_URL + link["href"] for link in all_links]
    return all_links_list
