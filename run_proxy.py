import subprocess
import time

# 1. Читаем прокси
with open("proxies.txt", "r", encoding="utf-8") as f:
    proxies = [line.strip() for line in f if line.strip()]

# 2. Выбор прокси
print("Выберите прокси:")
for i, p in enumerate(proxies, 1):
    print(f"{i}. {p}")
index = int(input("Введите номер: ")) - 1

ip, port, user, pwd = proxies[index].split(":")

# 3. Запуск proxy-server.js с аргументами
args = ["node", "proxy-server.js", ip, port, user, pwd]
print(f"\n🚀 Запуск локального прокси через: {ip}:{port}")
proxy_proc = subprocess.Popen(args)

# 4. Ждём и даём поработать
print("Локальный прокси запущен на 127.0.0.1:8899")
print("Нажмите Enter, чтобы остановить...")
input()

proxy_proc.terminate()

