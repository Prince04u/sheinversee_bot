import os
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =========================
# ENV VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHECK_INTERVAL = 60

if not BOT_TOKEN or not ADMIN_ID:
    raise RuntimeError("BOT_TOKEN or ADMIN_ID missing")

# =========================
# STORAGE (RAM)
# =========================
categories = []
last_seen = {}

# =========================
# COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "✅ Sheinverse Stock Bot ONLINE (STABLE MODE)\n\n"
        "/addcategory <url>\n"
        "/list\n"
        "/remove <index>\n\n"
        "⚠️ Analytics disabled (safe mode)"
    )

async def addcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("❌ Category URL bhejo")
        return

    url = context.args[0]
    if url not in categories:
        categories.append(url)
        last_seen[url] = datetime.now()
        await update.message.reply_text("✅ Category added")
    else:
        await update.message.reply_text("ℹ️ Already added")

async def list_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not categories:
        await update.message.reply_text("📭 No categories added")
        return

    msg = "\n".join(f"{i+1}. {u}" for i, u in enumerate(categories))
    await update.message.reply_text(msg)

async def remove_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        idx = int(context.args[0]) - 1
        url = categories.pop(idx)
        last_seen.pop(url, None)
        await update.message.reply_text("🗑 Category removed")
    except:
        await update.message.reply_text("❌ Invalid index")

# =========================
# BACKGROUND JOB (PING)
# =========================
async def heartbeat(context: ContextTypes.DEFAULT_TYPE):
    # simple heartbeat to prove bot is alive
    pass

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addcategory", addcategory))
    app.add_handler(CommandHandler("list", list_items))
    app.add_handler(CommandHandler("remove", remove_item))

    app.job_queue.run_repeating(
        heartbeat,
        interval=CHECK_INTERVAL,
        first=10
    )

    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
