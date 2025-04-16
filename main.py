import os
import json
import register
import resume
import settings
import subprocess
import time


def choose_template(folder="templates"):
    templates = [f for f in os.listdir(folder) if f.endswith((".xlsx", ".xls"))]
    if not templates:
        print("Нет шаблонов в папке:", folder)
        return None
    print("Доступные шаблоны:")
    for idx, t in enumerate(templates, start=1):
        print(f"- {idx}: {t}")
    choice = input("Введите номер шаблона: ").strip()
    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(templates):
        print("Неверный выбор шаблона.")
        return None
    return os.path.join(folder, templates[int(choice)-1])


def choose_proxy(proxy_file="proxies.txt"):
    if not os.path.exists(proxy_file):
        print("Файл прокси не найден:", proxy_file)
        return None

    with open(proxy_file, "r", encoding="utf-8") as f:
        proxies = [line.strip() for line in f if line.strip()]

    if not proxies:
        print("Нет доступных прокси в файле:", proxy_file)
        return None

    print("Выберите прокси:")
    for i, p in enumerate(proxies, 1):
        print(f"{i}. {p}")

    index = int(input("Введите номер: ")) - 1
    if index < 0 or index >= len(proxies):
        print("Неверный номер.")
        return None

    ip, port, user, pwd = proxies[index].split(":")

    args = ["node", "proxy-server.js", ip, port, user, pwd]
    print(f"\n🚀 Запуск локального прокси через: {ip}:{port}")
    proxy_proc = subprocess.Popen(args)
    time.sleep(2)  # ждём пока поднимется

    print("Локальный прокси запущен на 127.0.0.1:8899")
    
    # Возвращаем сам прокси-строку и процесс, чтобы можно было использовать и завершить
    return f"{ip}:{port}:{user}:{pwd}", proxy_proc

def main():
    template = choose_template()
    if template is None:
        return
    proxy = choose_proxy()
    if proxy is None:
        return

    cookies = register.main()
    # cookies = './cookies/79805637571.json'
    resume.main(template_arg=template, cookies_arg=cookies)
    # settings.main(cookies_arg=cookies, template_arg=template) 
    
if __name__ == "__main__":
    main()
