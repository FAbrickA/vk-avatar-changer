import datetime as dt
import pickle
import time
import os
from typing import List

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

import login_data

BASE_DIR = os.getcwd()
UTC_OFFSET = 3  # hours


def get_photos():
    photos = []
    with open(os.path.join(BASE_DIR, 'schedule.txt'), 'r') as schedule_file:
        line_number = 0
        for line in schedule_file:
            line_number += 1
            line = line.strip()
            if not line:
                continue
            time_str, link = line.split()
            time_arr = time_str.split(":")
            if len(time_arr) > 3 or len(time_arr) < 1:
                raise ValueError(f"Incorrect time \"{time_str}\" on line {line_number}")
            seconds = int(time_arr[0]) * 3600
            try:
                seconds += int(time_arr[1]) * 60
                seconds += int(time_arr[2])
            except IndexError:
                pass
            photos.append(PlannedPhoto(seconds, link))
    photos.sort(key=lambda x: x.time)
    return photos


def close_driver(driver: webdriver.Chrome):
    try:
        driver.close()
    except Exception:
        pass
    try:
        driver.quit()
    except Exception:
        pass
    del driver


def main():
    driver_filepath = os.path.join(BASE_DIR, "chromedriver", "chromedriver.exe")
    try:
        photos = get_photos()
        photo_i = get_nearest_photo_index(photos)
        while True:
            photo = photos[photo_i]
            photo.wait_to_next_call()
            driver = webdriver.Chrome(service=Service(driver_filepath))
            driver.get("https://vk.com")
            auth(driver)
            photo.set_photo(driver)
            close_driver(driver)
            photo_i = (photo_i + 1) % len(photos)
    except Exception as e:
        raise e
    finally:
        try:
            driver.close()
        except Exception:
            pass
        driver.quit()
        print("Finished")


def auth(driver: webdriver.Chrome):
    cookie_folder = os.path.join(BASE_DIR, 'cookies')
    if not os.path.exists(cookie_folder):
        os.mkdir(cookie_folder)
    cookie_filepath = os.path.join(cookie_folder, 'cookies.cookie')
    if os.path.exists(cookie_filepath):
        with open(cookie_filepath, 'rb') as cookie_file:
            cookies = pickle.load(cookie_file)
        for cookie in cookies:
            driver.add_cookie(cookie)
        driver.refresh()
    time.sleep(0.5)

    if driver.current_url.split("/")[-1] != "feed":  # if not logged
        login_field = driver.find_element(By.CSS_SELECTOR, "input#index_email")
        password_field = driver.find_element(By.CSS_SELECTOR, "input#index_pass")
        submit_button = driver.find_element(By.CSS_SELECTOR, "button#index_login_button")
        login_field.send_keys(login_data.LOGIN)
        password_field.send_keys(login_data.PASSWORD)
        submit_button.click()

    second_to_wait = 5  # to wait for logging
    sleep_time = 0.1  # time between checks
    i = 0  # counter
    while driver.current_url.split("/")[-1] != "feed":  # while not logged
        i += sleep_time
        if i > second_to_wait:
            raise AttributeError("Incorrect login or password")
        time.sleep(sleep_time)

    cookies = driver.get_cookies()
    with open(cookie_filepath, 'wb') as cookie_file:
        pickle.dump(cookies, cookie_file)


class PlannedPhoto:
    day = 24 * 3600
    offset = UTC_OFFSET * 3600  # hours to seconds

    def __init__(self, seconds, link):
        super().__init__()
        self.time = seconds
        self.link = link

    def time_to_next_call(self):
        utcnow = dt.datetime.utcnow()
        seconds_now = dt.timedelta(
            hours=utcnow.hour,
            minutes=utcnow.minute,
            seconds=utcnow.second,
            microseconds=utcnow.microsecond
        ) / dt.timedelta(seconds=1)
        seconds = (self.time - (seconds_now + self.offset)) % self.day
        return seconds

    def wait_to_next_call(self):
        print(round(self.time_to_next_call()), round(self.time_to_next_call() / 3600, 3))
        time.sleep(self.time_to_next_call())

    @staticmethod
    def __try_execute(func, *args, time_wait=0.1, timeout=5):
        time_waited = 0
        while True:
            if time_waited >= timeout:
                raise ValueError("Timeout reached")
            try:
                func(*args)
            except Exception:
                time.sleep(time_wait)
                time_waited += time_wait
            else:
                break

    def set_photo(self, driver: webdriver.Chrome):
        driver.get(self.link)

        def get_action_more(driver: webdriver.Chrome):
            pv_actions_more = driver.find_element(By.CSS_SELECTOR, "a.pv_actions_more")
            ActionChains(driver).move_to_element(pv_actions_more).perform()

        self.__try_execute(get_action_more, driver)

        def open_add_to_profile_window(driver: webdriver.Chrome):
            driver.find_element(By.CSS_SELECTOR, "div#pv_more_act_to_profile").click()

        self.__try_execute(open_add_to_profile_window, driver)

        def click_submit_button(driver: webdriver.Chrome):
            driver.find_element(By.CSS_SELECTOR, "div.BaseModal.OwnerAvatarEditor__modal "
                                                 "button.Button.Button--primary.Button--size-m").click()

        self.__try_execute(click_submit_button, driver)
        self.__try_execute(click_submit_button, driver)

        def final_window_handler(driver: webdriver.Chrome):
            for label in driver.find_elements(By.CSS_SELECTOR, "div.BaseModal.OwnerAvatarEditor__modal "
                                                               "label.CheckBox"):
                if label.find_element(By.CSS_SELECTOR, "input.CheckBox__input").is_selected():
                    label.click()
            driver.find_element(By.CSS_SELECTOR, "div.BaseModal.OwnerAvatarEditor__modal "
                                                 "button.Button.Button--primary.Button--size-m").click()

        self.__try_execute(final_window_handler, driver)

        def check_if_photo_was_uploaded(driver: webdriver.Chrome):
            notification = driver.find_element(By.CSS_SELECTOR, "div.notifier_baloon_msg.wrapped")

        self.__try_execute(check_if_photo_was_uploaded, driver)


def get_nearest_photo_index(photos: List[PlannedPhoto]):
    last_time_to_next_call = 24 * 3600 + 1
    min_time_to_next_call = 24 * 3600 + 1
    photo_i = -1
    for i in range(len(photos)):
        time_to_next_call = photos[i].time_to_next_call()
        if 5 < time_to_next_call < min_time_to_next_call:  # block next call if it less than 5 seconds
            photo_i = i
            min_time_to_next_call = time_to_next_call
        elif time_to_next_call <= last_time_to_next_call:
            break
        last_time_to_next_call = time_to_next_call
    return photo_i


if __name__ == '__main__':
    main()
