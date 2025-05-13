# cfguard‑agent

Лёгкий Telegram‑бот‑агент для фиксации событий *stop‑clock*.

## Установка

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.lock
```

## Настройка

1. Скопируйте пример файла окружения:
   ```bash
   cp .env.example .env
   ```
2. Откройте `.env` и укажите необходимые переменные, например:
   ```env
   TG_TOKEN="123456:ABCDEF…"
   API_URL=http://127.0.0.1:8000
   ```

## Запуск

```bash
python bot.py
```

Команды:
* `/start` — краткая справка о возможностях бота
* `/starttask <ID> [YYYY‑mm‑dd HH:MM]` — начать задачу
* `/stoptask <ID> [YYYY‑mm‑dd HH:MM]` — остановить задачу
* `/elapsed` — показать отчёт с накопленным временем (в минутах)
* `/import <project_name>` — импорт плана проекта: приложите CSV или XLSX файл
* `/report <project_name> [table|html]` — получить отчёт по проекту
* `/list` — список доступных проектов
* `/reset` — сброс базы данных
* `/help` — подробная справка по структуре файла

## Примеры использования

```bash
# Фиксация вехи с указанием времени
/starttask DEMO-1 2025-05-10 14:32
/stoptask  DEMO-1 2025-05-10 15:45

# Получение отчёта
/elapsed
```

Бот теперь умеет принимать план-файл в команде /import. Отправьте сообщение:
/import my-project
приложив CSV или XLSX файл с колонками:
`id`, `task`, `planned_deadline`, `actual_completion_date` (опц.), `dependencies`, `status` (опц.).

## Формат файла

CSV или XLSX с колонками:
- `id` — уникальный идентификатор задачи
- `task` — название задачи
- `planned_deadline` — плановая дата завершения (в формате YYYY‑MM‑DD)
- `actual_completion_date` — фактическая дата завершения (опционально)
- `dependencies` — список зависимостей, через запятую
- `status` — текущий статус задачи (опционально)

Пример CSV:
```
id,task,planned_deadline,actual_completion_date,dependencies,status  
1,Design,2025-06-01,, ,in_progress  
2,Build,2025-07-15,2025-07-20,1,done
```

## Лицензия

MIT License.
