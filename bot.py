import os
import hashlib
import requests
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =========================
# ENV VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHECK_INTERVAL = 60  # seconds

if not BOT_TOKEN or not ADMIN_ID:
    raise RuntimeError("BOT_TOKEN or ADMIN_ID missing")

# =========================
# STORAGE (RAM)
# =========================
categories = []
last_fingerprint = {}
last_count = {}

# =========================
# HTTP
# =========================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def make_fingerprint(html: str) -> str:
    text = html.lower()

    signals = [
        "out of stock",
        "sold out",
        "add to bag",
        "add to cart",
        "notify me",
        "size"
    ]

    sig_count = "|".join(f"{s}:{text.count(s)}" for s in signals)
    core = f"{len(text)}|{sig_count}|{text[:1500]}|{text[-1500:]}"
    return hashlib.sha256(core.encode("utf-8", errors="ignore")).hexdigest()

def estimate_count(html: str) -> int:
    # very rough but effective signal
    return html.lower().count("product")

# =========================
# COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "✅ SHEINVERSE CATEGORY BOT ONLINE (HYBRID MODE)\n\n"
        "/addcategory <url>\n"
        "/list\n"
        "/remove <index>\n\n"
        "🔔 Cloud-safe category change alerts enabled"
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
        last_fingerprint[url] = None
        last_count[url] = None
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
        last_fingerprint.pop(url, None)
        last_count.pop(url, None)
        await update.message.reply_text("🗑 Category removed")
    except:
        await update.message.reply_text("❌ Invalid index")

# =========================
# BACKGROUND SCAN
# =========================
async def scan_job(context: ContextTypes.DEFAULT_TYPE):
    for url in categories:
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            html = r.text

            fp = make_fingerprint(html)
            count = estimate_count(html)

            if last_fingerprint[url] is None:
                last_fingerprint[url] = fp
                last_count[url] = count
                continue

            if fp != last_fingerprint[url] or count != last_count[url]:
                last_fingerprint[url] = fp
                last_count[url] = count

                now = datetime.now().strftime("%I:%M %p")

                msg = (
                    "🚨 SHEINVERSE CATEGORY UPDATED\n"
                    f"🕒 {now}\n\n"
                    "Stock count changed\n"
                    "Possible new products added with size need\n\n"
                    f"{url}"
                )

                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=msg
                )

        except Exception:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="⚠️ Category scan failed (network issue)"
            )

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addcategory", addcategory))
    app.add_handler(CommandHandler("list", list_items))
    app.add_handler(CommandHandler("remove", remove_item))

    app.job_queue.run_repeating(scan_job, interval=CHECK_INTERVAL, first=15)

    print("Sheinverse hybrid bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
