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
        print(f"API Response for {symbol}: {response.status_code}")
        print(f"Response text: {response.text[:200]}...")
        
        data = response.json()
        if not data:
            print(f"No data returned for {symbol}")
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
        print(f"Error in get_market_data for {symbol}: {e}")
        return None

def get_return(current, target):
    return ((target - current) / current) * 100

def format_percentage(value):
    return f"{value:,.0f}"

async def send_price(update, context):
    # Get EMP data in one API call
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": "empyreal"
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 429:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Rate limit exceeded. Please try again in a minute.")
            return
            
        data = response.json()
        if not data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not fetch price data.")
            return
        
        price = data[0]["current_price"]
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
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=img, caption=text)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching price data.")
        return

async def send_detailed_price(update, context):
    # Get EMP data in one API call
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": "empyreal"
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 429:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Rate limit exceeded. Please try again in a minute.")
            return
            
        data = response.json()
        if not data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not fetch price data.")
            return
        
        coin_data = data[0]
        price = coin_data["current_price"]
        ret = get_return(price, TARGET_PRICE)

        # Format large numbers with commas
        def format_number(num):
            return f"{num:,.0f}"

        text = (
            f"$EMP price update:\n\n"
            f"💸 currently bearish at: ${price:.2f}\n"
            f"{'🟢' if coin_data['price_change_percentage_24h'] >= 0 else '🔴'} 24h change: ${coin_data['price_change_24h']:.2f} ({coin_data['price_change_percentage_24h']:.2f}%)\n\n"
            f"🎯 next week target: ${TARGET_PRICE:,}\n"
            f"📈 guaranteed return: {format_percentage(ret)}%\n\n"
            f"📊 market cap: ${format_number(coin_data['market_cap'])}\n"
            f"🏆 rank: #{coin_data['market_cap_rank']}\n"
            f"📈 24h volume: ${format_number(coin_data['total_volume'])}\n\n"
            
            f"(this is absolutely financial advice)"
        )

        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching price data.")
        return

async def handle_wen_commands(update, context):
    if "/" in update.message.text and "wen" in update.message.text.lower():
        await context.bot.send_message(chat_id=update.effective_chat.id, text="next week")

async def send_performance_comparison(update, context):
    # Get data for all three coins in one API call
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": "bitcoin,ethereum,empyreal"
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 429:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Rate limit exceeded. Please try again in a minute.")
            return
            
        data = response.json()
        if not data or len(data) < 3:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not fetch market data. Please try again.")
            return
        
        # Organize data by coin
        coin_data = {}
        for coin in data:
            if coin["id"] == "bitcoin":
                coin_data["bitcoin"] = {
                    "price": coin["current_price"],
                    "change_24h": coin["price_change_percentage_24h"],
                    "price_change_24h": coin["price_change_24h"]
                }
            elif coin["id"] == "ethereum":
                coin_data["ethereum"] = {
                    "price": coin["current_price"],
                    "change_24h": coin["price_change_percentage_24h"],
                    "price_change_24h": coin["price_change_24h"]
                }
            elif coin["id"] == "empyreal":
                coin_data["empyreal"] = {
                    "price": coin["current_price"],
                    "change_24h": coin["price_change_percentage_24h"],
                    "price_change_24h": coin["price_change_24h"]
                }
        
        if len(coin_data) < 3:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not fetch all required data. Please try again.")
            return
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching market data. Please try again.")
        return
    
    # Format the data
    def format_number(num):
        return f"{num:,.0f}"
    
    def format_percent(value):
        return f"{value:+.2f}%" if value >= 0 else f"{value:.2f}%"
    
    # Calculate EMP's performance relative to BTC and ETH
    emp_percent = coin_data["empyreal"]["change_24h"]
    emp_vs_btc = emp_percent - coin_data["bitcoin"]["change_24h"]
    emp_vs_eth = emp_percent - coin_data["ethereum"]["change_24h"]
    
    text = (
        f"📊 24h Performance Comparison:\n\n"
        f"💰 Price:\n"
        f"₿ Bitcoin: ${coin_data['bitcoin']['price']:,.2f}\n"
        f"Ξ Ethereum: ${coin_data['ethereum']['price']:,.2f}\n"
        f"💎 EMP: ${coin_data['empyreal']['price']:,.2f}\n\n"
        f"📈 Performance:\n"
        f"₿ Bitcoin: ${coin_data['bitcoin']['price_change_24h']:+.2f} ({format_percent(coin_data['bitcoin']['change_24h'])})\n"
        f"Ξ Ethereum: ${coin_data['ethereum']['price_change_24h']:+.2f} ({format_percent(coin_data['ethereum']['change_24h'])})\n"
        f"💎 EMP: ${coin_data['empyreal']['price_change_24h']:+.2f} ({format_percent(coin_data['empyreal']['change_24h'])})\n\n"
        f"📊 EMP vs Others:\n"
        f"💎 EMP vs ₿ Bitcoin: {format_percent(emp_vs_btc)}\n"
        f"💎 EMP vs Ξ Ethereum: {format_percent(emp_vs_eth)}\n\n"
        f"💎 $EMP to $27"
    )
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("billi", send_price))
app.add_handler(CommandHandler("price", send_detailed_price))
app.add_handler(CommandHandler("performance", send_performance_comparison))
app.add_handler(MessageHandler(filters.TEXT, handle_wen_commands))
app.run_polling()