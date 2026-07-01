import requests
import bs4
import os
import time

os.makedirs('xkcd', exist_ok = True)

link = 'https://xkcd.com/'
prev_link = 0

while prev_link != 1:

    page = requests.get(link)
    page.raise_for_status()
    soup_page = bs4.BeautifulSoup(page.text, 'html.parser')

    img_div = soup_page.select_one('#comic')
    img_link = img_div.img['src']

    comic_image = requests.get("https:" + img_link)
    comic_image.raise_for_status()

    filename = os.path.basename(img_link)
    file_path = os.path.join('xkcd', filename)
    image_file = open(file_path, 'wb')

    prev_button = soup_page.select('a[rel="prev"]')[0]
    prev_link = prev_button["href"]
    link = "https://xkcd.com/" + prev_link

    for chunk in comic_image.iter_content(100000):
        image_file.write(chunk)
    image_file.close()

    time.sleep(0.5)


