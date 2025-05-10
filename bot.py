import os, requests, socket, sqlite3
import logging
import asyncio
logging.basicConfig(level=logging.INFO)

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from datetime import datetime, UTC
import sqlite_utils
from dateutil.parser import parse as parse_dt

# ───── конфигурация ───────────────────────────────────────────
# export TEST_TG_TOKEN (for CI smoke tests) or TG_TOKEN (for production) in environment
TOKEN = os.environ.get("TEST_TG_TOKEN") or os.environ.get("TG_TOKEN")
if not TOKEN:
    raise RuntimeError("Bot token is not set. Please set TEST_TG_TOKEN or TG_TOKEN.")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
DB_PATH = os.getenv("BOT_DB_PATH","cfguard.db")
# Ensure the directory for the bot database exists
db_dir = os.path.dirname(DB_PATH)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)

conn    = sqlite3.connect(DB_PATH, check_same_thread=False)
DB      = sqlite_utils.Database(conn)

def post_api(endpoint: str, payload: dict) -> bool:
    try:
        r = requests.post(f"{API_URL}/{endpoint}", json=payload, timeout=1)
        r.raise_for_status()
        return True
    except (requests.RequestException, socket.error):
        return False

def write_local(task: str, event: str, ts: str = None):
    if ts is None:
        ts = datetime.now(UTC).isoformat()
    DB["log"].insert({"task": task, "event": event, "ts": ts})

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
        write_local(task, "start", ts)
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
        write_local(task, "stop", ts)
    await update.message.reply_text(f"■ Stop  {task} @ {ts or 'now'}")

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
    """Run the Telegram bot with graceful shutdown."""
    # Build application
    app = ApplicationBuilder().token(TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("starttask",  starttask))
    app.add_handler(CommandHandler("stoptask",   stoptask))
    app.add_handler(CommandHandler("report",     report))

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