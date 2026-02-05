import os
import asyncio
from datetime import datetime
from collections import defaultdict

from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from playwright.async_api import async_playwright

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

PROXY_HOST = os.getenv("PROXY_HOST")
PROXY_PORT = os.getenv("PROXY_PORT")
PROXY_USER = os.getenv("PROXY_USER")
PROXY_PASS = os.getenv("PROXY_PASS")

CHECK_INTERVAL = 120  # 2 min (safe)

categories = []
last_counts = {}

PRICE_BUCKETS = [
    (0, 500),
    (500, 1000),
    (1000, 2000),
    (2000, 3000),
]

def bucket_label(lo, hi):
    if lo == 0:
        return "Below ₹500"
    return f"₹{lo}–₹{hi}"

async def fetch_category(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={
                "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
                "username": PROXY_USER,
                "password": PROXY_PASS,
            },
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(5000)

        html = await page.content()
        await browser.close()

        soup = BeautifulSoup(html, "html.parser")
        products = soup.select("[data-testid*='product'], .product-card")

        stock = []
        for p in products:
            price_el = p.select_one(".price, .product-price")
            size_els = p.select("[data-testid*='size'], .size")

            if not price_el:
                continue

            price = int("".join(filter(str.isdigit, price_el.text)))
            sizes = [s.text.strip() for s in size_els if s.text.strip()]
            stock.append((price, sizes))

        return stock

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        "✅ SHEINVERSE PRO STOCK BOT (OPTION C)\n\n"
        "/addcategory <url>\n"
        "/list\n"
        "/remove <index>\n\n"
        "🔥 Exact stock + size analytics enabled"
    )

async def addcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    url = context.args[0]
    if url not in categories:
        categories.append(url)
        await update.message.reply_text("✅ Category added")

async def list_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "\n".join(f"{i+1}. {u}" for i, u in enumerate(categories))
    await update.message.reply_text(msg or "No categories")

async def scan_job(context):
    for url in categories:
        stock = await fetch_category(url)
        total = len(stock)

        if url not in last_counts:
            last_counts[url] = total
            continue

        prev = last_counts[url]
        if total != prev:
            last_counts[url] = total
            now = datetime.now().strftime("%I:%M %p")

            buckets = defaultdict(int)
            for price, _ in stock:
                for lo, hi in PRICE_BUCKETS:
                    if lo <= price < hi:
                        buckets[bucket_label(lo, hi)] += 1
                        break

            msg = [
                "📈 SHEINVERSE – MEN STOCK UPDATED",
                f"🕒 {now}",
                "",
                f"Previous stock : {prev}",
                f"Current stock  : {total}",
                "",
            ]

            for k, v in buckets.items():
                msg.append(f"{k} : {v}")

            msg.append("\n🔥 Go and Buy !!!")

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="\n".join(msg)
            )

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addcategory", addcategory))
    app.add_handler(CommandHandler("list", list_items))

    app.job_queue.run_repeating(scan_job, interval=CHECK_INTERVAL, first=30)
    app.run_polling()

if __name__ == "__main__":
    main()
