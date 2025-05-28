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
* `/report <project_name> [table|html|json]` — отчёт по проекту  
  *table* → `.txt`‑файл с summary-метриками (кол-во незапущенных задач, просрочки), ascii-графиком статусов, отмечены вехи (*).  
*html*  → `.html`‑файл с краткой сводкой, SVG-графиком по статусам, ключевыми метриками.  
  *json*  → `.json`‑файл с расчетными полями: дельта, статус, флаги, иерархия задач (через `parent_id`, `is_group`, `level`).  
  ⓘ Milestones (вехи) отмечены звёздочкой *.
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

```bash
# В начале отчёта будет краткая сводка с ключевыми показателями (выполнено, в работе, не начато, просрочено)
# Табличный отчёт (придёт файлом)
/report DEMO table

# Полный HTML‑отчёт (придёт файлом)
/report DEMO html

# JSON-отчёт с расчетами (придёт файлом)
/report DEMO json
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

## Лицензия

MIT License.
