# run-proxy.py
import subprocess
import sys

def main():
    try:
        with open("proxies.txt", "r", encoding="utf-8") as f:
            proxies = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Файл proxies.txt не найден")
        sys.exit(1)

    if not proxies:
        print("Список прокси пуст")
        sys.exit(1)

    print("Выберите прокси:")
    for i, p in enumerate(proxies, 1):
        print(f"{i}. {p}")
    try:
        idx = int(input("Введите номер: ")) - 1
        ip, port, user, pwd = proxies[idx].split(":")
    except (ValueError, IndexError):
        print("Неверный выбор")
        sys.exit(1)

    args = ["node", "proxy-server.js", ip, port, user, pwd]
    print(f"\nЗапускаем локальный прокси через {ip}:{port} …")
    try:
        proc = subprocess.Popen(args)
    except FileNotFoundError:
        print("Не удалось запустить node. Убедитесь, что Node.js установлена и доступна в PATH.")
        sys.exit(1)

    print("Локальный прокси запущен на 127.0.0.1:8899")
    input("Нажмите Enter для остановки…")
    proc.terminate()
    proc.wait()
    print("Прокси остановлен")

if __name__ == "__main__":
    main()

