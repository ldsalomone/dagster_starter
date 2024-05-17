import json
import os
import time
from typing import List

import pandas as pd  # Add new imports to the top of `assets.py`
import requests
import base64
from io import BytesIO

import matplotlib.pyplot as plt
from dagster import AssetExecutionContext, MetadataValue, asset, MaterializeResult, get_dagster_logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromiumService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

@asset
def al_scraper() -> None:
    from certipy import scraper

    al_scraper = scraper.AL()
    df = al_scraper.search_by_type_and_name("PC", "", "J")
    my_logger.info(len(df))
    my_logger.info(df.iloc[0])


def get_table_data(driver):
    my_logger = get_dagster_logger()
    # Find the table element by its ID
    table = driver.find_element(By.XPATH, '//*[@id="ContentPlaceHolder2_LData"]')
    # Find all rows of the table
    rows = table.find_elements(By.TAG_NAME, "tr")

    table_data = []
    my_logger.info(len(rows))
    for i, row in enumerate(rows[4:]):  # Skip the first four rows
        if i % 100 == 0:
            my_logger.info(f"Processing row {i}")
        # Find all cells of the row
        cells = row.find_elements(By.TAG_NAME, "td")
        # Extract text from each cell and append to table_data
        table_data.append([cell.text for cell in cells])

    return table_data


@asset  # add the asset decorator to tell Dagster this is an asset
def topstory_ids() -> None:
    newstories_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
    top_new_story_ids = requests.get(newstories_url).json()[:100]

    os.makedirs("data", exist_ok=True)
    with open("data/topstory_ids.json", "w") as f:
        json.dump(top_new_story_ids, f)


@asset(deps=[topstory_ids])  # this asset is dependent on topstory_ids
def topstories() -> None:
    with open("data/topstory_ids.json", "r") as f:
        topstory_ids = json.load(f)

    results = []
    for item_id in topstory_ids:
        item = requests.get(
            f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
        ).json()
        results.append(item)

        if len(results) % 20 == 0:
            print(f"Got {len(results)} items so far.")

    df = pd.DataFrame(results)
    df.to_csv("data/topstories.csv")


@asset(deps=[topstories])
def most_frequent_words() -> None:
    stopwords = ["a", "the", "an", "of", "to", "in", "for", "and", "with", "on", "is"]

    topstories = pd.read_csv("data/topstories.csv")

    # loop through the titles and count the frequency of each word
    word_counts = {}
    for raw_title in topstories["title"]:
        title = raw_title.lower()
        for word in title.split():
            cleaned_word = word.strip(".,-!?:;()[]'\"-")
            if cleaned_word not in stopwords and len(cleaned_word) > 0:
                word_counts[cleaned_word] = word_counts.get(cleaned_word, 0) + 1

    # Get the top 25 most frequent words
    top_words = {
        pair[0]: pair[1]
        for pair in sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:25]
    }

    with open("data/most_frequent_words.json", "w") as f:
        json.dump(top_words, f)


@asset(deps=[topstories])
def most_frequent_words() -> MaterializeResult:
    stopwords = ["a", "the", "an", "of", "to", "in", "for", "and", "with", "on", "is"]

    topstories = pd.read_csv("data/topstories.csv")

    # loop through the titles and count the frequency of each word
    word_counts = {}
    for raw_title in topstories["title"]:
        title = raw_title.lower()
        for word in title.split():
            cleaned_word = word.strip(".,-!?:;()[]'\"-")
            if cleaned_word not in stopwords and len(cleaned_word) > 0:
                word_counts[cleaned_word] = word_counts.get(cleaned_word, 0) + 1

    # Get the top 25 most frequent words
    top_words = {
        pair[0]: pair[1]
        for pair in sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:25]
    }

    # Make a bar chart of the top 25 words
    plt.figure(figsize=(10, 6))
    plt.bar(list(top_words.keys()), list(top_words.values()))
    plt.xticks(rotation=45, ha="right")
    plt.title("Top 25 Words in Hacker News Titles")
    plt.tight_layout()

    # Convert the image to a saveable format
    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    image_data = base64.b64encode(buffer.getvalue())

    # Convert the image to Markdown to preview it within Dagster
    md_content = f"![img](data:image/png;base64,{image_data.decode()})"

    with open("data/most_frequent_words.json", "w") as f:
        json.dump(top_words, f)

    # Attach the Markdown content as metadata to the asset
    return MaterializeResult(metadata={"plot": MetadataValue.md(md_content)})

def get_table_data_pw(page):
    my_logger = get_dagster_logger()
    table = page.locator('//*[@id="ContentPlaceHolder2_LData"]')
    table.wait_for()
    rows = table.locator("tr").all()
    my_logger.info(rows)
    table_data = []
    for row in rows[4:]:
        my_logger.info(row)
        table_data.append([cell.inner_text() for cell in row.locator("td").all()])
    return table_data

@asset
def run_playwright() -> List:
    my_logger = get_dagster_logger()
    import playwright.sync_api as p

    with p.sync_playwright() as pw:

        #  browser = pw.chromium.connect_over_cdp(
        #      "wss://production-sfo.browserless.io?token=Q24V0Yq4e6ifri9f9b1b075944bcdad3f742ad9f8c"
        #  )
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://oop.ky.gov/")

        pc_checkbox = page.locator('//*[@id="ContentPlaceHolder2_chkBoards_9"]')
        pc_checkbox.hover()
        pc_checkbox.click()

        last_name_box = page.locator('//*[@id="ContentPlaceHolder2_TLname"]')
        last_name_box.hover()
        last_name_box.click()

        all_data = []

        for letter in "AB":
            t_data = []
            my_logger.info(f"Scraping for {letter}...")
            last_name_box.fill(letter)

            search_button = page.locator('//*[@id="ContentPlaceHolder2_BSrch"]')
            search_button.hover()
            search_button.click()
            time.sleep(5)
            my_logger.info("---getting table data...")
            t_data = get_table_data_pw(page)
            my_logger.info(f"---{len(t_data)} rows retrieved...")
            all_data.extend(t_data)

    return all_data

@asset
def run_selenium() -> None:
    my_logger = get_dagster_logger()
    # import chromedriver_autoinstaller

    # chromedriver_autoinstaller.install()
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    # driver = webdriver.Chrome(
    #     service=ChromiumService(
    #         ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install(),
    #         options=options,
    #     )
    # )

    # service = webdriver.ChromeService(executable_path=chromedriver_bin)

    # driver = webdriver.Chrome(service=service, options=options)
    driver = webdriver.Chrome(options=options)

    driver.get("https://oop.ky.gov/")

    # Find and interact with elements using Selenium
    pc_checkbox = driver.find_element(
        By.XPATH, '//*[@id="ContentPlaceHolder2_chkBoards_9"]'
    )
    pc_checkbox.click()

    all_data = []

    for letter in "ABCDEGFHIJKLMNOPQRSTUVWXYZ":
        my_logger.info(f"Scraping for {letter}...")
        last_name_box = driver.find_element(
            By.XPATH, '//*[@id="ContentPlaceHolder2_TLname"]'
        )
        last_name_box.clear()
        last_name_box.send_keys(letter)

        search_button = driver.find_element(
            By.XPATH, '//*[@id="ContentPlaceHolder2_BSrch"]'
        )
        search_button.click()
        time.sleep(5)
        my_logger.info("---getting table data...")
        t_data = get_table_data(driver)
        my_logger.info(f"---{len(t_data)} rows retrieved...")
        all_data.extend(t_data)

    print(all_data)
