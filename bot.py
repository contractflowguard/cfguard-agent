import os, asyncio, requests, socket
import logging
logging.basicConfig(level=logging.INFO)

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from datetime import datetime, UTC
import sqlite_utils

# ───── конфигурация ───────────────────────────────────────────
TOKEN   = os.environ["TG_TOKEN"]               # экспортируйте в shell
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
DB      = sqlite_utils.Database("cfguard.db")

def post_api(endpoint: str, payload: dict) -> bool:
    try:
        r = requests.post(f"{API_URL}/{endpoint}", json=payload, timeout=1)
        r.raise_for_status()
        return True
    except (requests.RequestException, socket.error):
        return False

def write_local(task: str, event: str):
    DB["log"].insert({"task": task, "event": event,
                      "ts": datetime.now(UTC).isoformat()})

# ───── хэндлеры ────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/starttask <ID>\n"
        "/stoptask <ID>\n"
        "/report"
    )

async def starttask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Нужно: /starttask <ID>")
        return
    task = ctx.args[0]
    if not post_api("start", {"task": task}):
        write_local(task, "start")
    await update.message.reply_text(f"▶ Start {task}")

async def stoptask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Нужно: /stoptask <ID>")
        return
    task = ctx.args[0]
    if not post_api("stop", {"task": task}):
        write_local(task, "stop")
    await update.message.reply_text(f"■ Stop {task}")

async def report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        data = requests.get(f"{API_URL}/report", timeout=1).json()
    except (requests.RequestException, ValueError):
        data = list(DB.query("SELECT task, 0.0 AS minutes FROM log GROUP BY task"))
    if not data:
        await update.message.reply_text("Пока пусто")
        return
    text = "\n".join(f"{row['task']:<12} {row['minutes']:>6}" for row in data)
    await update.message.reply_text(text)

# ───── запуск ─────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("starttask",  starttask))
    app.add_handler(CommandHandler("stoptask",   stoptask))
    app.add_handler(CommandHandler("report",     report))
    app.run_polling()

if __name__ == "__main__":
    try:
        main()  # run_polling() handles its own loop
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")
    