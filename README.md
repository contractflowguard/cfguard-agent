# cfguard‑agent

Лёгкий Telegram‑бот‑агент для фиксации событий *stop‑clock*.

```bash
pip install -r requirements.txt
export TG_TOKEN="123:ABC" API_URL="http://127.0.0.1:8000"
python bot.py
```

Команды:
* `/starttask TASK‑ID [YYYY‑mm‑dd HH:MM]`
* `/stoptask  TASK‑ID [YYYY‑mm‑dd HH:MM]`
* `/report` — свернуть сводку.

MIT License.
