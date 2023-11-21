import requests
import time
from datetime import datetime
import json
from bs4 import BeautifulSoup
import re
from selenium import webdriver
from selenium.webdriver import Firefox, FirefoxOptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import telegram





# gets a values from a nested object
def get_value_from_config(path):

    with open("config.json") as file:
        config_json = json.load(file)

    data = config_json

    for prop in path:
        if len(prop) == 0:
            continue
        if prop.isdigit():
            prop = int(prop)
        data = data[prop]

    return data


def get_links_to_offers():
    html = get_html_from_saga()
    if html == "":
        return []

    links_to_offers = []

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all('a', class_='inner media', href=True)

    for link in links:
        if "/objekt/wohnungen/" in link['href']:
            links_to_offers.append("https://saga.hamburg" + link['href'])

    return links_to_offers


def get_html_from_saga():
    post_address = "https://www.saga.hamburg/immobiliensuche"
    request_data = {
        "sort": "preis",
        "perpage": 90,
        "type": "wohnungen"
    }

    try:
        r = requests.post(post_address, json=request_data, headers={'Content-Type': 'application/json'})
        if not r.status_code == 200:
            print("could post to saga")
            print("Error code", r.status_code)
            return ""
        else:
            return r.content

    except requests.exceptions.RequestException as e:
        print("error while posting to saga" + str(e))
        return ""


def get_offer_title(link_to_offer):
    try:
        get_url = requests.get(link_to_offer)
        get_text = get_url.text
        soup = BeautifulSoup(get_text, "html.parser")

        title = soup.find_all('h1', class_='h3 ft-bold', limit=1)[0]

        return title.text

    except:
        return ' '


# posts all information about an offer to telegram
def post_offer_to_telegram(link_to_offer, chat_id):
    send_msg_to_telegram("/////////////////////////////////////////////////////", chat_id)
    for msg in [link_to_offer, get_offer_title(link_to_offer)]:
        send_msg_to_telegram(msg, chat_id)





def apply_for_offer(link_to_offer):
    options = FirefoxOptions()
    options.headless = False  
    browser = Firefox(options=options)
    browser.get(link_to_offer)
    time.sleep(1)
    button = browser.find_element(By.CLASS_NAME, 'btn-blue')
    button.click()
    # wait = WebDriverWait(browser, 10)
    time.sleep(10)
    wait.until(EC.presence_of_element_located(By.CLASS_NAME, 'application-actions__inner'))
    # Klick auf die Schaltfläche auf der neuen Seite
    rent_element = browser.find_element(By.CLASS_NAME, 'application-actions__inner')
    w_button = parent_element.find_element(By.CLASS_NAME, 'button--type-primary')
    new_button.click()
    




# sends a message to a telegram chat
def send_msg_to_telegram(msg, chat_id):
    token = get_value_from_config(["telegram_token"])

    msg = 'https://api.telegram.org/bot' + token + '/sendMessage?chat_id=' + chat_id + '&parse_mode=Markdown&text=' + msg


    try:
        response = requests.get(msg)
        if not response.status_code == 200:
            print("could not forward to telegram")
            print("Error code", response.status_code)
            return False
    except requests.exceptions.RequestException as e:
        print("could not forward to telegram" + str(e))
        print("this was the message I tried to send: " + msg)


def add_offer_to_known_offers(offer):
    print("adding offer to known offers")
    file = open("known_offers.txt", "a+")
    file.write(offer)
    file.write("\n")
    file.close()

def add_offer_to_wanted_offers(offer):
    print("adding offer to wanted offers")
    file = open("wanted_offers.txt", "a+")
    file.write(offer)
    file.write("\n")
    file.close()


def is_offer_zipcode_in_whitelist(offer_soup, whitelisted_zipcodes:[int], link_to_offer):

    address = offer_soup.find_all('p', class_='ft-semi', limit=1)  # address is in "ft-semi" class
    if address:
        zipcode = int(re.findall('\d{5}', str(address[0]))[0])  # find zipcode by regex for 5digits

        if zipcode in whitelisted_zipcodes:
            print("zipcode in whitelist", zipcode)
            return True
        else:
            print("zipcode not in whitelist")
            return False

    print("could not find address in link ", link_to_offer)

    return False


def is_offer_rent_below_max(offer_soup, max_rent) -> bool:
    # Example rent_string 1.002,68 €
    rent_string = offer_soup.find("dt",text="Gesamtmiete").findNext("dd").string
    rent_string = rent_string.replace('€', '').replace(' ', '')
    rent_string = rent_string.split(',')[0]  # ignore cents
    rent = rent_string.replace('.', '')  # replace 1.000 to be 1000

    print("rent", rent, max_rent)

    if float(rent) <= max_rent:
        return True

    return False


def is_offer_rooms_above_min_rooms(offer_soup, min_rooms) -> bool:
    rooms_string = offer_soup.find("dt",text="Zimmer").findNext("dd").string

    try:
        rooms = int(rooms_string)
    except ValueError:
        # invalid literal for int() with base 10: '2 1/2'  there is "half rooms"
        rooms_string = rooms_string.split(" ")[0]
        rooms = int(rooms_string)

    if rooms >= min_rooms:
        return True

    return False


# checks if the offer meets the criteria for this chat
def offer_meets_chat_criteria(link_to_offer, chat_id) -> bool:
    criteria = get_value_from_config(["chats", chat_id, "criteria"])
    print(criteria)

    zipcode_whitelist = criteria["zipcode_whitelist"]

    get_url = requests.get(link_to_offer)
    get_text = get_url.text
    offer_soup = BeautifulSoup(get_text, "html.parser")

    rent_until = criteria["rent_until"]
    print("max_rent", rent_until)
    if not is_offer_rent_below_max(offer_soup, max_rent=rent_until):
        print("rent too high")
        return False

    min_rooms = criteria["min_rooms"]
    print("min_rooms", min_rooms)
    if not is_offer_rooms_above_min_rooms(offer_soup, min_rooms=min_rooms):
        print("not enough rooms")
        return False

    # check if zipcode is in zipcode whitelist
    if zipcode_whitelist and not is_offer_zipcode_in_whitelist(offer_soup, zipcode_whitelist, link_to_offer):
        print("Offer not in zipcode whitelist")
        return False

    # all criteria matched
    return True


if __name__ == "__main__":

    chat_ids = get_value_from_config(["chats"]).keys()

    for chat_id in chat_ids:
        if get_value_from_config(["chats", chat_id, "debug_group"]):
            send_msg_to_telegram("Bot started at " + str(datetime.now()), chat_id)

if __name__ == "__main__":
    chat_data = get_value_from_config(["chats"])
    print(chat_data)


    while True:
        print("checking for updates ", datetime.now())
        current_offers = get_links_to_offers()

        for offer in current_offers:
            if offer not in open("known_offers.txt").read().splitlines():
                print("new offer", offer)
                # for each chat: send offer to telegram, if it meets the chat's criteria
                for chat_id in chat_ids:
                    if offer_meets_chat_criteria(offer, chat_id):
                        # if there is a whitelist for this chat: Post offer only if location is in whitelist
                        post_offer_to_telegram(offer, chat_id)
                        # add offer to wanted list to check
                        add_offer_to_wanted_offers(offer)
                        # apply for flat
                        apply_for_offer(offer)



                # finally add to known offers
                add_offer_to_known_offers(offer)

        # check every xx seconds
        time.sleep(0.2)



