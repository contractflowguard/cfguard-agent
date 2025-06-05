import os, requests, socket
import logging
import asyncio

# For set_snapshot_status_via_api
import httpx

API_BASE_URL = "http://localhost:8000"  # Adjust to match actual CFG API base URL
logging.basicConfig(level=logging.INFO)

# ───── импорты и состояние ───────────────────────────────────────────
pending_imports: dict[int, str] = {}

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
)
from datetime import datetime, UTC
from dateutil.parser import parse as parse_dt
import tempfile

API_URL = os.getenv("API_URL", API_BASE_URL)
TOKEN = os.environ.get("TEST_TG_TOKEN") or os.environ.get("TG_TOKEN")
if not TOKEN:
    raise RuntimeError("Bot token is not set. Please set TEST_TG_TOKEN or TG_TOKEN.")

async def handle_diff(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        args = ctx.args
        if len(args) != 3:
            await update.message.reply_text("❗ Пример использования:\n/diff PROJECT BASE_SNAPSHOT NEW_SNAPSHOT")
            return
        project, base, new = args

        url = f"{API_URL}/diff?project={project}&left={base}&right={new}&format=html"
        response = requests.get(url)
        if response.status_code == 200:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
                tmp.write(response.content)
                tmp_path = tmp.name
            with open(tmp_path, 'rb') as f:
                await update.message.reply_document(document=f, filename=f"diff_{project}_{base}_vs_{new}.html")
        else:
            await update.message.reply_text(f"Ошибка: {response.status_code}\n{response.text}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при выполнении diff:\n{e}")

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/starttask <ID> [YYYY‑mm‑dd HH:MM] — начать задачу\n"
        "/stoptask <ID> [YYYY‑mm‑dd HH:MM] — остановить задачу\n"
        "/elapsed — показать отчёт с накопленным временем (минуты)\n"
        "/import <project> — инициировать импорт проекта\n"
        "/report <project> [table|html|json] — получить отчёт по проекту\n"
        "/diff <project> <base_snapshot> <new_snapshot> — сравнить два среза\n"
        "/projects — список доступных проектов\n"
        "/reset — сбросить все данные в базе\n"
        "/help — подробная справка\n"
        "/snapshots — list all snapshots for all projects  \n"
        "/snapshots --project <project> — list snapshots for a specific project"
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
        await update.message.reply_text("Использование: /import <project>")
        return
    project = ctx.args[0]
    pending_imports[update.effective_chat.id] = project
    await update.message.reply_text(
        f"Ок, жду CSV или XLSX файл для проекта '{project}'. Пришлите файл отдельным сообщением."
    )

async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /report <project> [table|html]
    if not ctx.args:
        await update.message.reply_text("Использование: /report <project> [format]")
        return
    project = ctx.args[0]
    fmt = ctx.args[1] if len(ctx.args) > 1 else "table"
    try:
        resp = requests.get(f"{API_URL}/report", params={"project": project, "format": fmt}, timeout=5)
        print(resp.status_code, resp.text)
        resp.raise_for_status()
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

async def cmd_projects(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # /projects
    try:
        resp = requests.get(f"{API_URL}/projects", timeout=5)
        resp.raise_for_status()
        projects = resp.json().get("projects", [])
        if not projects:
            text = "Проекты не найдены."
        else:
            text = "\n".join(projects)
        await update.message.reply_text(text)
    except requests.RequestException:
        await update.message.reply_text("Ошибка: не удалось получить список проектов.")

async def cmd_snapshots(update, context):
    args = context.args
    if len(args) == 2 and args[0] == "--project":
        project = args[1]
        result = requests.get(f"{API_URL}/projects/{project}/snapshots")
        if result.status_code == 200:
            snapshots = result.json().get("snapshots", [])
            message = f"📂 {project}\n"
            for snap in snapshots:
                message += f"  • {snap}\n"
        else:
            message = f"❌ Failed to fetch snapshots for project '{project}'"
        return await update.message.reply_text(message)
    else:
        result = requests.get(f"{API_URL}/projects")
        if result.status_code == 200:
            message = ""
            projects = result.json().get("projects", [])
            for project in projects:
                snap_resp = requests.get(f"{API_URL}/projects/{project}/snapshots")
                if snap_resp.status_code == 200:
                    for snap in snap_resp.json().get("snapshots", []):
                        message += f"📂 {project}\n"
                        message += f"  • {snap}\n"
        else:
            message = "❌ Failed to fetch project list"
        return await update.message.reply_text(message)

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
        "/import <project> — инициировать импорт проекта\n"
        "   1. Отправьте `/import <project>`\n"
        "   2. Затем пришлите CSV или XLSX файл с задачами\n"
        "/report <project> [table|html|json] — получить отчёт по проекту\n"
        "  • table — .txt‑файл с summary-метриками, ascii-графиком и вехами (*)\n"
        "  • html  — .html‑файл с футером, SVG-графиком и вехами (*)\n"
        "  • json  — enriched-данные с аналитикой\n"
        "/diff <project> <base_snapshot> <new_snapshot> — сравнение двух срезов\n"
        "  • Возвращает HTML‑отчёт с различиями задач между срезами\n"
        "/snapshots — list all snapshots for all projects  \n"
        "/snapshots --project <project> — list snapshots for a specific project\n"
        "/projects — список доступных проектов\n"
        "/reset — сбросить все данные в базе\n"
        "/help — показать эту справку\n\n"
        "Формат файла (CSV/XLSX): если `parent_id` и `level` не заданы, иерархия определяется по шаблону ID\n"
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
        "\n"
        "Примеры:\n"
        "  /report demo table — табличный отчёт с метриками\n"
        "  /report demo html — html-отчёт с футером\n"
        "  /diff demo v1 v2 — HTML‑отчёт с разницей между v1 и v2"
    )
    await update.message.reply_text(text)

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
    data = {"project": project}
    try:
        resp = requests.post(f"{API_URL}/import", files=files, data=data, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        count = result.get("imported", '?')
        # Get snapshot_id if present
        snapshot_id = result.get("snapshot_id")
        await update.message.reply_text(f"✔ Imported {count} tasks into project '{project}'")
        # Set snapshot status if caption is present and snapshot_id is available
        if snapshot_id and update.message.caption:
            status = update.message.caption.strip()
            set_snapshot_status_via_api(project, snapshot_id, status)
    except requests.RequestException:
        logging.exception("Ошибка при импорте")
        await update.message.reply_text("Ошибка: не удалось импортировать данные на сервере.")
# Set snapshot status via API
def set_snapshot_status_via_api(project: str, snapshot_id: str, status: str) -> None:
    response = httpx.put(f"{API_URL}/snapshot/status", json={
        "project": project,
        "snapshot_id": snapshot_id,
        "status": status
    })
    response.raise_for_status()

# Async handler for /setstatus command
async def cmd_setstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text("Usage: /setstatus <project> <snapshot_id> <status text>")
            return
        project = args[0]
        snapshot_id = args[1]
        status = " ".join(args[2:])
        set_snapshot_status_via_api(project, snapshot_id, status)
        await update.message.reply_text(f"✅ Status set for {project}/{snapshot_id}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error setting status: {e}")

def post_api(endpoint: str, payload: dict) -> bool:
    try:
        resp = requests.post(f"{API_URL}/{endpoint}", json=payload, timeout=5)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        logging.error(f"API request failed: {e}")
        return False

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
    app.add_handler(CommandHandler("projects",     cmd_projects))
    app.add_handler(CommandHandler("snapshots", cmd_snapshots))
    app.add_handler(CommandHandler("reset",    cmd_reset))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("diff",     handle_diff))
    app.add_handler(CommandHandler("setstatus", cmd_setstatus))
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