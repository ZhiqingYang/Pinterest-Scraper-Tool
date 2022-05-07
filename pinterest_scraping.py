#!/usr/bin/env python
# coding: utf-8

# In[7]:


import sys
import re
import json
import os
from os.path import exists
import cv2
import csv
import numpy as np
from requests import get
from tqdm import tqdm
from bs4 import BeautifulSoup as soup
from concurrent.futures import ThreadPoolExecutor

from pydotmap import DotMap


class PinterestImageScraper:

    def __init__(self):
        self.json_data_list = []
        self.unique_img = []
        self.test_list = []
        self.key_word = ""

    @staticmethod
    def clear():
        if os.name == 'nt':
            _ = os.system('cls')
        else:
            _ = os.system('clear')

    # ---------------------------------------- GET GOOGLE RESULTS ---------------------------------
    @staticmethod
    def get_pinterest_links(body):
        searched_urls = []
        html = soup(body, 'html.parser')
        links = html.select('#main > div > div > div > a')
        print('[+] saving results ...')
        for link in links:
            link = link.get('href')
            link = re.sub(r'/url\?q=', '', link)
            if link[0] != "/" and "pinterest" in link:
                searched_urls.append(link)

        return searched_urls

    # -------------------------- save json data from source code of given pinterest url -------------
    def get_source(self, url):
        try:
            res = get(url)
        except Exception as e:
            return
        html = soup(res.text, 'html.parser')
        # get json data from script tag having id initial-state
        json_data = html.find_all("script", attrs={"id": "__PWS_DATA__"})
        for a in json_data:
            self.json_data_list.append(a.string)

    # --------------------------- READ JSON OF PINTEREST WEBSITE ----------------------
    def save_image_url(self):
        print('[+] saving image urls ...')
        url_list = [i for i in self.json_data_list if i.strip()]
        if not len(url_list):
            return url_list
        url_list = []

        for js in self.json_data_list:
            try:
                data = DotMap(json.loads(js))
                urls = []

                for pin in data.props.initialReduxState.pins:

                    # get all relevant info
                    pic = data.props.initialReduxState.pins[pin].images.get("474x").get("url")
                    name = data.props.initialReduxState.pins[pin].rich_summary.get("display_name")
                    description = data.props.initialReduxState.pins[pin].rich_summary.get("display_description")
                    pic_name = data.props.initialReduxState.pins[pin].images.get("474x").get("url").split('/')[-1]

                    if isinstance(data.props.initialReduxState.pins[pin].images.get("474x"), list):
                        for i in data.props.initialReduxState.pins[pin].images.get("474x"):
                            if description != "":
                                url_list.append(i.get("url"))
                                combo = [self.key_word, i.get("url"), pic_name, name, description]
                                self.test_list.append(combo)

                    else:
                        if description != "":
                            url_list.append(pic)
                            combo = [self.key_word, pic, pic_name, name, description]
                            self.test_list.append(combo)

            #                 for url in urls:
            #                     url_list.append(url)

            except Exception as e:
                continue

        #         self.test_list = list(set(self.test_list))
        return list(set(url_list))

    # ------------------------------ image hash calculation -------------------------
    def dhash(self, image, hashSize=8):
        resized = cv2.resize(image, (hashSize + 1, hashSize))
        diff = resized[:, 1:] > resized[:, :-1]
        return sum([2 ** i for (i, v) in enumerate(diff.flatten()) if v])

    # ------------------------------  save all downloaded images to folder ---------------------------
    def saving_op(self, var):
        url_list, folder_name = var
        #         if not os.path.exists(os.getcwd() + folder_name):
        #             os.mkdir(os.getcwd() + "/result/images")
        for img in tqdm(url_list):
            result = get(img, stream=True).content
            file_name = img.split("/")[-1]
            file_path = os.getcwd() + "/result/images/" + file_name
            img_arr = np.asarray(bytearray(result), dtype="uint8")
            image = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
            if not self.dhash(image) in self.unique_img:
                cv2.imwrite(file_path, image)
            self.unique_img.append(self.dhash(image))

    # ------------------------------  download images from image url list ----------------------------
    def download(self, url_list, keyword):
        folder_name = keyword
        num_of_workers = 10
        idx = len(url_list) // num_of_workers
        param = []
        for i in range(num_of_workers):
            # [((i*idx)):(idx*(i+1))]
            param.append((url_list, keyword))

        with ThreadPoolExecutor(max_workers=num_of_workers) as executor:
            executor.map(self.saving_op, param)
        PinterestImageScraper.clear()

    # -------------------------- get user keyword and google search for that keywords ---------------------
    @staticmethod
    def start_scraping(key=None):
        try:
            key = input("Enter keyword: ") if key == None else key

            keyword = key + " pinterest"
            keyword = keyword.replace("+", "%20")
            url = f'http://www.google.co.in/search?hl=en&q={keyword}'
            print('[+] starting search ...')
            res = get(url)
            # see the result from first scraping
            searched_urls = PinterestImageScraper.get_pinterest_links(res.content)
        except Exception as e:
            return []

        return searched_urls, key

    def make_ready(self, key=None):
        extracted_urls, keyword = PinterestImageScraper.start_scraping(key)
        # store the key
        self.key_word = keyword

        print('[+] saving json data ...')
        for i in extracted_urls:
            self.get_source(i)

        # get all urls of images and save in a list
        url_list = self.save_image_url()

        # download images from saved images url
        print(f"[+] Total {len(url_list)} files available to download.")
        print()

        if len(url_list):
            try:
                print("downloading...")

                if not os.path.exists(os.getcwd() + "/result"):
                    os.mkdir(os.getcwd() + "/result")
                    os.mkdir(os.getcwd() + "/result/images")

                self.download(url_list, keyword)

                # write current data into csv file
                csv_path = os.getcwd() + "/result/data.csv"
                with open(csv_path, 'a') as f:
                    writer = csv.writer(f)

                    if (os.path.getsize(csv_path) == 0):
                        writer.writerow(["search_keyword", "url", "name", "title", "description"])

                    for fields in self.test_list:
                        writer.writerow(fields)

            except KeyboardInterrupt:
                return False
            return True

        return False


if __name__ == "__main__":
    p_scraper = PinterestImageScraper()
    is_downloaded = p_scraper.make_ready()

    if is_downloaded:
        print("\nDownloading completed !!")
    else:
        print("\nNothing to download !!")

# In[ ]:




