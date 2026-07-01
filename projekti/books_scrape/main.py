import requests
import bs4
import json
from util_func import convert_rating
from time import sleep


BASE_URL = "https://books.toscrape.com/catalogue/"
START_URL = "https://books.toscrape.com/catalogue/page-{page}.html"


session = requests.Session()


def get_soup(url: str) -> bs4.BeautifulSoup:
    response = session.get(url, timeout=10)
    response.encoding = "utf-8"
    response.raise_for_status()
    return bs4.BeautifulSoup(response.text, "html.parser")


def get_max_pages() -> int:
    max_page = int(input("How many pages do you want to scrape? "))
    return min(max(max_page, 0), 50)


def get_book_cards(soup: bs4.BeautifulSoup):
    return soup.select(".product_pod")


def build_detail_url(href: str) -> str:
    return BASE_URL + href


def extract_genre(url: str) -> str:
    sleep(0.2)
    soup = get_soup(url)
    return soup.find_all("a")[3].text


def extract_book_from_card(book) -> dict:
    title = book.h3.a["title"]
    price = book.find("p", class_="price_color").text
    stock = book.find("p", class_="instock availability").text.strip()

    rating_class = book.find("p", class_="star-rating").get("class")[1]
    rating = convert_rating(rating_class)

    detail_url = build_detail_url(book.h3.a["href"])
    genre = extract_genre(detail_url)

    return {
        "title": title,
        "price": price[1:],
        "stock": stock,
        "genre": genre,
        "rating": rating,
    }


def print_book(book: dict):
    print(
        book["title"] + "\n" +
        book["price"] + "\n" +
        book["stock"] + "\n" +
        book["genre"] + "\n" +
        f"Rated {book['rating']}.\n\n"
    )


def save_books(data, filename="knjige.txt"):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def scrape_books(max_page: int):
    books_scraped = 0
    book_info = []

    for i in range(1, max_page + 1):
        sleep(0.5)
        soup = get_soup(START_URL.format(page=i))
        cards = get_book_cards(soup)

        for book in cards:
            data = extract_book_from_card(book)

            book_info.append({
                "title": data["title"],
                "price": data["price"],
                "stock": data["stock"],
                "genre": data["genre"],
                "rating": data["rating"]
            })

            print_book(data)
            books_scraped += 1

            sleep(0.1)

        print(f"BOOKS SCRAPED: {books_scraped}.")

    return book_info


def main():
    max_page = get_max_pages()
    data = scrape_books(max_page)
    save_books(data)


if __name__ == "__main__":
    main()