from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
import requests
import dotenv
import os
import asyncio
import json
from web3 import Web3
from datetime import datetime
import time

dotenv.load_dotenv()

TOKEN = os.getenv("TOKEN")
SYMBOL = "empyreal"
TARGET_PRICE = 3333
IMAGE_PATH = "logo.jpg"

# Token configurations
TOKENS = {
    "emp": {
        "name": "Empyreal",
        "symbol": "EMP",
        "pool_address": "0xe092769bc1fa5262D4f48353f90890Dcc339BF80",
        "network": "ethereum",
        "rpc_url": os.getenv("INFURA_URL"),
        "explorer_url": "https://etherscan.io",
        "target_price": 3333,
        "logo_path": "logo.jpg",
        "buy_image": "buy.jpg",
        "sell_image": "sold.jpg"
    },
    "talos": {
        "name": "Talos",
        "symbol": "T",
        "pool_address": "0x30a538eFFD91ACeFb1b12CE9Bc0074eD18c9dFc9",
        "network": "arbitrum",
        "rpc_url": os.getenv("ARBITRUM_RPC_URL"),
        "explorer_url": "https://arbiscan.io",
        "target_price": 1000,  # You can adjust this
        "logo_path": "logo.jpg",  # You can add a Talos logo later
        "buy_image": "buy.jpg",
        "sell_image": "sold.jpg"
    }
}

# Environment variables
INFURA_URL = os.getenv("INFURA_URL")
ARBITRUM_RPC_URL = os.getenv("ARBITRUM_RPC_URL")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

# Store the group chat IDs when monitoring starts
monitoring_groups = {}

# Initialize Web3 connections
w3_connections = {}
if INFURA_URL:
    w3_connections["ethereum"] = Web3(Web3.HTTPProvider(INFURA_URL))
if ARBITRUM_RPC_URL:
    w3_connections["arbitrum"] = Web3(Web3.HTTPProvider(ARBITRUM_RPC_URL))

# Uniswap V3 Pool ABI (minimal for Swap events)
UNISWAP_POOL_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "sender", "type": "address"},
            {"indexed": True, "name": "recipient", "type": "address"},
            {"indexed": False, "name": "amount0", "type": "int256"},
            {"indexed": False, "name": "amount1", "type": "int256"},
            {"indexed": False, "name": "sqrtPriceX96", "type": "uint160"},
            {"indexed": False, "name": "liquidity", "type": "uint128"},
            {"indexed": False, "name": "tick", "type": "int24"}
        ],
        "name": "Swap",
        "type": "event"
    }
]

# Track processed transactions to avoid duplicates (per token)
processed_transactions = {
    "emp": set(),
    "talos": set()
}

# Simple price cache to reduce API calls
price_cache = {}
price_cache_timestamp = 0
CACHE_DURATION = 60  # Cache prices for 60 seconds

def get_cached_prices(token_symbol=None):
    """Get cached prices or fetch new ones if cache is expired"""
    global price_cache, price_cache_timestamp
    
    current_time = time.time()
    
    # Return cached prices if still valid
    if current_time - price_cache_timestamp < CACHE_DURATION and price_cache:
        if token_symbol == "T":
            # For Talos, we need ETH price for Arbitrum
            eth_price = price_cache.get("eth_usd_price", 0)
            print(f"Using cached prices - ETH: ${eth_price}")
            return 0, eth_price  # Return 0 for token price, ETH price for calculations
        else:
            # For EMP, return both prices
            emp_price = price_cache.get("emp_usd_price", 0)
            eth_price = price_cache.get("eth_usd_price", 0)
            print(f"Using cached prices - EMP: ${emp_price}, ETH: ${eth_price}")
            return emp_price, eth_price
    
    # Try multiple APIs to get prices
    emp_usd_price = 0
    eth_usd_price = 0
    
    # Try CoinGecko first
    try:
        print("Trying CoinGecko API...")
        price_url = "https://api.coingecko.com/api/v3/simple/price?ids=empyreal,ethereum&vs_currencies=usd"
        response = requests.get(price_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            emp_usd_price = data.get("empyreal", {}).get("usd", 0)
            eth_usd_price = data.get("ethereum", {}).get("usd", 0)
            print(f"CoinGecko prices - EMP: ${emp_usd_price}, ETH: ${eth_usd_price}")
        else:
            print(f"CoinGecko API error: {response.status_code}")
    except Exception as e:
        print(f"CoinGecko API failed: {e}")
    
    # If ETH price is still 0, try alternative APIs
    if eth_usd_price == 0:
        # Try alternative CoinGecko endpoint
        try:
            print("Trying CoinGecko ETH-only API...")
            eth_url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
            eth_response = requests.get(eth_url, timeout=10)
            if eth_response.status_code == 200:
                eth_data = eth_response.json()
                eth_usd_price = eth_data.get("ethereum", {}).get("usd", 0)
                print(f"CoinGecko ETH-only price: ${eth_usd_price}")
        except Exception as e:
            print(f"CoinGecko ETH-only API failed: {e}")
        
        # If still no ETH price, try alternative API
        if eth_usd_price == 0:
            try:
                print("Trying alternative API...")
                # Try a different price API (example: CoinCap)
                alt_url = "https://api.coincap.io/v2/assets/ethereum"
                alt_response = requests.get(alt_url, timeout=10)
                if alt_response.status_code == 200:
                    alt_data = alt_response.json()
                    eth_usd_price = float(alt_data.get("data", {}).get("priceUsd", 0))
                    print(f"Alternative API ETH price: ${eth_usd_price}")
            except Exception as e:
                print(f"Alternative API failed: {e}")
    
    # Update cache with whatever we got
    price_cache = {
        "emp_usd_price": emp_usd_price,
        "eth_usd_price": eth_usd_price
    }
    price_cache_timestamp = current_time
    
    if token_symbol == "T":
        print(f"Final prices - ETH: ${eth_usd_price}")
        return 0, eth_usd_price  # Return 0 for token price, ETH price for calculations
    else:
        print(f"Final prices - EMP: ${emp_usd_price}, ETH: ${eth_usd_price}")
        return emp_usd_price, eth_usd_price

def get_transaction_details(tx_hash):
    """Get transaction details from Etherscan API"""
    if not ETHERSCAN_API_KEY:
        return None
    
    url = f"https://api.etherscan.io/api"
    params = {
        "module": "proxy",
        "action": "eth_getTransactionByHash",
        "txhash": tx_hash,
        "apikey": ETHERSCAN_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get("result"):
                return data["result"]
    except Exception as e:
        print(f"Error fetching transaction details: {e}")
    
    return None



def get_last_5_transactions(token_key="emp"):
    """Get the last 5 buy/sell transactions from the Uniswap pool for a specific token"""
    token_config = TOKENS.get(token_key)
    if not token_config:
        print(f"Token configuration not found for {token_key}")
        return None
    
    network = token_config["network"]
    w3 = w3_connections.get(network)
    
    if not w3 or not ETHERSCAN_API_KEY:
        return None
    
    try:
        # Create contract instance
        pool_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_config["pool_address"]),
            abi=UNISWAP_POOL_ABI
        )
        
        # Get latest block with rate limiting
        try:
            latest_block = w3.eth.block_number
        except Exception as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                print(f"Rate limited in get_last_5_transactions for {token_key}")
                return None
            else:
                print(f"Error getting block number in get_last_5_transactions for {token_key}: {e}")
                return None
        
        # Search for recent events (go back more blocks to ensure we get enough)
        search_blocks = 5000  # Search last 5000 blocks
        from_block = latest_block - search_blocks
        
        # Get swap events with rate limiting
        try:
            swap_events = pool_contract.events.Swap.get_logs(
                fromBlock=from_block,
                toBlock=latest_block
            )
        except Exception as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                print(f"Rate limited while getting swap events for {token_key}")
                return None
            else:
                print(f"Error getting swap events for {token_key}: {e}")
                return None
        
        # Sort by block number (newest first)
        sorted_events = sorted(swap_events, key=lambda x: x['blockNumber'], reverse=True)
        
        # Filter for buy/sell transactions only
        buy_sell_events = []
        for event in sorted_events:
            amount0 = event["args"]["amount0"]
            amount1 = event["args"]["amount1"]
            
            # Check if it's a buy (ETH -> Token) or sell (Token -> ETH)
            if (amount0 < 0 and amount1 > 0) or (amount0 > 0 and amount1 < 0):
                buy_sell_events.append(event)
                if len(buy_sell_events) >= 5:  # Stop after finding 5
                    break
        
        return buy_sell_events[:5]
        
    except Exception as e:
        print(f"Error fetching recent transactions for {token_key}: {e}")
        return None

def format_last_5_transactions(transactions, token_key="emp"):
    """Format the last 5 transactions into a readable message for a specific token"""
    if not transactions:
        return "❌ No recent buy/sell transactions found."
    
    token_config = TOKENS.get(token_key)
    if not token_config:
        return "❌ Token configuration not found."
    
    token_symbol = token_config["symbol"]
    network = token_config["network"]
    w3 = w3_connections.get(network)
    explorer_url = token_config["explorer_url"]
    
    # Get current prices using cache to reduce API calls
    if token_symbol == "T":
        # For Talos, we only need ETH price for Arbitrum
        token_usd_price, eth_usd_price = get_cached_prices("T")
    else:
        # For EMP, get both prices
        token_usd_price, eth_usd_price = get_cached_prices()
    
    # Process each transaction
    transaction_details = []
    total_bought = 0
    total_sold = 0
    buy_count = 0
    sell_count = 0
    
    for event in transactions:
        try:
            # Extract data
            sender = event["args"]["sender"]
            amount0 = event["args"]["amount0"]
            amount1 = event["args"]["amount1"]
            tx_hash = event["transactionHash"].hex()
            block_number = event["blockNumber"]
            
            # Get block timestamp
            try:
                block = w3.eth.get_block(block_number)
                timestamp = datetime.fromtimestamp(block.timestamp)
            except:
                timestamp = datetime.now()
            
            # Convert amounts
            token_amount = abs(amount0) / (10 ** 18)
            eth_amount = abs(amount1) / (10 ** 18)
            
            # Determine direction
            if amount0 > 0 and amount1 < 0:
                # SELL Token
                direction = f"🔴 SOLD ${token_symbol}"
                action_emojis = ""
                usd_value = eth_amount * eth_usd_price  # Use ETH amount for USD value
                print(f"Last5 SELL - eth_amount: {eth_amount}, eth_usd_price: ${eth_usd_price}, usd_value: ${usd_value}")
                
                # Calculate actual price per token from the transaction
                if token_amount > 0 and eth_usd_price > 0:
                    actual_price_per_token = usd_value / token_amount
                else:
                    actual_price_per_token = token_usd_price  # Fallback to current price
                
                emoji_count = max(1, int(usd_value / 50) + (1 if usd_value % 50 > 0 else 0)) if usd_value > 0 else 1
                for i in range(emoji_count):
                    if i % 2 == 0:
                        action_emojis += "🍆"
                    else:
                        action_emojis += "🍌"
                
                total_sold += usd_value
                sell_count += 1
                
                # Format detail based on whether we have USD prices
                if eth_usd_price > 0:
                    detail = (
                        f"{direction}\n\n"
                        f"{action_emojis}\n\n"
                        f"💰 ${usd_value:.2f} ({eth_amount:.2f} ETH)\n"
                        f"💎 {token_amount:.3f} ${token_symbol}\n"
                        f"💵 ${actual_price_per_token:.2f} per {token_symbol}\n"
                        f"⏰ {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"🔗 [View TX]({explorer_url}/tx/{tx_hash})\n"
                    )
                else:
                    detail = (
                        f"{direction}\n\n"
                        f"{action_emojis}\n\n"
                        f"💰 {eth_amount:.2f} ETH\n"
                        f"💎 {token_amount:.3f} ${token_symbol}\n"
                        f"⏰ {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"🔗 [View TX]({explorer_url}/tx/{tx_hash})\n"
                    )
                
            elif amount0 < 0 and amount1 > 0:
                # BUY Token
                direction = f"🟢 BOUGHT ${token_symbol}"
                action_emojis = ""
                usd_value = eth_amount * eth_usd_price
                print(f"Last5 BUY - eth_amount: {eth_amount}, eth_usd_price: ${eth_usd_price}, usd_value: ${usd_value}")
                
                # Calculate actual price per token from the transaction
                if token_amount > 0 and eth_usd_price > 0:
                    actual_price_per_token = usd_value / token_amount
                else:
                    actual_price_per_token = token_usd_price  # Fallback to current price
                
                emoji_count = max(1, int(usd_value / 50) + (1 if usd_value % 50 > 0 else 0)) if usd_value > 0 else 1
                for i in range(emoji_count):
                    if i % 2 == 0:
                        action_emojis += "🍑"
                    else:
                        action_emojis += "🍒"
                
                total_bought += usd_value
                buy_count += 1
                
                # Format detail based on whether we have USD prices
                if eth_usd_price > 0:
                    detail = (
                        f"{direction}\n\n"
                        f"{action_emojis}\n\n"
                        f"💰 ${usd_value:.2f} ({eth_amount:.2f} ETH)\n"
                        f"💎 {token_amount:.3f} ${token_symbol}\n"
                        f"💵 ${actual_price_per_token:.2f} per {token_symbol}\n"
                        f"⏰ {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"🔗 [View TX]({explorer_url}/tx/{tx_hash})\n"
                    )
                else:
                    detail = (
                        f"{direction}\n\n"
                        f"{action_emojis}\n\n"
                        f"💰 {eth_amount:.2f} ETH\n"
                        f"💎 {token_amount:.3f} ${token_symbol}\n"
                        f"⏰ {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"🔗 [View TX]({explorer_url}/tx/{tx_hash})\n"
                    )
            
            transaction_details.append(detail)
            
        except Exception as e:
            print(f"Error processing transaction: {e}")
            continue
    
    # Calculate summary
    total_transactions = buy_count + sell_count
    buy_percentage = (buy_count / total_transactions * 100) if total_transactions > 0 else 0
    net_buying = total_bought - total_sold
    total_volume = total_bought + total_sold
    
    # Create summary
    summary = (
        f"📊 **LAST 5 {token_symbol} TRANSACTIONS SUMMARY**\n\n"
        f"🟢 **{buy_count} Buys** ({buy_percentage:.1f}%)\n"
        f"🔴 **{sell_count} Sells** ({100-buy_percentage:.1f}%)\n\n"
        f"💰 **${total_bought:,.0f} Bought**\n"
        f"💰 **${total_sold:,.0f} Sold**\n"
        f"📈 **${net_buying:+,.0f} Net Buying** ({'+' if net_buying >= 0 else ''}${net_buying:,.0f})\n"
        f"📊 **${total_volume:,.0f} Total Volume**\n"
    )
    
    # Combine all details with numbered transactions
    numbered_details = []
    for i, detail in enumerate(transaction_details, 1):
        numbered_details.append(f"**Transaction {i}:**\n{detail}")
    
    full_message = "\n\n----------------------\n\n".join(numbered_details) + "\n\n----------------------\n\n" + summary
    
    return full_message

def format_swap_message(swap_event, tx_hash, tx_details=None, token_key="emp"):
    """Format a swap event into a readable message for a specific token"""
    try:
        token_config = TOKENS.get(token_key)
        if not token_config:
            return f"🔄 **New Swap Detected**\n\n🔗 [View Transaction](https://etherscan.io/tx/{tx_hash})", "🔄 SWAP"
        
        token_symbol = token_config["symbol"]
        explorer_url = token_config["explorer_url"]
        
        # Extract swap data
        sender = swap_event["args"]["sender"]
        recipient = swap_event["args"]["recipient"]
        amount0 = swap_event["args"]["amount0"]
        amount1 = swap_event["args"]["amount1"]
        
        # Token decimals (both tokens = 18, ETH = 18)
        TOKEN_DECIMALS = 18
        ETH_DECIMALS = 18
        
        # Convert raw amounts to human readable
        token_amount = abs(amount0) / (10 ** TOKEN_DECIMALS)
        eth_amount = abs(amount1) / (10 ** ETH_DECIMALS)
        
        # Determine swap direction and initialize variables
        if amount0 > 0 and amount1 < 0:
            # Token0 (Token) -> Token1 (ETH) = SELL Token
            direction = "🔴 SELL"
            token_in = token_amount
            eth_out = eth_amount
            eth_in = 0
            token_out = 0
        elif amount0 < 0 and amount1 > 0:
            # Token1 (ETH) -> Token0 (Token) = BUY Token
            direction = "🟢 BUY"
            eth_in = eth_amount
            token_out = token_amount
            token_in = 0
            eth_out = 0
        else:
            # Fallback for other cases
            direction = "🔄 SWAP"
            token_in = token_amount if amount0 > 0 else 0
            eth_out = eth_amount if amount1 > 0 else 0
            eth_in = eth_amount if amount1 < 0 else 0
            token_out = token_amount if amount0 < 0 else 0
        
        # Get current prices using cache to reduce API calls
        if token_symbol == "T":
            # For Talos, we only need ETH price for Arbitrum
            token_usd_price, eth_usd_price = get_cached_prices("T")
        else:
            # For EMP, get both prices
            token_usd_price, eth_usd_price = get_cached_prices()
        
        # Calculate USD values and emojis
        if direction == "🔴 SELL":
            # For SELL: Calculate USD value based on ETH received
            eth_usd_value = eth_out * eth_usd_price
            total_usd = eth_usd_value
            
            print(f"SELL calculation - eth_out: {eth_out}, eth_usd_price: ${eth_usd_price}, total_usd: ${total_usd}")
            
            # Calculate actual price per token from the transaction
            if token_in > 0 and eth_usd_price > 0:
                actual_price_per_token = eth_usd_value / token_in
            else:
                actual_price_per_token = token_usd_price  # Fallback to current price
            
            # Calculate emojis for sell (🍆🍌 alternating)
            emoji_count = max(1, int(total_usd / 50) + (1 if total_usd % 50 > 0 else 0)) if total_usd > 0 else 1
            sell_emojis = ""
            for i in range(emoji_count):
                if i % 2 == 0:
                    sell_emojis += "🍆"
                else:
                    sell_emojis += "🍌"
            
            # Format message based on whether we have USD prices
            if eth_usd_price > 0:
                message = (
                    f"🔴 **SOLD ${token_symbol}** 🔴\n\n"
                    f"{sell_emojis}\n\n"
                    f"💰 **${total_usd:.2f} ({eth_out:.2f} ETH)**\n"
                    f"💎 **{token_in:.3f} ${token_symbol}**\n"
                    f"💵 **${actual_price_per_token:.2f} per {token_symbol}**\n\n"
                    f"🔗 **Transaction:** [View TX]({explorer_url}/tx/{tx_hash})"
                )
            else:
                message = (
                    f"🔴 **SOLD ${token_symbol}** 🔴\n\n"
                    f"{sell_emojis}\n\n"
                    f"💰 **{eth_out:.2f} ETH**\n"
                    f"💎 **{token_in:.3f} ${token_symbol}**\n\n"
                    f"🔗 **Transaction:** [View TX]({explorer_url}/tx/{tx_hash})"
                )
        elif direction == "🟢 BUY":
            # For BUY: Calculate USD value based on ETH spent
            eth_usd_value = eth_in * eth_usd_price
            total_usd = eth_usd_value
            
            print(f"BUY calculation - eth_in: {eth_in}, eth_usd_price: ${eth_usd_price}, total_usd: ${total_usd}")
            
            # Calculate actual price per token from the transaction
            if token_out > 0 and eth_usd_price > 0:
                actual_price_per_token = eth_usd_value / token_out
            else:
                actual_price_per_token = token_usd_price  # Fallback to current price
            
            # Calculate emojis for buy (🍑🍒 alternating)
            emoji_count = max(1, int(total_usd / 50) + (1 if total_usd % 50 > 0 else 0)) if total_usd > 0 else 1
            buy_emojis = ""
            for i in range(emoji_count):
                if i % 2 == 0:
                    buy_emojis += "🍑"
                else:
                    buy_emojis += "🍒"
            
            # Format message based on whether we have USD prices
            if eth_usd_price > 0:
                message = (
                    f"🟢 **BOUGHT ${token_symbol}** 🟢\n\n"
                    f"{buy_emojis}\n\n"
                    f"💰 **${total_usd:.2f} ({eth_in:.2f} ETH)**\n"
                    f"💎 **{token_out:.3f} ${token_symbol}**\n"
                    f"💵 **${actual_price_per_token:.2f} per {token_symbol}**\n\n"
                    f"🔗 **Transaction:** [View TX]({explorer_url}/tx/{tx_hash})"
                )
            else:
                message = (
                    f"🟢 **BOUGHT ${token_symbol}** 🟢\n\n"
                    f"{buy_emojis}\n\n"
                    f"💰 **{eth_in:.2f} ETH**\n"
                    f"💎 **{token_out:.3f} ${token_symbol}**\n\n"
                    f"🔗 **Transaction:** [View TX]({explorer_url}/tx/{tx_hash})"
                )
        else:
            message = (
                f"🔄 **SWAP DETECTED**\n\n"
                f"💎 **Amounts:** {token_amount:.3f} {token_symbol} / {eth_amount:.2f} ETH\n"
                f"🔗 **Transaction:** [View TX]({explorer_url}/tx/{tx_hash})"
            )
        
        return message, direction
        
    except Exception as e:
        print(f"Error formatting swap message: {e}")
        return f"🔄 **New Swap Detected**\n\n🔗 [View Transaction]({explorer_url}/tx/{tx_hash})", "🔄 SWAP"

async def monitor_transactions(bot, token_key="emp", group_id=None):
    """Monitor Uniswap pool for new transactions for a specific token"""
    global monitoring_groups, processed_transactions
    
    token_config = TOKENS.get(token_key)
    if not token_config:
        print(f"Token configuration not found for {token_key}")
        return
    
    network = token_config["network"]
    w3 = w3_connections.get(network)
    
    if not w3:
        print(f"Web3 not configured for {network}. Skipping transaction monitoring for {token_key}.")
        return
    
    if not group_id:
        print(f"No group chat ID set for {token_key}. Use /startmonitor in a group first.")
        return
    
    try:
        # Create contract instance
        pool_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_config["pool_address"]),
            abi=UNISWAP_POOL_ABI
        )
        
        print(f"Starting transaction monitoring for {token_key} pool: {token_config['pool_address']}")
        print(f"Posting updates to group chat: {group_id}")
        
        # Get latest block with error handling
        try:
            latest_block = w3.eth.block_number
            print(f"Starting from block: {latest_block}")
        except Exception as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                print(f"Rate limited during startup for {token_key}, waiting 60 seconds before retrying...")
                await asyncio.sleep(60)
                try:
                    latest_block = w3.eth.block_number
                    print(f"Retry successful, starting from block: {latest_block}")
                except Exception as e2:
                    print(f"Still rate limited for {token_key}: {e2}")
                    return
            else:
                print(f"Error getting initial block number for {token_key}: {e}")
                return
        
        while True:
            try:
                # Get new blocks with rate limiting
                try:
                    current_block = w3.eth.block_number
                except Exception as e:
                    if "429" in str(e) or "Too Many Requests" in str(e):
                        print(f"Rate limited by {network} provider for {token_key}, waiting 60 seconds...")
                        await asyncio.sleep(60)
                        continue
                    else:
                        print(f"Error getting block number for {token_key}: {e}")
                        await asyncio.sleep(30)
                        continue
                
                if current_block > latest_block:
                    # Check for swap events in new blocks
                    for block_num in range(latest_block + 1, current_block + 1):
                        try:
                            # Get swap events from the block with rate limiting
                            swap_events = pool_contract.events.Swap.get_logs(
                                fromBlock=block_num,
                                toBlock=block_num
                            )
                            
                            for event in swap_events:
                                tx_hash = event["transactionHash"].hex()
                                
                                # Avoid duplicate processing
                                if tx_hash in processed_transactions[token_key]:
                                    continue
                                
                                processed_transactions[token_key].add(tx_hash)
                                
                                # Get transaction details
                                tx_details = get_transaction_details(tx_hash)
                                
                                # Format and send message
                                message_result = format_swap_message(event, tx_hash, tx_details, token_key)
                                
                                if isinstance(message_result, tuple):
                                    message, direction = message_result
                                else:
                                    message = message_result
                                    direction = "🔄 SWAP"
                                
                                # Process both BUY and SELL transactions
                                if direction == "🔴 SELL":
                                    try:
                                        # Use sell-specific image
                                        image_path = token_config["sell_image"]
                                        
                                        # Send message with image
                                        with open(image_path, "rb") as img:
                                            await bot.send_photo(
                                                chat_id=group_id,
                                                photo=img,
                                                caption=message,
                                                parse_mode='Markdown'
                                            )
                                        print(f"Posted {token_key} SELL transaction with image: {tx_hash}")
                                    except Exception as e:
                                        print(f"Error sending message with image for {token_key}: {e}")
                                        # Fallback to text-only if image fails
                                        try:
                                            await bot.send_message(
                                                chat_id=group_id,
                                                text=message,
                                                parse_mode='Markdown',
                                                disable_web_page_preview=True
                                            )
                                            print(f"Posted {token_key} SELL transaction (text-only): {tx_hash}")
                                        except Exception as e2:
                                            print(f"Error sending text-only message for {token_key}: {e2}")
                                elif direction == "🟢 BUY":
                                    try:
                                        # Use buy-specific image
                                        image_path = token_config["buy_image"]
                                        
                                        # Send message with image
                                        with open(image_path, "rb") as img:
                                            await bot.send_photo(
                                                chat_id=group_id,
                                                photo=img,
                                                caption=message,
                                                parse_mode='Markdown'
                                            )
                                        print(f"Posted {token_key} BUY transaction with image: {tx_hash}")
                                    except Exception as e:
                                        print(f"Error sending message with image for {token_key}: {e}")
                                        # Fallback to text-only if image fails
                                        try:
                                            await bot.send_message(
                                                chat_id=group_id,
                                                text=message,
                                                parse_mode='Markdown',
                                                disable_web_page_preview=True
                                            )
                                            print(f"Posted {token_key} BUY transaction (text-only): {tx_hash}")
                                        except Exception as e2:
                                            print(f"Error sending text-only message for {token_key}: {e2}")
                                else:
                                    # For other swap types, send text-only
                                    try:
                                        await bot.send_message(
                                            chat_id=group_id,
                                            text=message,
                                            parse_mode='Markdown',
                                            disable_web_page_preview=True
                                        )
                                        print(f"Posted {token_key} SWAP transaction: {tx_hash}")
                                    except Exception as e:
                                        print(f"Error sending text-only message for {token_key}: {e}")
                                
                                # Small delay to avoid rate limits (increased to reduce API calls)
                                await asyncio.sleep(5)
                                
                        except Exception as e:
                            if "429" in str(e) or "Too Many Requests" in str(e):
                                print(f"Rate limited while processing block {block_num} for {token_key}, waiting 30 seconds...")
                                await asyncio.sleep(30)
                                break  # Exit the block processing loop
                            else:
                                print(f"Error processing block {block_num} for {token_key}: {e}")
                                continue
                    
                    latest_block = current_block
                
                # Wait before checking for new blocks (increased delay to reduce rate limiting)
                await asyncio.sleep(30)  # Check every ~30 seconds
                
            except Exception as e:
                print(f"Error in transaction monitoring loop for {token_key}: {e}")
                await asyncio.sleep(30)  # Wait longer on error
                
    except Exception as e:
        print(f"Error initializing transaction monitoring for {token_key}: {e}")

async def show_last_5_transactions(update, context):
    """Command to show last 5 buy/sell transactions for EMP"""
    token_key = "emp"
    token_config = TOKENS.get(token_key)
    network = token_config["network"]
    w3 = w3_connections.get(network)
    
    if not w3:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Web3 not configured for {network}. Please set INFURA_URL in .env file"
        )
        return
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔍 Fetching last 5 buy/sell transactions for EMP..."
    )
    
    # Get recent transactions
    transactions = get_last_5_transactions(token_key)
    
    if not transactions:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ No recent buy/sell transactions found or error fetching data."
        )
        return
    
    # Format the message
    message = format_last_5_transactions(transactions, token_key)
    
    # Send the message
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode='Markdown'
    )

async def start_monitoring(update, context):
    """Command to start EMP transaction monitoring"""
    global monitoring_groups
    
    token_key = "emp"
    token_config = TOKENS.get(token_key)
    network = token_config["network"]
    w3 = w3_connections.get(network)
    
    if not w3:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ {network.upper()} RPC URL not configured in .env file\n\n"
                 f"Please add your {network} endpoint to the .env file:\n"
                 f"INFURA_URL=https://mainnet.infura.io/v3/your_project_id"
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
                 "2. Type `/startmonitor` in that group"
        )
        return
    
    monitoring_groups[token_key] = chat_id
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="🚀 Starting EMP transaction monitoring...\n\n"
             f"📊 Pool: {token_config['pool_address']}\n"
             f"🌐 Network: {network.title()}\n"
             f"💬 Group: {chat_id}\n"
             f"📝 Chat Type: {chat_type}\n\n"
             "Monitoring will run in the background.\n"
             "You'll see transaction updates here soon!"
    )
    
    # Start monitoring in background
    asyncio.create_task(monitor_transactions(context.bot, token_key, chat_id))

async def stop_monitoring(update, context):
    """Command to stop EMP transaction monitoring"""
    global monitoring_groups
    
    token_key = "emp"
    
    if token_key in monitoring_groups:
        del monitoring_groups[token_key]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🛑 EMP transaction monitoring stopped.\n\n"
                 "Use `/startmonitor` to restart EMP monitoring."
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ℹ️ No active EMP monitoring to stop."
        )

async def check_status(update, context):
    """Command to check monitoring status"""
    global monitoring_groups, processed_transactions
    
    status_text = "📊 **Monitoring Status**\n\n"
    
    # Check Web3 connections
    for network, w3 in w3_connections.items():
        try:
            latest_block = w3.eth.block_number
            status_text += f"✅ **{network.title()} Connected**\n"
            status_text += f"📦 Latest Block: {latest_block:,}\n"
        except Exception as e:
            status_text += f"❌ **{network.title()} Error**: {str(e)}\n"
    
    if not w3_connections:
        status_text += f"❌ **No Web3 Connections**\n"
        status_text += f"Missing RPC URLs in .env file\n"
    
    # Check monitoring status for each token
    for token_key, token_config in TOKENS.items():
        status_text += f"\n📊 **{token_config['name']} ({token_config['symbol']})**\n"
        if token_key in monitoring_groups:
            status_text += f"✅ **Monitoring Active**\n"
            status_text += f"💬 Group ID: {monitoring_groups[token_key]}\n"
            status_text += f"📊 Pool: {token_config['pool_address'][:8]}...{token_config['pool_address'][-6:]}\n"
            status_text += f"🔄 Processed TXs: {len(processed_transactions[token_key])}\n"
        else:
            status_text += f"❌ **Monitoring Inactive**\n"
            status_text += f"Use `/startmonitor` to begin\n"
    
    # Check environment variables
    status_text += f"\n🔧 **Configuration**\n"
    status_text += f"INFURA_URL: {'✅ Set' if INFURA_URL else '❌ Missing'}\n"
    status_text += f"ARBITRUM_RPC_URL: {'✅ Set' if ARBITRUM_RPC_URL else '❌ Missing'}\n"
    status_text += f"ETHERSCAN_API: {'✅ Set' if ETHERSCAN_API_KEY else '❌ Missing (optional)'}\n"
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=status_text,
        parse_mode='Markdown'
    )

async def test_connection(update, context):
    """Command to test blockchain connection for EMP"""
    token_key = "emp"
    token_config = TOKENS.get(token_key)
    network = token_config["network"]
    w3 = w3_connections.get(network)
    
    if not w3:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Web3 not configured for {network}. Please set INFURA_URL in .env file"
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
                 f"🔗 Provider: Infura"
        )
        
        # Test pool contract
        try:
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
                 f"Please check your INFURA_URL in .env file"
        )

# Talos-specific commands
async def show_last_5_talos_transactions(update, context):
    """Command to show last 5 buy/sell transactions for Talos"""
    token_key = "talos"
    token_config = TOKENS.get(token_key)
    network = token_config["network"]
    w3 = w3_connections.get(network)
    
    if not w3:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Web3 not configured for {network}. Please set ARBITRUM_RPC_URL in .env file"
        )
        return
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔍 Fetching last 5 buy/sell transactions for Talos..."
    )
    
    # Get recent transactions
    transactions = get_last_5_transactions(token_key)
    
    if not transactions:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ No recent buy/sell transactions found or error fetching data."
        )
        return
    
    # Format the message
    message = format_last_5_transactions(transactions, token_key)
    
    # Send the message
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode='Markdown'
    )

async def start_talos_monitoring(update, context):
    """Command to start Talos transaction monitoring"""
    global monitoring_groups
    
    token_key = "talos"
    token_config = TOKENS.get(token_key)
    network = token_config["network"]
    w3 = w3_connections.get(network)
    
    if not w3:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ {network.upper()} RPC URL not configured in .env file\n\n"
                 f"Please add your {network} endpoint to the .env file:\n"
                 f"ARBITRUM_RPC_URL=https://arbitrum-mainnet.infura.io/v3/your_project_id"
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
                 "2. Type `/starttalos` in that group"
        )
        return
    
    monitoring_groups[token_key] = chat_id
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="🚀 Starting Talos transaction monitoring...\n\n"
             f"📊 Pool: {token_config['pool_address']}\n"
             f"🌐 Network: {network.title()}\n"
             f"💬 Group: {chat_id}\n"
             f"📝 Chat Type: {chat_type}\n\n"
             "Monitoring will run in the background.\n"
             "You'll see transaction updates here soon!"
    )
    
    # Start monitoring in background
    asyncio.create_task(monitor_transactions(context.bot, token_key, chat_id))

async def stop_talos_monitoring(update, context):
    """Command to stop Talos transaction monitoring"""
    global monitoring_groups
    
    token_key = "talos"
    
    if token_key in monitoring_groups:
        del monitoring_groups[token_key]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🛑 Talos transaction monitoring stopped.\n\n"
                 "Use `/starttalos` to restart Talos monitoring."
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ℹ️ No active Talos monitoring to stop."
        )

async def test_talos_connection(update, context):
    """Command to test blockchain connection for Talos"""
    token_key = "talos"
    token_config = TOKENS.get(token_key)
    network = token_config["network"]
    w3 = w3_connections.get(network)
    
    if not w3:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Web3 not configured for {network}. Please set ARBITRUM_RPC_URL in .env file"
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
                 f"🔗 Provider: Arbitrum"
        )
        
        # Test pool contract
        try:
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
                 f"Please check your ARBITRUM_RPC_URL in .env file"
        )

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
            f"💸 bearish at: ${price:.2f}\n"
            f"{'🟢' if coin_data['price_change_percentage_24h'] >= 0 else '🔴'} 24h change: ${coin_data['price_change_24h']:.2f} ({coin_data['price_change_percentage_24h']:.2f}%)\n\n"
            f"📈 24h volume: ${format_number(coin_data['total_volume'])}\n\n"
            f"🎯 next week price: ${TARGET_PRICE:,}\n"
            f"📈 guaranteed return: {format_percentage(ret)}%\n\n"
            f"🏆 rank: #{coin_data['market_cap_rank']}\n"
            f"📊 market cap: ${format_number(coin_data['market_cap'])}\n"
        )

        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching price data.")
        return

async def handle_wen_commands(update, context):
    if "/" in update.message.text and "wen" in update.message.text.lower():
        await context.bot.send_message(chat_id=update.effective_chat.id, text="next week")

async def send_emp_price(update, context):
    # Get EMP price in one API call
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
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not fetch EMP price.")
            return
        
        price = data[0]["current_price"]
        text = f"💎 $EMP: ${price:,.2f}"
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching EMP price.")
        return

async def send_btc_price(update, context):
    # Get BTC price in one API call
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": "bitcoin"
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 429:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Rate limit exceeded. Please try again in a minute.")
            return
            
        data = response.json()
        if not data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not fetch BTC price.")
            return
        
        price = data[0]["current_price"]
        text = f"₿ Bitcoin: ${price:,.2f}"
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching BTC price.")
        return

async def send_eth_price(update, context):
    # Get ETH price in one API call
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": "ethereum"
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 429:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Rate limit exceeded. Please try again in a minute.")
            return
            
        data = response.json()
        if not data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Could not fetch ETH price.")
            return
        
        price = data[0]["current_price"]
        text = f"Ξ Ethereum: ${price:,.2f}"
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Error fetching ETH price.")
        return

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
        f"📈 24h Performance:\n"
        f"₿ Bitcoin: ${coin_data['bitcoin']['price_change_24h']:+.2f} ({format_percent(coin_data['bitcoin']['change_24h'])})\n"
        f"Ξ Ethereum: ${coin_data['ethereum']['price_change_24h']:+.2f} ({format_percent(coin_data['ethereum']['change_24h'])})\n"
        f"💎 EMP: ${coin_data['empyreal']['price_change_24h']:+.2f} ({format_percent(coin_data['empyreal']['change_24h'])})\n\n"
        f"📊 EMP vs Others:(24h)\n"
        f"💎 EMP vs ₿ Bitcoin: {format_percent(emp_vs_btc)}\n"
        f"💎 EMP vs Ξ Ethereum: {format_percent(emp_vs_eth)}\n\n"
    )
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

async def send_daily_volume(update, context):
    """Command to show daily trading volume for EMP"""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": "empyreal"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 429:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Rate limit exceeded. Please try again in a minute.")
            return
        elif response.status_code != 200:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ API error: {response.status_code}. Please try again later.")
            return
            
        data = response.json()
        if not data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Could not fetch EMP volume data.")
            return
        
        volume_24h = data[0]["total_volume"]
        
        # Format the volume with appropriate units
        if volume_24h >= 1_000_000_000:
            formatted_volume = f"${volume_24h/1_000_000_000:.2f}B"
        elif volume_24h >= 1_000_000:
            formatted_volume = f"${volume_24h/1_000_000:.2f}M"
        elif volume_24h >= 1_000:
            formatted_volume = f"${volume_24h/1_000:.2f}K"
        else:
            formatted_volume = f"${volume_24h:.2f}"
        
        text = f"💎 **$EMP 24h Volume:** {formatted_volume}"
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='Markdown')
    except requests.exceptions.Timeout:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⏰ Request timeout. Please try again.")
        return
    except Exception as e:
        print(f"Error in send_daily_volume: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Error fetching EMP volume data.")
        return

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("billi", send_price))
app.add_handler(CommandHandler("price", send_detailed_price))
app.add_handler(CommandHandler("empprice", send_emp_price))
app.add_handler(CommandHandler("btcprice", send_btc_price))
app.add_handler(CommandHandler("ethprice", send_eth_price))
app.add_handler(CommandHandler("performance", send_performance_comparison))
app.add_handler(CommandHandler("startmonitor", start_monitoring))
app.add_handler(CommandHandler("stopmonitor", stop_monitoring))
app.add_handler(CommandHandler("status", check_status))
app.add_handler(CommandHandler("test", test_connection))
app.add_handler(CommandHandler("last5", show_last_5_transactions))
app.add_handler(CommandHandler("vol", send_daily_volume))

# Talos-specific commands
app.add_handler(CommandHandler("last5talos", show_last_5_talos_transactions))
app.add_handler(CommandHandler("starttalos", start_talos_monitoring))
app.add_handler(CommandHandler("stoptalos", stop_talos_monitoring))
app.add_handler(CommandHandler("testtalos", test_talos_connection))

app.add_handler(MessageHandler(filters.TEXT, handle_wen_commands))

# Don't auto-start monitoring - wait for /startmonitor command
print("Bot started. Use /startmonitor in a group to begin EMP transaction monitoring.")
print("Use /starttalos in a group to begin Talos transaction monitoring.")

app.run_polling()