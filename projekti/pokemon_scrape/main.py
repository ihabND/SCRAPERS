from bs4 import BeautifulSoup
import json
from functions import *

BASE_URL = "https://scrapeme.live/shop/page/{page_id}/"
INDIVIDUAL_URL = "https://scrapeme.live/shop/{pokemon_name}/"

pokemons = []
id = 0
page_id = 47 # pocinje od 47 da bi scrapovo samo zadnje dvije strane da se vidi
# kako radi a da se ne ceka 100 godina (19 pokemona je to)
while True:
    items, next_btn, page_id = get_products(BASE_URL, page_id)

    for item in items:
        id += 1
        poke_id = id      
        print(f"Scraping pokemon {id}/755") 

        poke_name = item.find("h2", class_="woocommerce-loop-product__title").text

        individual_page = get_page(INDIVIDUAL_URL, poke_name)
        individual_page_content = BeautifulSoup(individual_page.text, "html.parser")

        poke_data = individual_page_content.find("div", "summary")
        
        pokemon = create_pokemon(poke_data, poke_id, poke_name)      

        pokemons.append(pokemon)  

    if not next_btn: # ako nema dugme za next page onda break
        break

with open("pokemon_db.txt", "w", encoding="utf-8") as file:
    json.dump(pokemons, file, indent=2)
