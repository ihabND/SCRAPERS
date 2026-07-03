from util import get_page, get_all_links

BASE_URL = "https://www.imdb.com/title/"
URL_TOP = "https://www.imdb.com/chart/top/"

top_250_page = get_page(URL_TOP)
individual_movie_links_list = get_all_links(top_250_page)

brojac = 0
for link in individual_movie_links_list:
    print(brojac, link)
    brojac += 1

