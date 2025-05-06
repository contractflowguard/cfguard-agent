# cfguard‑agent

Лёгкий Telegram‑бот‑агент для фиксации событий *stop‑clock*.

## Установка

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Настройка

1. Скопируйте пример файла окружения:
   ```bash
   cp .env.example .env
   ```
2. Откройте `.env` и укажите:
   ```env
   TG_TOKEN="123456:ABCDEF…"
   API_URL=http://127.0.0.1:8000
   BOT_DB_PATH=./cfguard.db    # по умолчанию cfguard.db в рабочем каталоге
   ```
   
   При первом запуске бот автоматически создаст каталог для файла базы, указанного в `BOT_DB_PATH`, если такой каталог отсутствует.

## Запуск

```bash
python bot.py
```

Команды:
* `/starttask TASK‑ID [YYYY‑mm‑dd HH:MM]`
* `/stoptask  TASK‑ID [YYYY‑mm‑dd HH:MM]`
* `/report` — выводит задержки в минутах для каждой задачи.

## Примеры использования

```bash
# Фиксация вехи с указанием времени
/starttask DEMO-1 2025-05-10 14:32
/stoptask  DEMO-1 2025-05-10 15:45

# Получение отчёта
/report
```

## Лицензия

MIT License.
