import os
import re
import hashlib
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from playwright.async_api import async_playwright

# =========================
# ENV VARIABLES (Railway)
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHECK_INTERVAL = 60

if not BOT_TOKEN or not ADMIN_ID:
    raise RuntimeError("BOT_TOKEN or ADMIN_ID missing in environment variables")

# =========================
# PRICE BUCKETS
# =========================
PRICE_BUCKETS = [
    (0, 500),
    (500, 1000),
    (1000, 2000),
    (2000, 3000),
]

def bucket_label(lo, hi):
    if hi == 3000:
        return "₹2000–₹3000"
    if lo == 0:
        return "Below ₹500"
    return f"₹{lo}–₹{hi}"

def parse_price(text):
    m = re.search(r'₹?\s*([\d,]+)', text)
    return int(m.group(1).replace(",", "")) if m else None

# =========================
# STORAGE (RAM)
# =========================
categories = []
prev_stats = {}

# =========================
# FETCH CATEGORY DATA
# =========================
async def fetch_category_stats(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=60000)

        cards = await page.query_selector_all(
            "[data-testid*='product'], .product-card, .product-item"
        )

        prices = []

        for c in cards:
            for sel in [".price", ".product-price", "[data-testid*='price']"]:
                el = await c.query_selector(sel)
                if el:
                    txt = await el.inner_text()
                    val = parse_price(txt)
                    if val:
                        prices.append(val)
                        break

        await browser.close()

        total = len(prices)
        buckets = {bucket_label(lo, hi): 0 for lo, hi in PRICE_BUCKETS}

        for pr in prices:
            for lo, hi in PRICE_BUCKETS:
                if lo <= pr < hi:
                    buckets[bucket_label(lo, hi)] += 1
                    break

        return total, buckets

# =========================
# BOT COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "✅ Sheinverse CATEGORY Stock Bot (FULL ANALYTICS MODE)\n\n"
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
        prev_stats.pop(url, None)
        await update.message.reply_text("🗑 Category removed")
    except:
        await update.message.reply_text("❌ Invalid index")

# =========================
# BACKGROUND SCAN JOB
# =========================
async def scan_job(context: ContextTypes.DEFAULT_TYPE):
    for url in categories:
        try:
            total, buckets = await fetch_category_stats(url)
            now = datetime.now().strftime("%I:%M %p")

            if url not in prev_stats:
                prev_stats[url] = (total, buckets)
                continue

            prev_total, _ = prev_stats[url]

            if total != prev_total:
                diff = total - prev_total
                prev_stats[url] = (total, buckets)

                msg = [
                    "📈 SHEINVERSE – MEN STOCK INCREASED",
                    f"🕒 {now}",
                    "",
                    f"🆕 New SKUs added : {max(diff, 0)}",
                    f"Previous stock  : {prev_total}",
                    f"Current stock   : {total}",
                    ""
                ]

                for k, v in buckets.items():
                    msg.append(f"{k} : {v}")

                msg.append("\n🔥 Go and Buy !!!")

                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text="\n".join(msg)
                )

        except Exception:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="⚠️ Analytics scan failed"
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

    app.job_queue.run_repeating(scan_job, interval=CHECK_INTERVAL, first=10)

    app.run_polling()

if __name__ == "__main__":
    main()
