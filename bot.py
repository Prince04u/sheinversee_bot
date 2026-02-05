import hashlib
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import BOT_TOKEN, ADMIN_ID, CHECK_INTERVAL

# Storage (RAM)
categories = []
last_fingerprint = {}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def page_fingerprint(html: str) -> str:
    text = html.lower()

    keywords = [
        "out of stock",
        "sold out",
        "add to bag",
        "add to cart",
        "notify me",
        "in stock"
    ]

    signal = []
    for k in keywords:
        signal.append(f"{k}:{text.count(k)}")

    # multiple chunks fingerprint
    chunk = text[:2000] + text[len(text)//2:len(text)//2+2000]

    base = f"{len(text)}|{'|'.join(signal)}|{chunk}"
    return hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "✅ Sheinverse CATEGORY Stock Bot (Hybrid Safe Mode)\n\n"
        "/addcategory <url>\n"
        "/list\n"
        "/remove <index>\n\n"
        "⏱ Check interval: 60 seconds"
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
        await update.message.reply_text("✅ Category added")
    else:
        await update.message.reply_text("ℹ️ Category already added")

async def list_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not categories:
        await update.message.reply_text("📭 No categories added")
        return
    msg = "\n".join([f"{i+1}. {u}" for i, u in enumerate(categories)])
    await update.message.reply_text(msg)

async def remove_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        idx = int(context.args[0]) - 1
        url = categories.pop(idx)
        last_fingerprint.pop(url, None)
        await update.message.reply_text("🗑 Removed")
    except:
        await update.message.reply_text("❌ Invalid index")

async def scan_job(context: ContextTypes.DEFAULT_TYPE):
    for url in categories:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            html = r.text or ""
            fp = page_fingerprint(html)

            if last_fingerprint.get(url) is None:
                # First scan – baseline set
                last_fingerprint[url] = fp
            else:
                if fp != last_fingerprint[url]:
                    last_fingerprint[url] = fp
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=(
                            "🚨 CATEGORY UPDATE DETECTED\n"
                            "Possible new stock / change\n\n"
                            f"{url}"
                        )
                    )
        except Exception:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "⚠️ Scan error on category\n"
                    f"{url}"
                )
            )

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addcategory", addcategory))
    app.add_handler(CommandHandler("list", list_items))
    app.add_handler(CommandHandler("remove", remove_item))

    # Background job every 60 seconds
    app.job_queue.run_repeating(scan_job, interval=CHECK_INTERVAL, first=10)

    app.run_polling()

if __name__ == "__main__":
    main()
