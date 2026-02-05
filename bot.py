import os
import hashlib
import requests
import re
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from playwright.async_api import async_playwright

BOT_TOKEN = os.getenv("8599224488:AAHConLJRAcg56Xf3C0nHZUZGvLsy_EWTpw")
ADMIN_ID = int(os.getenv("8434008747"))
CHECK_INTERVAL = 60

if not BOT_TOKEN or not ADMIN_ID:
    raise RuntimeError("BOT_TOKEN or ADMIN_ID missing in environment variables")



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
    m = re.search(r'₹?\s*([\d,]+)', text.replace(',', ''))
    return int(m.group(1)) if m else None

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

prev_stats = {}

prev_stats = {}

async def scan_job(context):
    for url in categories:
        try:
            total, buckets = await fetch_category_stats(url)
            now = datetime.now().strftime("%I:%M %p")

            if url not in prev_stats:
                prev_stats[url] = (total, buckets)
                continue   # ⚠️ return nahi

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

        except Exception as e:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="⚠️ Analytics scan failed"
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




