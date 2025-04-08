import os
import re
import io
import csv
import base64
import asyncio
import time
import random
import requests
import zipfile
import json
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import argparse
import threading


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--proxy', help='Прокси в формате host:port:username:password', default=None)
    return parser.parse_args()

load_dotenv()

# ===================== 365sim API =====================
SIM_API_KEY = os.getenv("SIM_API_KEY")
if not SIM_API_KEY:
    raise Exception("Необходимо установить переменную окружения SIM_API_KEY")

SERVICE = 'yh'
COUNTRY = '0'
OPERATORS = ['megafon', 'mts', 'tele2']
MAX_RETRIES = 5

def get_number():
    operator = random.choice(OPERATORS)
    url = f'https://365api.net/stubs/handler_api.php?api_key={SIM_API_KEY}&action=getNumber&service={SERVICE}&operator={operator}&country={COUNTRY}'
    r = requests.get(url).text
    if 'ACCESS_NUMBER' in r:
        _, id_, number = r.strip().split(':')
        return id_, number
    raise Exception(f'Ошибка при заказе номера: {r}')

def get_status(id_):
    url = f'https://365api.net/stubs/handler_api.php?api_key={SIM_API_KEY}&action=getStatus&id={id_}'
    r = requests.get(url).text
    return r.strip()

def set_status(id_, status):
    url = f'https://365api.net/stubs/handler_api.php?api_key={SIM_API_KEY}&action=setStatus&status={status}&id={id_}'
    requests.get(url)

def wait_for_code(id_, timeout=90):
    for _ in range(timeout // 3):
        status = get_status(id_)
        if 'STATUS_OK:' in status:
            code = status.split(':')[1]
            set_status(id_, 6)
            return code
        elif status == 'STATUS_CANCEL':
            raise Exception('Активация отменена')
        time.sleep(3)
    set_status(id_, 8)
    return None

# ===================== GeminiVision (капча) =====================
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise Exception("Необходимо установить переменную окружения GOOGLE_API_KEY")

class GeminiVision:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name='gemini-2.0-flash')

    async def extract_text_from_image(self, image_path: str):
        with open(image_path, "rb") as img_file:
            image_data = base64.b64encode(img_file.read()).decode()
        image = Image.open(io.BytesIO(base64.b64decode(image_data)))
        prompt = ("This is a photo of a captcha, decipher it. Extract and return all words "
                  "in English without punctuation marks and numbers. And combine all words into one without spaces.")
        response = await self.model.generate_content_async([image, prompt])
        return re.sub(r'[^a-zA-Z]', '', response.text.lower()).strip()

def decipher_captcha(image_path: str) -> str:
    vision = GeminiVision(API_KEY)
    return asyncio.run(vision.extract_text_from_image(image_path))

# ===================== Ввод по символу =====================
def simulate_typing(element, text, delay=0.2):
    element.clear()
    for ch in text:
        element.send_keys(ch)
        time.sleep(delay)

# ===================== Selenium: регистрация, капча, OTP =====================
def solve_captcha(driver):
    wait = WebDriverWait(driver, 10)
    click_language = True
    while True:
        try:
            captcha_elems = driver.find_elements(By.CSS_SELECTOR, '[data-qa="account-captcha-picture"]')
            if not captcha_elems or not captcha_elems[0].is_displayed():
                print("Капча не видна, переходим к OTP/регистрации.")
                break
            captcha_elem = captcha_elems[0]
            if click_language:
                try:
                    lang_btn = driver.find_element(By.CSS_SELECTOR, '[data-qa="captcha-language"]')
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", lang_btn)
                    time.sleep(0.5)
                    lang_btn.click()
                    time.sleep(3)
                except Exception as e:
                    print("Не удалось кликнуть по смене языка:", e)
            captcha_path = "captcha.png"
            try:
                captcha_elem.screenshot(captcha_path)
            except Exception as e:
                print("Ошибка при скриншоте капчи:", e)
                time.sleep(1)
                continue
            try:
                captcha_text = decipher_captcha(captcha_path)
            except Exception as e:
                if "400 User location is not supported" in str(e):
                    print("Ошибка API капчи.")
                    print("Введите капчу вручную в браузере, нажмите кнопку 'Подтвердить',")
                    print("и когда появится поле для ввода кода, нажмите Enter в терминале.")
                    input()
                    break
                else:
                    print("Ошибка при расшифровке капчи:", e)
                    time.sleep(2)
                    continue
            print("Распознанный текст капчи:", captcha_text)
            captcha_input = driver.find_element(By.CSS_SELECTOR, '[data-qa="account-captcha-input"]')
            captcha_input.clear()
            captcha_input.send_keys(captcha_text)
            driver.find_element(By.CSS_SELECTOR, '[data-qa="account-signup-submit"]').click()
            time.sleep(2)
            if driver.find_elements(By.CSS_SELECTOR, '[data-qa="account-captcha-error"]'):
                print("Ошибка капчи, пробуем снова...")
                click_language = True
                time.sleep(2)
                continue
            break
        except StaleElementReferenceException:
            print("Stale element reference, пробуем заново...")
            time.sleep(1)
            continue
        except Exception as e:
            print("Ошибка при решении капчи:", e)
            break


def selenium_signup(phone_number):
    seleniumwire_options = {
        'proxy': {
            'http': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
            'https': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
            'no_proxy': 'localhost,127.0.0.1'
        },
        'verify_ssl': False,         # Отключаем проверку SSL сертификатов
        'disable_capture': True,     # Отключаем перехват HTTPS-трафика (и генерацию своего сертификата)
        'connection_interceptor': False,
        'enable_har': False,
        'disable_encoding': True,
    }

    options = webdriver.ChromeOptions()
    options.add_argument("--ignore-certificate-errors")  # на всякий случай
    driver = webdriver.Chrome(seleniumwire_options=seleniumwire_options, options=options)
    wait = WebDriverWait(driver, 10)
    driver.get("https://hh.ru/account/signup")
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-qa="account-signup-email"]'))).send_keys(phone_number)
    driver.find_element(By.CSS_SELECTOR, '[data-qa="account-signup-submit"]').click()
    time.sleep(3)

    def accept_cookies(driver):
        while True:
            try:
                elem = driver.find_element(By.CSS_SELECTOR, '[data-qa="cookies-policy-informer-accept"]')
                if elem.is_displayed():
                    elem.click()
                    print("Клик по 'Принять cookies' выполнен.")
                    break
            except Exception:
                pass
            time.sleep(1)  # Проверка каждую секунду

    # Запуск в отдельном потоке
    threading.Thread(target=accept_cookies, args=(driver,), daemon=True).start()


    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-qa="account-captcha-picture"]')))
        if driver.find_element(By.CSS_SELECTOR, '[data-qa="account-captcha-picture"]').is_displayed():
            solve_captcha(driver)
        else:
            print("Капча не видна, переходим к OTP/регистрации.")
    except TimeoutException:
        print("Капча не появилась, переходим к OTP/регистрации.")
    except Exception as e:
        print("Ошибка проверки капчи:", e)
    return driver, wait

def fill_name_details(driver, wait, csv_file="names.csv"):
    names = []
    try:
        with open(csv_file, newline='', encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    names.append((row[0].strip(), row[1].strip()))
    except Exception as e:
        print("Ошибка чтения CSV файла:", e)
        raise e
    if not names:
        raise Exception("CSV файл пуст или имеет неверный формат.")
    firstName, lastName = random.choice(names)
    print("Выбраны имя и фамилия:", firstName, lastName)
    first_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="firstName"]')))
    last_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="lastName"]')))
    simulate_typing(first_field, firstName, delay=0.2)
    simulate_typing(last_field, lastName, delay=0.2)
    driver.find_element(By.CSS_SELECTOR, '[data-qa="account-signup"] button').click()
    print("Данные регистрации (имя, фамилия) отправлены.")

def change_password(driver, wait, new_password="Karra228"):
    try:
        driver.get("https://hh.ru/applicant/settings")
        edit_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-qa="settings__password-edit"]')))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", edit_button)
        time.sleep(0.5)
        edit_button.click()
        newpwd_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '[data-qa="settings__password-newpassword"]')))
        confirm_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '[data-qa="settings__password-newpasswordconfirm"]')))
        simulate_typing(newpwd_input, new_password, delay=0.2)
        simulate_typing(confirm_input, new_password, delay=0.2)
        submit_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-qa="settings__password-submit"]')))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", submit_button)
        time.sleep(0.5)
        submit_button.click()
        print("Пароль успешно изменен на", new_password)
    except Exception as e:
        print("Ошибка при изменении пароля:", e)
        raise e

def save_password(phone_number, new_password="Karra228"):
    folder = "users"
    if not os.path.exists(folder):
        os.makedirs(folder)
    file_path = os.path.join(folder, f"{phone_number}.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"{phone_number}\n{new_password}\n")
    return file_path

def save_cookies(driver, phone_number, cookies_folder="cookies"):
    if not os.path.exists(cookies_folder):
        os.makedirs(cookies_folder)
    cookies = driver.get_cookies()
    file_path = os.path.join(cookies_folder, f"{phone_number}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print("Куки сохранены в", file_path)
    return file_path

def main(proxy_arg=None):
    try:
        if proxy_arg:
            selected_proxy = proxy_arg
            print("Используется прокси из параметра:", selected_proxy)
        else:
            args = parse_args()
            if args.proxy:
                selected_proxy = args.proxy
                print("Используется прокси из аргумента:", selected_proxy)
            else:
                raise Exception("Необходимо передать прокси через аргумент --proxy в формате host:port:username:password")
                
        parts = selected_proxy.split(':')
        if len(parts) != 4:
            raise Exception("Прокси должен быть в формате host:port:username:password")
        host, port, username, password = parts
        global PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS
        PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS = host, port, username, password

        for attempt in range(MAX_RETRIES):
            id_ = None
            driver = None
            try:
                print(f"Попытка #{attempt+1}")
                id_, phone_number = get_number()
                print(f"Куплен номер: {phone_number} | ID: {id_}")
                driver, wait = selenium_signup(phone_number)
                print("Ожидание кода через API...")
                otp_code = wait_for_code(id_, timeout=100)
                if not otp_code:
                    print("Код не получен. Отмена активации...")
                    driver.quit()
                    continue
                print(f"Код получен: {otp_code}")
                try:
                    otp_input = wait.until(EC.presence_of_element_located(
                        (By.CSS_SELECTOR, '[data-qa="otp-code-input"]')
                    ))
                    otp_input.clear()
                    otp_input.send_keys(otp_code)
                    print("Введен OTP код:", otp_code)
                    driver.find_element(
                        By.CSS_SELECTOR, '[data-qa="otp-code-submit"]'
                    ).click()
                except Exception as e:
                    print("Ошибка при заполнении OTP:", e)
                time.sleep(5)
                try:
                    wait.until(EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'input[name="firstName"]')
                    ))
                    wait.until(EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'input[name="lastName"]')
                    ))
                    fill_name_details(driver, wait, csv_file="names.csv")
                except Exception as e:
                    print("Ошибка при заполнении имени/фамилии:", e)
                    driver.quit()
                    continue
                time.sleep(5)
                try:
                    change_password(driver, wait, new_password="Karra228")
                except Exception as e:
                    print("Ошибка при изменении пароля, перезапуск процесса:", e)
                    driver.quit()
                    continue
                # Сохраняем файл с данными пароля (если нужен)
                created_file = save_password(phone_number, new_password="Karra228")
                # Сохраняем куки и получаем путь к файлу куки
                cookies_file = save_cookies(driver, phone_number)
                time.sleep(5)
                driver.quit()
                print("Создан файл куки:", cookies_file)
                return cookies_file
            except KeyboardInterrupt:
                print("Операция прервана пользователем.")
                if id_ is not None:
                    try:
                        set_status(id_, 8)
                        print("Номер отменен, деньги возвращены.")
                    except Exception as ex:
                        print("Ошибка при отмене номера:", ex)
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                return
            except Exception as e:
                print(f"Ошибка: {e}")
                if id_ is not None and "no such window: target window already closed" in str(e).lower():
                    try:
                        set_status(id_, 8)
                        print("Номер отменен, деньги возвращены.")
                    except Exception as ex:
                        print("Ошибка при отмене номера:", ex)
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
        print("Все попытки исчерпаны.")
    except KeyboardInterrupt:
        print("Операция прервана пользователем на этапе выбора прокси.")

if __name__ == '__main__':
    main()
