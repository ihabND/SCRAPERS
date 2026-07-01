import requests
from bs4 import BeautifulSoup
import re
from time import sleep
import json
from funkcije import *

BASE_URL = "https://webscraper.io/test-sites/pagination/"
BASE_LINK = "https://webscraper.io/test-sites/product/"

counter = 1
all_cars_list = []
while True:    
    content = get_page_content(BASE_URL)
    all_cars_div = content.find("div", {'class' : 'test-items-container'})
    link_re_exp = re.compile("https://webscraper.io/test-sites/product/.*")
    
    all_cars_links = all_cars_div.find_all("a", {'href' : link_re_exp})
    all_cars_links = set([link["href"] for link in all_cars_links])
    for link in all_cars_links:
        individual_car_page = get_page_content(link) 
        new_car = create_car(individual_car_page, counter)
        all_cars_list.append(new_car)
        print(counter)
        counter += 1

    link_next_page = get_next_page_link(content)
    if link_next_page is None:
        break
    BASE_URL = link_next_page["href"]

write_to_JSON(all_cars_list, "cars")