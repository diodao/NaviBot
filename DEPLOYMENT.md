**Инструкция по деплою NaviBot на Beget**

**1. Подготовка сервера (VPS Beget)**
1. **Подключение к серверу:**
• Откройте терминал на своём компьютере и выполните:

```
ssh root@<IP вашего VPS>
```

• Введите пароль, если потребуется.

1. **Настройка домена:**

• Убедитесь, что поддомен (например, bot.allneva.ru) создан и направлен на IP вашего VPS (например, 5.35.93.76).
• Проверьте, что SSL‑сертификат от Let’s Encrypt для поддомена установлен и корректен.


**2. Развёртывание проекта**

1. **Клонирование репозитория:**
• Если в директории /opt/navi_bot уже есть файлы, очистите её:

```
rm -rf /opt/navi_bot/*
```

• Перейдите в директорию:

```
mkdir -p /opt/navi_bot
cd /opt/navi_bot
```

• Клонируйте репозиторий:

```
git clone https://github.com/diodao/NaviBot.git .
```

**Создание виртуального окружения и установка зависимостей:**

```
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**3. Настройка автоматического запуска через systemd**

1. **Создайте unit‑файл:**

• Откройте редактор для создания файла /etc/systemd/system/navi_bot.service:

```
sudo nano /etc/systemd/system/navi_bot.service
```

• Вставьте следующее содержимое:

```
[Unit]

Description=NaviBot Telegram Bot Service
After=network.target

[Service]
User=root
WorkingDirectory=/opt/navi_bot
ExecStart=/opt/navi_bot/venv/bin/python telegram_bot.py
Restart=always
RestartSec=10
Environment="PORT=10000" 

[Install]
WantedBy=multi-user.target
```

• Сохраните файл и выйдите (Ctrl+O, Enter, Ctrl+X).


1. **Перезагрузите systemd и запустите сервис:**

```
sudo systemctl daemon-reload
sudo systemctl start navi_bot.service
sudo systemctl enable navi_bot.service
sudo systemctl status navi_bot.service
```

• Для просмотра логов:

```
sudo journalctl -u navi_bot.service -f
```

**4. Настройка вебхука (если используется)**

1. **Удаление существующего вебхука:**

• В коде бота (в файле telegram_bot.py) должна вызываться функция:

```
await application.bot.delete_webhook(drop_pending_updates=True)
```

1. **Установка нового вебхука:**

• Добавьте в код вызов:

```
await application.bot.set_webhook(url="https://bot.allneva.ru/<your_webhook_endpoint>")
```

• Убедитесь, что Flask‑сервер принимает запросы на указанном endpoint (например, /webhook).


**5. Обновление кода на сервере**

1. **На локальной машине внесите изменения, закоммитьте и отправьте их в GitHub:**

```
git add .
git commit -m "Описание изменений"
git push origin master
```

1. **На VPS выполните:**

```
cd /opt/navi_bot
git fetch origin
git reset --hard origin/master
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart navi_bot.service
```

