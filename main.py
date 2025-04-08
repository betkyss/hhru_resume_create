import os
import json
import register
import resume
import settings


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
    with open(proxy_file, "r") as f:
        proxies = [line.strip() for line in f if line.strip()]
    if not proxies:
        print("Нет доступных прокси в файле:", proxy_file)
        return None
    print("Доступные прокси:")
    for idx, proxy in enumerate(proxies, start=1):
        print(f"- {idx}: {proxy}")
    choice = input("Введите номер прокси: ").strip()
    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(proxies):
        print("Неверный выбор прокси.")
        return None
    return proxies[int(choice)-1]

def main():
    template = choose_template()
    if template is None:
        return
    proxy = choose_proxy()
    if proxy is None:
        return

    cookies = register.main(proxy_arg=proxy)
    resume.main(proxy_arg=proxy, template_arg=template, cookies_arg=cookies)
    settings.main(proxy_arg=proxy, cookies_arg=cookies, template_arg=template) 
    
if __name__ == "__main__":
    main()
