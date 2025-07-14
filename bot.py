from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
import requests
import dotenv
import os

dotenv.load_dotenv()

TOKEN = os.getenv("TOKEN")
SYMBOL = "empyreal"
TARGET_PRICE = 3333
IMAGE_PATH = "logo.jpg"

def get_price(symbol):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd"
    try:
        response = requests.get(url).json()
        return response[symbol]["usd"]
    except:
        return None

def get_return(current, target):
    return ((target - current) / current) * 100

def format_percentage(value):
    return f"{value:,.2f}"

async def send_price(update, context):
    price = get_price(SYMBOL)
    if price is None:
        await update.message.reply_text("could not fetch price")
        return

    ret = get_return(price, TARGET_PRICE)

    text = (
        f"$EMP Price Update:\n\n"
        f"🐻 bearish at ${price:.2f}\n"
        f"💰 price next week: ${TARGET_PRICE:.2f}\n"
        f"📈 predicted return: {format_percentage(ret)}%\n"
        f"👨 performance secured by Jpow\n\n"
        f"(not financial advice)"
    )

    with open(IMAGE_PATH, "rb") as img:
        await update.message.reply_photo(photo=img, caption=text)

async def handle_wen_commands(update, context):
    if update.message.text.startswith("/") and "wen" in update.message.text.lower():
        await update.message.reply_text("next week")


app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("billi", send_price))
app.add_handler(MessageHandler(filters.COMMAND, handle_wen_commands))
app.run_polling()
