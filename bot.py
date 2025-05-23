import os, requests, socket
import logging
import asyncio
logging.basicConfig(level=logging.INFO)

# ───── импорты и состояние ───────────────────────────────────────────
pending_imports: dict[int, str] = {}

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from datetime import datetime, UTC
from dateutil.parser import parse as parse_dt

# ───── конфигурация ───────────────────────────────────────────
# export TEST_TG_TOKEN (for CI smoke tests) or TG_TOKEN (for production) in environment
TOKEN = os.environ.get("TEST_TG_TOKEN") or os.environ.get("TG_TOKEN")
if not TOKEN:
    raise RuntimeError("Bot token is not set. Please set TEST_TG_TOKEN or TG_TOKEN.")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

def post_api(endpoint: str, payload: dict) -> bool:
    """
    Helper to POST to the backend API.
    Returns True on HTTP 2xx, False on any exception or non-2xx response.
    """
    try:
        r = requests.post(f"{API_URL}/{endpoint}", json=payload, timeout=1)
        r.raise_for_status()
        return True
    except requests.RequestException:
        return False

# ───── хэндлеры ────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/starttask <ID> [YYYY‑mm‑dd HH:MM] — начать задачу\n"
        "/stoptask <ID> [YYYY‑mm‑dd HH:MM] — остановить задачу\n"
        "/elapsed — показать отчёт с накопленным временем (минуты)\n"
        "/import <project_name> — инициировать импорт проекта\n"
        "/report <project_name> [table|html] — получить отчёт по проекту\n"
        "/list — список доступных проектов\n"
        "/reset — сбросить все данные в базе\n"
        "/help — подробная справка"
    )

async def starttask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Нужно: /starttask <ID> [YYYY-mm-dd HH:MM]")
        return
    task = ctx.args[0]
    ts = None
    if len(ctx.args) > 1:
        # combine all tokens after task as timestamp string
        ts_str = " ".join(ctx.args[1:])
        dt = parse_dt(ts_str)
        # ensure tzinfo for correct ISO output
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        ts = dt.isoformat()
    if not post_api("start", {"task": task, "ts": ts}):
        await update.message.reply_text("Ошибка: не удалось сохранить событие на сервере.")
        return
    await update.message.reply_text(f"▶ Start {task} @ {ts or 'now'}")

async def stoptask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Нужно: /stoptask <ID> [YYYY-mm-dd HH:MM]")
        return
    task = ctx.args[0]
    ts = None
    if len(ctx.args) > 1:
        ts_str = " ".join(ctx.args[1:])
        dt = parse_dt(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        ts = dt.isoformat()
    if not post_api("stop", {"task": task, "ts": ts}):
        await update.message.reply_text("Ошибка: не удалось сохранить событие на сервере.")
        return
    await update.message.reply_text(f"■ Stop  {task} @ {ts or 'now'}")

async def elapsed(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        data = requests.get(f"{API_URL}/elapsed", timeout=1).json()
    except (requests.RequestException, ValueError):
        await update.message.reply_text("Ошибка: не удалось получить отчёт от сервера.")
        return
    if not data:
        await update.message.reply_text("Пока пусто")
        return
    text = "\n".join(f"{row['task']:<12} {row['minutes']:>6}" for row in data)
    await update.message.reply_text(text)

async def cmd_import(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /import <project_name>")
        return
    project = ctx.args[0]
    pending_imports[update.effective_chat.id] = project
    await update.message.reply_text(
        f"Ок, жду CSV или XLSX файл для проекта '{project}'. Пришлите файл отдельным сообщением."
    )

async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /report <project_name> [table|html]
    if not ctx.args:
        await update.message.reply_text("Использование: /report <project_name> [format]")
        return
    project = ctx.args[0]
    fmt = ctx.args[1] if len(ctx.args) > 1 else "table"
    try:
        resp = requests.get(f"{API_URL}/report", params={"project": project, "format": fmt}, timeout=5)
        print(resp.status_code, resp.text)
        resp.raise_for_status()
        import tempfile
        if fmt.lower() == "json":
            import json
            records = resp.json().get("records", [])
            json_text = json.dumps(records, indent=2, ensure_ascii=False)
            with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as f:
                f.write(json_text)
                f.flush()
                f.seek(0)
                await update.message.reply_document(
                    document=f.name,
                    filename=f"{project}_report.json"
                )
            return
        report_text = resp.json().get("report", "")
        # For both HTML and table formats we send the report as a file
        if fmt.lower() in ("html", "table"):
            suffix = ".html" if fmt.lower() == "html" else ".txt"
            with tempfile.NamedTemporaryFile("w+", delete=False, suffix=suffix) as f:
                f.write(report_text)
                f.flush()
                f.seek(0)
                await update.message.reply_document(
                    document=f.name,
                    filename=f"{project}_report{suffix}"
                )
            return  # nothing more to do
        # fallback for other formats: send as chunked Markdown text
        max_len = 4000
        chunks = [report_text[i:i+max_len] for i in range(0, len(report_text), max_len)]
        for part in chunks:
            await update.message.reply_text(f"```\n{part}\n```", parse_mode="Markdown")
    except requests.RequestException:
        await update.message.reply_text("Ошибка: не удалось получить отчёт от сервера.")
    except Exception as ex:
        await update.message.reply_text(f"Ошибка отправки отчёта: {ex}")

async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /list
    try:
        resp = requests.get(f"{API_URL}/projects", timeout=5)
        resp.raise_for_status()
        names = resp.json().get("projects", [])
        if not names:
            text = "Проекты не найдены."
        else:
            text = "\n".join(names)
        await update.message.reply_text(text)
    except requests.RequestException:
        await update.message.reply_text("Ошибка: не удалось получить список проектов.")

async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /reset
    try:
        resp = requests.post(f"{API_URL}/reset", json={"force": True}, timeout=5)
        resp.raise_for_status()
        await update.message.reply_text("✔ Database reset")
    except requests.RequestException:
        await update.message.reply_text("Ошибка: не удалось сбросить базу данных.")

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "Подробная справка по командам:\n"
        "/starttask <ID> [YYYY‑mm‑dd HH:MM] — начать задачу (по умолчанию сейчас)\n"
        "/stoptask <ID> [YYYY‑mm‑dd HH:MM] — остановить задачу (по умолчанию сейчас)\n"
        "/elapsed — показать отчёт с накопленным временем (минуты)\n"
        "/import <project_name> — инициировать импорт проекта\n"
        "   1. Отправьте `/import <project_name>`\n"
        "   2. Затем пришлите CSV или XLSX файл с задачами\n"
        "/report <project_name> [table|html|json] — получить отчёт по проекту\n"
        "  • table — .txt‑файл с summary-метриками в начале (просрочки, незапущенные задачи), ascii-графиком статусов, вехи (*)\n"
        "  • html  — .html‑файл с футером-резюме, SVG-графиком, summary-метриками, вехи (*)\n"
        "  • json  — .json‑файл с расчетами: дельта, статус, флаги, is_milestone\n"
        "  ⓘ Вехи (milestones) отмечены звёздочкой *.\n"
        "В табличном и HTML отчёте теперь отображается иерархия задач (📁 группы, ⭐ вехи), определяемая по parent_id, level, is_group и др.\n"
        "/list — список доступных проектов\n"
        "/reset — сбросить все данные в базе\n"
        "/help — показать эту справку\n\n"
        "Формат файла (CSV/XLSX):\n"
        "  • project — код/имя проекта\n"
        "  • task_id — уникальный идентификатор задачи\n"
        "  • summary — краткое описание задачи\n"
        "  • planned_deadline — плановая дата завершения (YYYY‑MM‑DD)\n"
        "  • actual_completion_date — фактическая дата завершения (опционально)\n"
        "  • duration_days — продолжительность (дни, опционально)\n"
        "  • deps — зависимости (id через запятую, опционально)\n"
        "  • assignee — исполнитель (опционально)\n"
        "  • description — описание (опционально)\n"
        "  • result — результат выполнения (опционально)\n"
        "  • status — статус задачи (опционально)\n"
        "  • parent_id — ID родительской задачи (если есть)\n"
        "  • is_group — булево, обозначает группу задач (опционально)\n"
        "  • level — уровень вложенности (определяется автоматически при импорте)\n"
        "\n"
       "Примеры:\n"
        "  /report demo table — табличный отчёт с метриками\n"
        "  /report demo html — html-отчёт с футером\n"
        "  /report demo json — json-отчёт с аналитикой\n"
    )
    await update.message.reply_text(text)

from telegram.ext import MessageHandler, filters

async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in pending_imports:
        return  # ignore
    project = pending_imports.pop(chat_id)
    try:
        file_obj = await update.message.document.get_file()
        content = await file_obj.download_as_bytearray()
    except Exception:
        logging.exception("Ошибка при получении файла")
        await update.message.reply_text("Ошибка: не удалось получить файл")
        return
    files = {"file": (update.message.document.file_name, content)}
    data = {"name": project}
    try:
        resp = requests.post(f"{API_URL}/import", files=files, data=data, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        count = result.get("imported", '?')
        await update.message.reply_text(f"✔ Imported {count} tasks into project '{project}'")
    except requests.RequestException:
        logging.exception("Ошибка при импорте")
        await update.message.reply_text("Ошибка: не удалось импортировать данные на сервере.")

# ───── запуск ─────────────────────────────────────────────────
def main():
    """Run the Telegram bot with graceful shutdown."""
    # Build application
    app = ApplicationBuilder().token(TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("starttask",  starttask))
    app.add_handler(CommandHandler("stoptask",   stoptask))
    app.add_handler(CommandHandler("elapsed",     elapsed))
    app.add_handler(CommandHandler("import",   cmd_import))
    app.add_handler(CommandHandler("report",   cmd_report))
    app.add_handler(CommandHandler("list",     cmd_list))
    app.add_handler(CommandHandler("reset",    cmd_reset))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    try:
        # run_polling without internal signal handlers
        app.run_polling(stop_signals=None)
    finally:
        # Ensure all async cleanup completes to avoid 'coroutine was never awaited'
        asyncio.run(app.shutdown())
        print("Bot stopped.")

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        pass