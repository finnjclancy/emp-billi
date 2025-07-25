import asyncio
import requests
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from web3 import Web3

# Import our modular components
from config import TOKEN, TARGET_PRICE, IMAGE_PATH, validate_config, get_token_config, get_all_token_keys
from price_utils import get_emp_price_from_pool, get_btc_price_from_eth, get_return, format_percentage, eth_usd
from transaction_utils import get_last_5_transactions, format_last_5_transactions
from monitoring import monitor_transactions, monitoring_groups, monitoring_tasks, get_w3_connection, get_monitoring_status
from betting_system import place_bet, get_daily_leaderboard, get_user_stats

# Initialize Web3 connections
w3_connections = {}
from config import INFURA_URL, ARBITRUM_RPC_URL
if INFURA_URL:
    w3_connections["ethereum"] = Web3(Web3.HTTPProvider(INFURA_URL))
if ARBITRUM_RPC_URL:
    w3_connections["arbitrum"] = Web3(Web3.HTTPProvider(ARBITRUM_RPC_URL))

# ============================================================================
# COMMAND HANDLERS
# ============================================================================

async def send_price(update, context):
    """Send EMP price with target and return prediction"""
    print(f"💰 Command called: /billi by user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        price = get_emp_price_from_pool()
        if price is None:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not fetch EMP price from pool.")
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
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=img, caption=text)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching price data.")
        return

async def send_detailed_price(update, context):
    """Send detailed EMP price information"""
    print(f"📊 Command called: /price by user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        price = get_emp_price_from_pool()
        if price is None:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not fetch EMP price from pool.")
            return
        
        ret = get_return(price, TARGET_PRICE)

        text = (
            f"$EMP price update:\n\n"
            f"💸 bearish at: ${price:.2f}\n"
            f"🎯 next week price: ${TARGET_PRICE:,}\n"
            f"📈 guaranteed return: {format_percentage(ret)}%\n\n"
            f"📊 Price from Uniswap V3 Pool\n"
            f"📍 Pool: 0xe092769bc1fa5262D4f48353f90890Dcc339BF80\n"
        )

        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching price data.")
        return

async def send_emp_price(update, context):
    """Send simple EMP price"""
    print(f"💎 Command called: /empprice by user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        price = get_emp_price_from_pool()
        if price is None:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not fetch EMP price from pool.")
            return
        
        text = f"💎 $EMP: ${price:,.2f}"
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching EMP price.")
        return

async def send_btc_price(update, context):
    """Send BTC price"""
    print(f"₿ Command called: /btcprice by user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        price = get_btc_price_from_eth()
        if price is None:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not fetch BTC price from ETH data.")
            return
        
        text = f"₿ Bitcoin: ${price:,.2f}"
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching BTC price.")
        return

async def send_eth_price(update, context):
    """Send ETH price"""
    print(f"Ξ Command called: /ethprice by user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        price = eth_usd()
        if price is None:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not fetch ETH price from Etherscan.")
            return
        
        text = f"Ξ Ethereum: ${price:,.2f}"
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching ETH price.")
        return

async def send_performance_comparison(update, context):
    """Get 24-hour performance data for ETH, BTC, and EMP with relative comparisons"""
    print(f"📈 Command called: /performance by user {update.effective_user.id} in chat {update.effective_chat.id}")
    
    # Get data for all three assets from CoinGecko
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": "ethereum,bitcoin,empyreal",
        "order": "market_cap_desc",
        "per_page": "10",
        "page": "1",
        "sparkline": "false"
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
        
        # Process CoinGecko data for ETH, BTC, and EMP
        for coin in data:
            if coin["id"] == "ethereum":
                coin_data["ethereum"] = {
                    "price": coin["current_price"],
                    "change_24h": coin["price_change_percentage_24h"],
                    "price_change_24h": coin["price_change_24h"]
                }
            elif coin["id"] == "bitcoin":
                coin_data["bitcoin"] = {
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
        
        # If EMP data not available from CoinGecko, fallback to pool price
        if "empyreal" not in coin_data:
            emp_price = get_emp_price_from_pool()
            if emp_price is None:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not fetch EMP price from pool.")
                return
            
            coin_data["empyreal"] = {
                "price": emp_price,
                "change_24h": 0,  # Fallback to 0 if not available
                "price_change_24h": 0
            }
        
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching market data. Please try again.")
        return
    
    # Format the data
    def format_percent(value):
        return f"{value:+.2f}%" if value >= 0 else f"{value:.2f}%"
    
    # Calculate relative performance
    eth_change = coin_data["ethereum"]["change_24h"]
    btc_change = coin_data["bitcoin"]["change_24h"]
    emp_change = coin_data["empyreal"]["change_24h"]
    
    # Relative performance calculations
    emp_vs_btc = emp_change - btc_change
    emp_vs_eth = emp_change - eth_change
    eth_vs_btc = eth_change - btc_change
    
    text = (
        f"📊 **24-Hour Performance Report** 📊\n\n"
        f"💰 **Current Prices:**\n"
        f"₿ Bitcoin: ${coin_data['bitcoin']['price']:,.2f}\n"
        f"Ξ Ethereum: ${coin_data['ethereum']['price']:,.2f}\n"
        f"💎 EMP: ${coin_data['empyreal']['price']:,.2f}\n\n"
        f"📈 **24h Change:**\n"
        f"₿ Bitcoin: {format_percent(btc_change)}\n"
        f"Ξ Ethereum: {format_percent(eth_change)}\n"
        f"💎 EMP: {format_percent(emp_change)}\n\n"
        f"📊 **Relative Performance:**\n"
        f"💎 EMP vs ₿ BTC: {format_percent(emp_vs_btc)}\n"
        f"💎 EMP vs Ξ ETH: {format_percent(emp_vs_eth)}\n"
        f"Ξ ETH vs ₿ BTC: {format_percent(eth_vs_btc)}"
    )
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='Markdown')

async def send_daily_volume(update, context):
    """Command to show daily trading volume for EMP"""
    print(f"📊 Command called: /vol by user {update.effective_user.id} in chat {update.effective_chat.id}")
    
    text = (
        f"💎 **$EMP Volume Information:**\n\n"
        f"📊 Volume data is not available from the Uniswap V3 pool.\n"
        f"📍 Pool: 0xe092769bc1fa5262D4f48353f90890Dcc339BF80\n\n"
        f"ℹ️ To get volume data, you would need to:\n"
        f"• Query historical swap events\n"
        f"• Calculate volume from transaction data\n"
        f"• Use a different API service\n\n"
        f"💡 Current price is available via /emp command"
    )
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='Markdown')

# ============================================================================
# MONITORING COMMANDS
# ============================================================================

async def start_monitoring(update, context):
    """Start transaction monitoring for EMP"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Unknown"
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Private Chat"
    
    print(f"🚀 Command called: /startemp by user {user_id} ({user_name}) in chat {chat_id} ({chat_title})")
    print(f"📡 SERVER LOG: User {user_name} (ID: {user_id}) called /startemp command in {chat_title}")
    
    await _start_monitoring_generic(update, context, "emp")

async def start_talos_monitoring(update, context):
    """Start transaction monitoring for Talos"""
    print(f"🚀 Command called: /starttalos by user {update.effective_user.id} in chat {update.effective_chat.id}")
    await _start_monitoring_generic(update, context, "talos")

async def start_betting_only(update, context):
    """Start betting-only monitoring for EMP (no transaction messages)"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Unknown"
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Private Chat"
    
    print(f"🎲 Command called: /bet by user {user_id} ({user_name}) in chat {chat_id} ({chat_title})")
    print(f"📡 SERVER LOG: User {user_name} (ID: {user_id}) called /bet command in {chat_title}")
    
    await _start_betting_only_generic(update, context, "emp")

async def start_buy_betting_only(update, context):
    """Start buy-only betting monitoring for EMP (no transaction messages, only buys trigger betting)"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Unknown"
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Private Chat"
    
    print(f"🟢 Command called: /buybet by user {user_id} ({user_name}) in chat {chat_id} ({chat_title})")
    print(f"📡 SERVER LOG: User {user_name} (ID: {user_id}) called /buybet command in {chat_title}")
    
    await _start_buy_betting_only_generic(update, context, "emp")

async def _start_monitoring_generic(update, context, token_key: str):
    """Generic function to start monitoring for any token"""
    token_config = get_token_config(token_key)
    network = token_config["network"]
    w3 = get_w3_connection(network)
    
    if not w3:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ {network.upper()} RPC URL not configured in .env file\n\n"
                 f"Please add your {network} endpoint to the .env file:\n"
                 f"{'INFURA_URL' if network == 'ethereum' else 'ARBITRUM_RPC_URL'}=your_rpc_endpoint"
        )
        return
    
    # Get the chat ID from where the command was sent
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    # Check if this is a group chat
    if chat_type == "private":
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ **Please use this command in a group chat!**\n\n"
                 "Transaction monitoring works best in groups where multiple people can see the updates.\n\n"
                 "1. Add me to a group\n"
                 f"2. Type /start{token_key} in that group"
        )
        return
    
    monitoring_groups[token_key] = chat_id
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🚀 Starting {token_config['name']} transaction monitoring...\n\n"
             f"📊 Pool: {token_config['pool_address']}\n"
             f"🌐 Network: {network.title()}\n"
             f"💬 Group: {chat_id}\n"
             f"📝 Chat Type: {chat_type}\n\n"
             "Monitoring will run in the background.\n"
             "You'll see transaction updates here soon!"
    )
    
    # Start monitoring in background
    asyncio.create_task(monitor_transactions(context.bot, token_key, chat_id, send_transaction_messages=True))
    
    # Start daily leaderboard scheduler
    from betting_system import schedule_daily_leaderboard
    asyncio.create_task(schedule_daily_leaderboard(context.bot, chat_id))

async def _start_betting_only_generic(update, context, token_key: str):
    """Generic function to start betting-only monitoring for any token"""
    token_config = get_token_config(token_key)
    network = token_config["network"]
    w3 = get_w3_connection(network)
    
    if not w3:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ {network.upper()} RPC URL not configured in .env file\n\n"
                 f"Please add your {network} endpoint to the .env file:\n"
                 f"{'INFURA_URL' if network == 'ethereum' else 'ARBITRUM_RPC_URL'}=your_rpc_endpoint"
        )
        return
    
    # Get the chat ID from where the command was sent
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    # Check if this is a group chat
    if chat_type == "private":
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ **Please use this command in a group chat!**\n\n"
                 "Betting system works best in groups where multiple people can participate.\n\n"
                 "1. Add me to a group\n"
                 "2. Type /bet in that group"
        )
        return
    
    # Check if monitoring is already running
    if token_key in monitoring_tasks:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ {token_config['name']} betting monitoring is already running in this group.\n\n"
                 f"Use /stopbet to stop betting monitoring."
        )
        return
    
    # Store the chat ID for betting monitoring
    monitoring_groups[token_key] = chat_id
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🎲 Starting {token_config['name']} betting system...\n\n"
             f"📊 Pool: {token_config['pool_address']}\n"
             f"🌐 Network: {network.title()}\n"
             f"💬 Group: {chat_id}\n"
             f"📝 Chat Type: {chat_type}\n\n"
             "🎯 **Betting-only mode** - No transaction messages will be sent\n"
             "📈 You'll only see betting rounds and results\n\n"
             "Commands:\n"
             "• /leaderboard - View daily leaderboard\n"
             "• /mystats - View your betting stats\n"
             "• /stopbet - Stop betting monitoring"
    )
    
    # Start betting-only monitoring in background
    from monitoring import monitor_transactions
    asyncio.create_task(monitor_transactions(context.bot, token_key, chat_id, send_transaction_messages=False))
    
    # Start daily leaderboard scheduler
    from betting_system import schedule_daily_leaderboard
    asyncio.create_task(schedule_daily_leaderboard(context.bot, chat_id))

async def _start_buy_betting_only_generic(update, context, token_key: str):
    """Generic function to start buy-only betting monitoring for any token"""
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    # Validate token
    if token_key not in TOKENS:
        await update.message.reply_text(f"❌ Unknown token: {token_key}")
        return
    
    token_config = get_token_config(token_key)
    network = token_config["network"]
    
    # Check if it's a group chat
    if chat_type not in ["group", "supergroup"]:
        await update.message.reply_text(
            "❌ This command only works in groups! Add me to a group and try again."
        )
        return
    
    # Store the group ID for this token
    if token_key not in active_groups:
        active_groups[token_key] = set()
    active_groups[token_key].add(chat_id)
    
    # Send confirmation message
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🟢 Starting {token_config['name']} **BUY-ONLY** betting system...\n\n"
             f"📊 Pool: {token_config['pool_address']}\n"
             f"🌐 Network: {network.title()}\n"
             f"💬 Group: {chat_id}\n"
             f"📝 Chat Type: {chat_type}\n\n"
             "🎯 **Buy-Only Betting Mode** - No transaction messages will be sent\n"
             "🟢 **Only BUY transactions trigger betting rounds**\n"
             "🔴 **SELL transactions are completely ignored**\n"
             "📈 You'll only see betting rounds and results from buys\n\n"
             "Commands:\n"
             "• /leaderboard - View daily leaderboard\n"
             "• /mystats - View your betting stats\n"
             "• /stopbuybet - Stop buy-only betting monitoring"
    )
    
    # Start buy-only betting monitoring in background
    from monitoring import monitor_transactions_buy_only
    asyncio.create_task(monitor_transactions_buy_only(context.bot, token_key, chat_id))
    
    # Start daily leaderboard scheduler
    from betting_system import schedule_daily_leaderboard
    asyncio.create_task(schedule_daily_leaderboard(context.bot, chat_id))

async def stop_monitoring(update, context):
    """Stop transaction monitoring for EMP"""
    print(f"🛑 Command called: /stopmonitor by user {update.effective_user.id} in chat {update.effective_chat.id}")
    await _stop_monitoring_generic(update, context, "emp")

async def stop_talos_monitoring(update, context):
    """Stop transaction monitoring for Talos"""
    print(f"🛑 Command called: /stoptalos by user {update.effective_user.id} in chat {update.effective_chat.id}")
    await _stop_monitoring_generic(update, context, "talos")

async def stop_betting_only(update, context):
    """Stop betting-only monitoring for EMP"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Unknown"
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Private Chat"
    
    print(f"🛑 Command called: /stopbet by user {user_id} ({user_name}) in chat {chat_id} ({chat_title})")
    print(f"📡 SERVER LOG: User {user_name} (ID: {user_id}) called /stopbet command in {chat_title}")
    
    await _stop_betting_only_generic(update, context, "emp")

async def stop_buy_betting_only(update, context):
    """Stop buy-only monitoring for EMP"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Unknown"
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Private Chat"
    
    print(f"🛑 Command called: /stopbuybet by user {user_id} ({user_name}) in chat {chat_id} ({chat_title})")
    print(f"📡 SERVER LOG: User {user_name} (ID: {user_id}) called /stopbuybet command in {chat_title}")
    
    await _stop_buy_betting_only_generic(update, context, "emp")

async def _stop_monitoring_generic(update, context, token_key: str):
    """Generic function to stop monitoring for any token"""
    token_config = get_token_config(token_key)
    
    if token_key in monitoring_groups:
        # Cancel the monitoring task
        if token_key in monitoring_tasks:
            task = monitoring_tasks[token_key]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling
        
        # Remove from monitoring groups
        del monitoring_groups[token_key]
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🛑 {token_config['name']} transaction monitoring stopped.\n\n"
                 f"Use /start{token_key} to restart {token_config['name']} monitoring."
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"ℹ️ No active {token_config['name']} monitoring to stop."
        )

async def _stop_betting_only_generic(update, context, token_key: str):
    """Generic function to stop betting-only monitoring for any token"""
    token_config = get_token_config(token_key)
    
    if token_key in monitoring_tasks:
        # Cancel the betting monitoring task
        task = monitoring_tasks[token_key]
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected when cancelling
        
        # Remove from monitoring groups
        if token_key in monitoring_groups:
            del monitoring_groups[token_key]
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🛑 {token_config['name']} betting monitoring stopped.\n\n"
                 f"Use /bet to restart {token_config['name']} betting system."
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"ℹ️ {token_config['name']} betting monitoring is not currently running.\n\n"
                 f"Use /bet to start {token_config['name']} betting system."
        )

async def _stop_buy_betting_only_generic(update, context, token_key: str):
    """Generic function to stop buy-only betting monitoring for any token"""
    chat_id = update.effective_chat.id
    token_config = get_token_config(token_key)
    
    # Import monitoring groups from monitoring module
    from monitoring import monitoring_groups
    
    if token_key in monitoring_groups and monitoring_groups[token_key] == chat_id:
        del monitoring_groups[token_key]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🛑 {token_config['name']} buy-only betting monitoring stopped.\n\n"
                 f"Use /buybet to restart {token_config['name']} buy-only system."
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"ℹ️ {token_config['name']} buy-only betting monitoring is not currently running.\n\n"
                 f"Use /buybet to start {token_config['name']} buy-only system."
        )

async def stop_all_monitoring(update, context):
    """Stop all transaction monitoring"""
    print(f"🛑 Command called: /stopall by user {update.effective_user.id} in chat {update.effective_chat.id}")
    
    stopped_count = 0
    
    # Stop all active monitoring
    for token_key in list(monitoring_groups.keys()):
        # Cancel the monitoring task
        if token_key in monitoring_tasks:
            task = monitoring_tasks[token_key]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling
        
        # Remove from monitoring groups
        del monitoring_groups[token_key]
        stopped_count += 1
    
    if stopped_count > 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🛑 Stopped {stopped_count} monitoring task(s).\n\n"
                 "Use `/startmonitor` to restart EMP monitoring.\n"
                 "Use `/starttalos` to restart Talos monitoring."
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ℹ️ No active monitoring to stop."
        )

# ============================================================================
# TRANSACTION HISTORY COMMANDS
# ============================================================================

async def show_last_5_transactions(update, context):
    """Show last 5 buy/sell transactions for EMP"""
    print(f"📋 Command called: /last5 by user {update.effective_user.id} in chat {update.effective_chat.id}")
    await _show_last_5_transactions_generic(update, context, "emp")

async def show_last_5_talos_transactions(update, context):
    """Show last 5 buy/sell transactions for Talos"""
    print(f"📋 Command called: /last5talos by user {update.effective_user.id} in chat {update.effective_chat.id}")
    await _show_last_5_transactions_generic(update, context, "talos")

async def _show_last_5_transactions_generic(update, context, token_key: str):
    """Generic function to show last 5 transactions for any token"""
    token_config = get_token_config(token_key)
    network = token_config["network"]
    w3 = get_w3_connection(network)
    
    if not w3:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Web3 not configured for {network}. Please set {'INFURA_URL' if network == 'ethereum' else 'ARBITRUM_RPC_URL'} in .env file"
        )
        return
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🔍 Fetching last 5 buy/sell transactions for {token_config['name']}..."
    )
    
    # Get recent transactions
    transactions = get_last_5_transactions(token_key, w3)
    
    if not transactions:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ No recent buy/sell transactions found or error fetching data."
        )
        return
    
    # Format the message
    message = format_last_5_transactions(transactions, token_key, w3)
    
    # Send the message
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode='Markdown'
    )

# ============================================================================
# TESTING COMMANDS
# ============================================================================

async def test_connection(update, context):
    """Test blockchain connection for EMP"""
    print(f"🔧 Command called: /test by user {update.effective_user.id} in chat {update.effective_chat.id}")
    await _test_connection_generic(update, context, "emp")

async def test_talos_connection(update, context):
    """Test blockchain connection for Talos"""
    print(f"🔧 Command called: /testtalos by user {update.effective_user.id} in chat {update.effective_chat.id}")
    await _test_connection_generic(update, context, "talos")

async def _test_connection_generic(update, context, token_key: str):
    """Generic function to test connection for any token"""
    token_config = get_token_config(token_key)
    network = token_config["network"]
    w3 = get_w3_connection(network)
    
    if not w3:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Web3 not configured for {network}. Please set {'INFURA_URL' if network == 'ethereum' else 'ARBITRUM_RPC_URL'} in .env file"
        )
        return
    
    try:
        # Test basic connection
        latest_block = w3.eth.block_number
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ **Connection Test Successful**\n\n"
                 f"📦 Latest Block: {latest_block:,}\n"
                 f"🌐 Network: {network.title()}\n"
                 f"🔗 Provider: {'Infura' if network == 'ethereum' else 'Arbitrum'}"
        )
        
        # Test pool contract
        try:
            from config import UNISWAP_POOL_ABI
            pool_contract = w3.eth.contract(
                address=Web3.to_checksum_address(token_config["pool_address"]),
                abi=UNISWAP_POOL_ABI
            )
            
            # Try to get recent events
            recent_events = pool_contract.events.Swap.get_logs(
                fromBlock=latest_block - 1000,
                toBlock=latest_block
            )
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ **Pool Contract Test Successful**\n\n"
                     f"📊 Pool: {token_config['pool_address'][:8]}...{token_config['pool_address'][-6:]}\n"
                     f"🔄 Recent Swaps: {len(recent_events)} (last 1000 blocks)\n"
                     f"💎 Contract: Active"
            )
            
        except Exception as e:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⚠️ **Pool Contract Test Failed**\n\n"
                     f"Error: {str(e)}\n\n"
                     f"This might be normal if the pool hasn't had recent activity."
            )
            
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ **Connection Test Failed**\n\n"
                 f"Error: {str(e)}\n\n"
                 f"Please check your {'INFURA_URL' if network == 'ethereum' else 'ARBITRUM_RPC_URL'} in .env file"
        )

async def check_status(update, context):
    """Check monitoring status"""
    print(f"📊 Command called: /status by user {update.effective_user.id} in chat {update.effective_chat.id}")
    
    status = get_monitoring_status()
    
    status_text = "📊 **Monitoring Status**\n\n"
    
    # Check Web3 connections
    from monitoring import get_w3_connection
    
    # Test Ethereum connection
    eth_w3 = get_w3_connection("ethereum")
    if eth_w3:
        try:
            latest_block = eth_w3.eth.block_number
            status_text += f"✅ **Ethereum Connected**\n"
            status_text += f"📦 Latest Block: {latest_block:,}\n"
        except Exception as e:
            status_text += f"❌ **Ethereum Error**: {str(e)}\n"
    else:
        status_text += f"❌ **Ethereum**: No connection configured\n"
    
    # Test Arbitrum connection
    arb_w3 = get_w3_connection("arbitrum")
    if arb_w3:
        try:
            latest_block = arb_w3.eth.block_number
            status_text += f"✅ **Arbitrum Connected**\n"
            status_text += f"📦 Latest Block: {latest_block:,}\n"
        except Exception as e:
            status_text += f"❌ **Arbitrum Error**: {str(e)}\n"
    else:
        status_text += f"❌ **Arbitrum**: No connection configured\n"
    
    # Check monitoring status for each token
    for token_key in get_all_token_keys():
        token_config = get_token_config(token_key)
        status_text += f"\n📊 **{token_config['name']} ({token_config['symbol']})**\n"
        
        monitoring_info = status["active_monitoring"].get(token_key, {})
        if monitoring_info.get("active"):
            status_text += f"✅ **Monitoring Active**\n"
            status_text += f"💬 Group ID: {monitoring_info['group_id']}\n"
            status_text += f"📊 Pool: {monitoring_info['pool_address'][:8]}...{monitoring_info['pool_address'][-6:]}\n"
            status_text += f"🔄 Processed TXs: {status['processed_transactions'].get(token_key, 0)}\n"
        else:
            status_text += f"❌ **Monitoring Inactive**\n"
            if token_key == "emp":
                status_text += f"Use /startemp to begin\n"
            else:
                status_text += f"Use /start{token_key} to begin\n"
    
    # Check environment variables
    status_text += f"\n🔧 **Configuration**\n"
    status_text += f"INFURA_URL: {'✅ Set' if INFURA_URL else '❌ Missing'}\n"
    status_text += f"ARBITRUM_RPC_URL: {'✅ Set' if ARBITRUM_RPC_URL else '❌ Missing'}\n"
    
    # Escape special characters for markdown
    status_text = status_text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=status_text,
        parse_mode='MarkdownV2'
    )

async def test_command(update, context):
    """Simple test command to verify command handling"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Unknown"
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Private Chat"
    
    print(f"🧪 TEST Command called: /testcommand by user {user_id} ({user_name}) in chat {chat_id} ({chat_title})")
    print(f"📡 SERVER LOG: User {user_name} (ID: {user_id}) called /testcommand in {chat_title}")
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="✅ Test command working! Command handlers are functioning."
    )

# ============================================================================
# UTILITY COMMANDS
# ============================================================================

async def handle_wen_commands(update, context):
    """Handle 'wen' commands"""
    # Only handle if it's not a command (doesn't start with /)
    if not update.message.text.startswith("/") and "wen" in update.message.text.lower():
        print(f"⏰ Wen command detected by user {update.effective_user.id} in chat {update.effective_chat.id}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="next week")

# ============================================================================
# BETTING SYSTEM COMMANDS
# ============================================================================

async def handle_betting_callback(update, context):
    """Handle betting button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    chat_id = query.message.chat_id
    
    print(f"🎲 Betting callback from user {user_id} in chat {chat_id}")
    
    # Determine which token this betting round is for
    # We'll need to store this information in the betting system
    # For now, let's assume it's for EMP
    token_key = "emp"
    
    if query.data == "bet_higher":
        success, message = place_bet(token_key, user_id, "higher", user)
    elif query.data == "bet_lower":
        success, message = place_bet(token_key, user_id, "lower", user)
    else:
        return
    
    # Send feedback to user
    if success:
        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='Markdown'
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ {message}"
        )

async def show_leaderboard(update, context):
    """Show daily betting leaderboard"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Unknown"
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Private Chat"
    
    print(f"📊 Command called: /leaderboard by user {user_id} ({user_name}) in chat {chat_id} ({chat_title})")
    print(f"📡 SERVER LOG: User {user_name} (ID: {user_id}) called /leaderboard command in {chat_title}")
    
    try:
        print("🔄 Loading betting system data...")
        from betting_system import load_data
        load_data()
        print("✅ Data loaded successfully")
        
        print("🔄 Generating leaderboard...")
        leaderboard = get_daily_leaderboard(context.bot)
        print(f"✅ Leaderboard generated: {leaderboard[:100]}...")
        
        print("🔄 Sending message to chat...")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=leaderboard,
            parse_mode='Markdown'
        )
        print("✅ Leaderboard sent successfully")
    except Exception as e:
        print(f"❌ Error in show_leaderboard: {e}")
        import traceback
        traceback.print_exc()
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ Error generating leaderboard: {e}"
            )
        except Exception as send_error:
            print(f"❌ Failed to send error message: {send_error}")

async def show_user_stats(update, context):
    """Show user's betting stats"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Unknown"
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Private Chat"
    
    print(f"📊 Command called: /mystats by user {user_id} ({user_name}) in chat {chat_id} ({chat_title})")
    print(f"📡 SERVER LOG: User {user_name} (ID: {user_id}) called /mystats command in {chat_title}")
    
    try:
        print("🔄 Loading betting system data...")
        from betting_system import load_data, get_user_display_name
        load_data()
        print("✅ Data loaded successfully")
        
        print(f"🔄 Getting stats for user {user_id}...")
        # Get user display name for the stats
        user = update.effective_user
        user_display_name = get_user_display_name(user)
        stats = get_user_stats(user_id, user_display_name)
        print(f"✅ Stats generated: {stats[:100]}...")
        
        print("🔄 Sending message to chat...")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=stats,
            parse_mode='Markdown'
        )
        print("✅ Stats sent successfully")
    except Exception as e:
        print(f"❌ Error in show_user_stats: {e}")
        import traceback
        traceback.print_exc()
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ Error generating stats: {e}"
            )
        except Exception as send_error:
            print(f"❌ Failed to send error message: {send_error}")

# ============================================================================
# MAIN APPLICATION SETUP
# ============================================================================

def main():
    """Initialize and run the bot"""
    # Validate configuration
    if not validate_config():
        print("❌ Configuration validation failed. Please check your .env file.")
        return
    
    # Create application
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("billi", send_price))
    app.add_handler(CommandHandler("price", send_detailed_price))
    app.add_handler(CommandHandler("empprice", send_emp_price))
    app.add_handler(CommandHandler("btcprice", send_btc_price))
    app.add_handler(CommandHandler("ethprice", send_eth_price))
    app.add_handler(CommandHandler("performance", send_performance_comparison))
    app.add_handler(CommandHandler("vol", send_daily_volume))
    
    # Monitoring commands
    app.add_handler(CommandHandler("startemp", start_monitoring))
    app.add_handler(CommandHandler("stopemp", stop_monitoring))
    app.add_handler(CommandHandler("starttalos", start_talos_monitoring))
    app.add_handler(CommandHandler("stoptalos", stop_talos_monitoring))
    app.add_handler(CommandHandler("stopall", stop_all_monitoring))
    app.add_handler(CommandHandler("bet", start_betting_only))
    app.add_handler(CommandHandler("stopbet", stop_betting_only))
    app.add_handler(CommandHandler("buybet", start_buy_betting_only))
    app.add_handler(CommandHandler("stopbuybet", stop_buy_betting_only))
    
    # Transaction history commands
    app.add_handler(CommandHandler("last5", show_last_5_transactions))
    app.add_handler(CommandHandler("last5talos", show_last_5_talos_transactions))
    
    # Testing commands
    app.add_handler(CommandHandler("test", test_connection))
    app.add_handler(CommandHandler("testtalos", test_talos_connection))
    app.add_handler(CommandHandler("status", check_status))
    app.add_handler(CommandHandler("testcommand", test_command))
    
    # Betting system commands
    print("🔧 Registering betting system commands...")
    app.add_handler(CommandHandler("leaderboard", show_leaderboard))
    app.add_handler(CommandHandler("mystats", show_user_stats))
    print("✅ Betting system commands registered")
    
    # Utility commands (must be last to avoid intercepting commands)
    app.add_handler(MessageHandler(filters.TEXT, handle_wen_commands))
    
    # Betting callback handlers
    app.add_handler(CallbackQueryHandler(handle_betting_callback))
    
    print("Bot started. Use /startemp in a group to begin EMP transaction monitoring.")
    print("Use /starttalos in a group to begin Talos transaction monitoring.")
    print("Use /bet in a group to begin betting-only monitoring (no transaction messages).")
    print("Use /buybet in a group to begin buy-only betting monitoring (only buys trigger betting).")
    print("Betting system commands: /leaderboard, /mystats")
    print("Stop commands: /stopbet, /stopbuybet")
    
    # Use polling with drop_pending_updates to avoid conflicts
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main() 