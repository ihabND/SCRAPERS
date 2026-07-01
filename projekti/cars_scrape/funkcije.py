from time import sleep
import requests
import json
from bs4 import BeautifulSoup

def makni_praznine(tekst):
    novi_tekst = ""
    for cifra in tekst:
        if cifra.isdigit():
            novi_tekst += cifra
    return novi_tekst

def get_page_content(url):
    sleep(0.2)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    content = BeautifulSoup(response.text, 'html.parser')
    return content

def get_next_page_link(content):
    link_next_page = content.find("a", {'aria-label' : 'Next »'})
    return link_next_page

def write_to_JSON(all_cars_list, file_name):
    with open(f"{file_name}.json", "w", encoding="utf-8") as file:
        json.dump(all_cars_list, file, indent=2) 

def create_car(individual_car_page, counter):
        new_car = {}

        new_car["id"] = counter

        details_div = individual_car_page.find("div", {'class' : 'vehicle-details'})
        details_data = details_div.find_all("td")
        info_categories = ["brand", 
                "model", 
                "year", 
                "engine", 
                "drivetrain", 
                "power_HP", 
                "country", 
                "mileage_KM", 
                "condition"]
        formatirane = ["power_HP", "mileage_KM"]
        for i in range(len(info_categories)):
            if info_categories[i] in formatirane:
                new_car[info_categories[i]] = makni_praznine(details_data[i].getText())
            else:
                new_car[info_categories[i]] = details_data[i].getText()

        new_car["body"] = individual_car_page.find("td", {"class" : "body-style"}).getText()

        availabilty = individual_car_page.find("div", {'class' : ['availability', 'badge', 'float-end', 'p-2']})
        new_car["availabilty"] = availabilty.getText().strip()

        new_car["price_EUR"] = makni_praznine(individual_car_page.find("span", {'class' : 'amount'}).getText())

        car_rating = individual_car_page.find("div", {'class' : 'rarity-rating'})
        new_car["rating"] = car_rating["data-rating"]

        new_car["seller"] = individual_car_page.find("p", {'class' : 'seller'}).getText()

        transmission_options_form = individual_car_page.find("select", {'class' : ['form-select', 'transmission']})
        transmission_options = transmission_options_form.find_all("option")
        transmission_options_list = [option["value"] for option in transmission_options]
        new_car["transmission"] = transmission_options_list

        tags_div = individual_car_page.find("div", {"class" : "tags"})
        tags = tags_div.find_all("span", {'class' : ['badge', 'tag']})
        tags_list = [tag.getText() for tag in tags]
        new_car["tags"] = tags_list

        all_colors_div = individual_car_page.find(id='color-swatches')
        all_colors_list = all_colors_div.find_all("button")
        new_car["colors"] = [button["value"] for button in all_colors_list]

        new_car["image_link"] = individual_car_page.find(id='main-product-image')['src']

        return new_car