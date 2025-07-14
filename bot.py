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

def get_market_data(symbol):
    url = f"https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": symbol
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if not data:
            return None
            
        data = data[0]
        return {
            "price": data["current_price"],
            "change_24h": data["price_change_percentage_24h"],
            "market_cap_rank": data["market_cap_rank"],
            "total_volume": data["total_volume"],
            "market_cap": data["market_cap"],
            "price_change_24h": data["price_change_24h"]
        }
    except Exception as e:
        print(f"Error in get_market_data: {e}")
        return None

def get_return(current, target):
    return ((target - current) / current) * 100

def format_percentage(value):
    return f"{value:,.0f}"

async def send_price(update, context):
    price = get_price(SYMBOL)
    if price is None:
        await update.message.reply_text("could not fetch price")
        return

    ret = get_return(price, TARGET_PRICE)

    text = (
        f"$EMP Price Update:\n\n"
        f"🐻 bearish at ${price:.2f}\n"
        f"💰 price next week: ${TARGET_PRICE:,}\n"
        f"📈 predicted return: {format_percentage(ret)}%\n"
        f"👨 performance secured by Jpow\n\n"
        f"(financial advice)"
    )

    with open(IMAGE_PATH, "rb") as img:
        await update.message.reply_photo(photo=img, caption=text)

async def send_detailed_price(update, context):
    data = get_market_data(SYMBOL)
    if data is None:
        await update.message.reply_text("could not fetch price")
        return

    price = data["price"]
    ret = get_return(price, TARGET_PRICE)

    # Format large numbers with commas
    def format_number(num):
        return f"{num:,.0f}"

    text = (
        f"$EMP price update:\n\n"
        f"💸 currently bearish at: ${price:.2f}\n"
        f"{'🟢' if data['change_24h'] >= 0 else '🔴'} 24h change: ${data['price_change_24h']:.2f} ({data['change_24h']:.2f}%)\n\n"
        f"🎯 next week target: ${TARGET_PRICE:,}\n"
        f"📈 guaranteed return: {format_percentage(ret)}%\n\n"
        f"📊 market cap: ${format_number(data['market_cap'])}\n"
        f"🏆 rank: #{data['market_cap_rank']}\n"
        f"📈 24h volume: ${format_number(data['total_volume'])}\n\n"
        
        f"(this is absolutely financial advice)"
    )

    await update.message.reply_text(text)

async def handle_wen_commands(update, context):
    if update.message.text.startswith("/") and "wen" in update.message.text.lower():
        await update.message.reply_text("next week")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("billi", send_price))
app.add_handler(CommandHandler("price", send_detailed_price))
app.add_handler(MessageHandler(filters.COMMAND, handle_wen_commands))
app.run_polling()