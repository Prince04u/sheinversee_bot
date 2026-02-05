import os
import re
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from playwright.async_api import async_playwright

# =========================
# ENV VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHECK_INTERVAL = 60  # seconds

if not BOT_TOKEN or not ADMIN_ID:
    raise RuntimeError("BOT_TOKEN or ADMIN_ID missing")

# =========================
# STORAGE
# =========================
categories = []
last_count = {}

# =========================
# UTILS
# =========================
def extract_prices(text: str):
    prices = re.findall(r"₹\s?([\d,]+)", text)
    return [int(p.replace(",", "")) for p in prices]

# =========================
# PLAYWRIGHT SCAN
# =========================
async def scan_category(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
        )

        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(4000)

        content = await page.content()
        await browser.close()

        prices = extract_prices(content)
        return len(prices), prices

# =========================
# COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "🔥 Sheinverse Bot ONLINE (FULL ANALYTICS MODE)\n\n"
        "/addcategory <url>\n"
        "/list\n"
        "/remove <index>\n\n"
        "⚠️ Aggressive mode (site may block sometimes)"
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
        last_count.pop(url, None)
        await update.message.reply_text("🗑 Removed")
    except:
        await update.message.reply_text("❌ Invalid index")

# =========================
# BACKGROUND JOB
# =========================
async def scan_job(context: ContextTypes.DEFAULT_TYPE):
    for url in categories:
        try:
            count, prices = await scan_category(url)

            if last_count[url] is None:
                last_count[url] = count
                return

            if count != last_count[url]:
                diff = count - last_count[url]
                last_count[url] = count

                now = datetime.now().strftime("%I:%M %p")

                msg = [
                    "📈 SHEINVERSE – CATEGORY UPDATE",
                    f"🕒 {now}",
                    "",
                    f"Previous stock : {count - diff}",
                    f"Current stock  : {count}",
                    f"Change         : {diff:+}",
                ]

                if prices:
                    msg.append("")
                    msg.append(f"Min price ₹{min(prices)}")
                    msg.append(f"Max price ₹{max(prices)}")

                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text="\n".join(msg)
                )

        except Exception as e:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠️ Analytics failed:\n{str(e)[:300]}"
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

    print("Bot started (FULL ANALYTICS MODE)")
    app.run_polling()

if __name__ == "__main__":
    main()
