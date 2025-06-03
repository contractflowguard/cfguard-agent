# cfguard‑agent

Лёгкий Telegram‑бот‑агент для фиксации событий *stop‑clock*.

## Установка зависимостей

```bash
python3 -m venv venv
source venv/bin/activate
pip install pyTelegramBotAPI httpx

> Требуемые библиотеки: `pyTelegramBotAPI`, `httpx` и др.
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

> Убедитесь, что у вас установлен Python 3.10+.

## Команды

* `/start` — краткая справка о возможностях бота
* `/starttask <ID> [YYYY‑mm‑dd HH:MM]` — начать задачу
* `/stoptask <ID> [YYYY‑mm‑dd HH:MM]` — остановить задачу
* `/elapsed` — показать отчёт с накопленным временем (в минутах)
* `/import <project_name>` — импорт плана проекта: приложите CSV или XLSX файл
* `/report <project_name> [table|html|json|text]` — отчёт по проекту  
  *table/text* → `.txt`‑файл с summary-метриками (кол-во незапущенных задач, просрочки), ascii-графиком статусов, отмечены вехи (*).  
*html*  → `.html`‑файл с краткой сводкой, SVG-графиком по статусам, ключевыми метриками.  
  *json*  → `.json`‑файл с расчетными полями: дельта, статус, флаги, иерархия задач (через `parent_id`, `is_group`, `level`).  
  ⓘ Milestones (вехи) отмечены звёздочкой *.
* `/diff <project_name> <base_snapshot_id> <new_snapshot_id>` — сравнение двух срезов плана. Ответ приходит в виде HTML-файла с отчётом различий.
* `/projects` — список доступных проектов

### Список срезов планов

Показать все срезы (snapshots) для всех проектов:
```bash
cfguard snapshots
```

Показать срезы только для одного проекта:
```bash
cfguard snapshots --project <project_name>
```

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

```bash
# В начале отчёта будет краткая сводка с ключевыми показателями (выполнено, в работе, не начато, просрочено)
# Табличный отчёт (придёт файлом)
/report DEMO table

# Полный HTML‑отчёт (придёт файлом)
/report DEMO html

# JSON-отчёт с расчетами (придёт файлом)
/report DEMO json
```

```bash
/diff demo 2024-05-01 2024-06-01 — сравнит срезы плана проекта demo между 1 мая и 1 июня 2024 года.
```

# В отчётах показываются ключевые метрики: завершённость, просрочка, статус задач, вехи

Бот теперь поддерживает многошаговый импорт:
1. Отправьте команду `/import <project_name>`
2. Затем в отдельном сообщении приложите CSV или XLSX файл с колонками:
   `project`, `task_id`, `summary`, `planned_deadline`, `actual_completion_date`, `duration_days`, `deps`, `assignee`, `description`, `result`, `status`.

Пример:
```
/import udacha
```
(потом отправьте файл `udacha_plan.csv`)

## Формат файла

CSV или XLSX с колонками:
- `project` — код/имя проекта
- `task_id` — уникальный идентификатор задачи
- `summary` — краткое описание задачи
- `planned_deadline` — плановая дата завершения (в формате YYYY‑MM‑DD)
- `actual_completion_date` — фактическая дата завершения (опционально)
- `duration_days` — продолжительность (дни, опционально)
- `planned_start` — плановая дата начала (в формате YYYY‑MM‑DD, опционально)
- `actual_start` — фактическая дата начала (в формате YYYY‑MM‑DD, опционально)
- `deps` — зависимости (id через запятую, опционально)
- `assignee` — исполнитель (опционально)
- `description` — описание (опционально)
- `result` — результат выполнения (опционально)
- `status` — статус задачи (опционально)

⚠️ Иерархия задач может быть определена автоматически по шаблону task_id (например, "1", "1.1", "2", "2.1", …).

Пример CSV:
```
project,task_id,summary,planned_deadline,actual_completion_date,duration_days,deps,assignee,description,result,status
udacha,1,Design,2025-06-01,,,,"",,"",,"in_progress"
udacha,2,Build,2025-07-15,2025-07-20,,,1,,"",,"done"
```

## Команда /diff

Команда `/diff` позволяет получить различия между двумя снапшотами проекта.
Использование:
```
/diff <project> <base_snapshot> <new_snapshot>
```

В ответ бот отправит HTML-файл с визуальным отчётом различий.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
