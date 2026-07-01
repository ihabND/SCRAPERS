from time import sleep
import requests
from bs4 import BeautifulSoup

def get_page(INDIVIDUAL_URL, poke_name):
    headers = {
        "User-Agent" : (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept-Language": "en"
    }
    individual_page = requests.get(INDIVIDUAL_URL.format(pokemon_name=poke_name), headers=headers, timeout=60)
    return individual_page


def get_products(BASE_URL, page_id): # vrati ovaj div sto sadrzi pokemone, inkrementiran page_id i dal je nasao dugme za next page
    sleep(0.1)
    page = requests.get(BASE_URL.format(page_id=page_id))
    page_content = BeautifulSoup(page.text, "html.parser")  

    products = page_content.find("ul", class_="products")
    items = products.find_all("li", class_="product")
    next_btn = page_content.find("a", class_="next")
    page_id += 1
    return items, next_btn, page_id

def get_categories(poke_categ):
    # Od 'Categories: prva, druga, treca' napravi ['prva', 'druga', 'treca']
    poke_categ = poke_categ.split(": ", 1)
    poke_categ = poke_categ[1].split(", ")
    poke_categ_list = []
    for categ in poke_categ:
        poke_categ_list.append(categ)
    return poke_categ_list

def get_tags(poke_tags):
    # isto ka get_categories samo za tagove
    poke_tags = poke_tags.split(": ", 1)
    poke_tags = poke_tags[1].split(", ")
    poke_tags_list = []
    for tag in poke_tags:
        poke_tags_list.append(tag)
    return poke_tags_list

def create_pokemon(poke_data, poke_id, poke_name): # izvlaci podatke iz individualne 
    # pofata podatke
    poke_price = poke_data.find("span", class_="woocommerce-Price-amount").text[1:]
    poke_desc = poke_data.find("div", class_="woocommerce-product-details__short-description").text
    poke_categ = poke_data.find("span", class_="posted_in").text
    poke_tags = poke_data.find("span", class_="tagged_as").text
    poke_stock = poke_data.find("p", class_="stock").text
    poke_SKU = poke_data.find("span", class_="sku").text

    # turi u recnik
    pokemon = {}
    pokemon["id"] = poke_id
    pokemon["name"] = poke_name
    pokemon["price"] = poke_price
    pokemon["description"] = poke_desc
    pokemon["SKU"] = poke_SKU

    # kategorije su formata 'Categories: prva, druga, treca'
    poke_categ_list = get_categories(poke_categ)        
    pokemon["categories"] = poke_categ_list

    # tagovi isti format ka kategorije
    poke_tags_list = get_tags(poke_tags)
    pokemon["tags"] = poke_tags_list

    pokemon["stock"] = poke_stock.split(" ")[0]  
    
    # vrati pokemona kao recnik sa svim podacima
    return pokemon