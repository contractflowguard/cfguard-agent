import os, requests, socket
import logging
import asyncio
logging.basicConfig(level=logging.INFO)

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
        "/help — подробная справка по формату файла"
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
    # /import <project_name>  (attach a CSV or XLSX file)
    # Expect a project name argument and an attached file
    if not ctx.args or not update.message.document:
        await update.message.reply_text(
            "Использование: /import <project_name> (приложите файл CSV или XLSX)"
        )
        return
    project = ctx.args[0]
    # Download the attached file
    file_obj = await update.message.document.get_file()
    content = await file_obj.download_as_bytearray()
    # Prepare multipart form-data
    files = {"file": (update.message.document.file_name, content)}
    data = {"name": project}
    try:
        resp = requests.post(f"{API_URL}/import", files=files, data=data, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        count = result.get("imported", "?")
        await update.message.reply_text(f"✔ Imported {count} tasks into project '{project}'")
    except requests.RequestException:
        await update.message.reply_text("Ошибка: не удалось импортировать данные на сервере.")

async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /report <project_name> [table|html]
    if not ctx.args:
        await update.message.reply_text("Использование: /report <project_name> [format]")
        return
    project = ctx.args[0]
    fmt = ctx.args[1] if len(ctx.args) > 1 else "table"
    try:
        resp = requests.get(f"{API_URL}/report", params={"project": project, "format": fmt}, timeout=5)
        resp.raise_for_status()
        report_text = resp.json().get("report", "")
        # if HTML and telegram supports, send as raw; else markdown
        if fmt.lower() == "html":
            await update.message.reply_text(report_text, parse_mode=None)
        else:
            await update.message.reply_text(f"```\n{report_text}\n```", parse_mode="Markdown")
    except requests.RequestException:
        await update.message.reply_text("Ошибка: не удалось получить отчёт от сервера.")

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
        "Бот понимает планы в формате CSV или XLSX с колонками:\n"
        "  • id — уникальный номер задачи\n"
        "  • task — название задачи\n"
        "  • planned_deadline — дата завершения по плану (YYYY-MM-DD)\n"
        "  • actual_completion_date — фактическая дата завершения (опционально)\n"
        "  • dependencies — через запятую id зависимостей\n"
        "  • status — статус задачи (опционально)\n\n"
        "Пример CSV:\n"
        "id,task,planned_deadline,actual_completion_date,dependencies,status\n"
        "1,Design,2025-06-01,, ,in_progress\n"
        "2,Build,2025-07-15,2025-07-20,1,done\n\n"
        "Используйте `/import <project_name>` и приложите файл."
    )
    await update.message.reply_text(text)

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