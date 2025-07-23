import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from web3 import Web3
from config import TOKENS, UNISWAP_POOL_ABI, get_token_config
from price_utils import get_cached_prices, unified_etherscan_api_call

# Track processed transactions to avoid duplicates (per token)
processed_transactions = {
    "emp": set(),
    "talos": set()
}

def decode_swap_event_data(data: str, topics: List[str]) -> Optional[Dict]:
    """
    Decode raw log data for Swap events
    Returns: Dict with amount0, amount1, sqrtPriceX96, liquidity, tick
    """
    try:
        # Swap event signature: Swap(address,address,int256,int256,uint160,uint128,int24)
        # Topics: [event_signature, sender, recipient]
        # Data: [amount0, amount1, sqrtPriceX96, liquidity, tick]
        
        if len(topics) < 1:
            print(f"❌ No topics found")
            return None
            
        # Check if this is a Swap event (should have 3 topics: signature, sender, recipient)
        if len(topics) < 3:
            print(f"⚠️ Not enough topics for Swap event (found {len(topics)}, need 3). This might be a different event type.")
            print(f"🔍 Topics: {topics}")
            print(f"🔍 Data length: {len(data)} chars")
            
            # Try to identify the event type from the first topic
            if len(topics) >= 1:
                event_signature = topics[0]
                print(f"🔍 Event signature: {event_signature}")
                
                # Known event signatures
                if event_signature == "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67":
                    print(f"🔍 This is a Swap event!")
                elif event_signature == "0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde":
                    print(f"🔍 This is a Mint event!")
                elif event_signature == "0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c":
                    print(f"🔍 This is a Burn event!")
                elif event_signature == "0xbdbd97176f35c5d130b373e3e7ac36b1b5d3e3f42b9f42a249f2a0b8294e0c4":
                    print(f"🔍 This is a Flash event!")
                else:
                    print(f"🔍 Unknown event signature: {event_signature}")
            
            return None
            
        # Remove '0x' prefix and decode data
        if data.startswith('0x'):
            data = data[2:]
        
        # Each parameter is 32 bytes (64 hex chars)
        # amount0, amount1: int256 (32 bytes each)
        # sqrtPriceX96: uint160 (32 bytes)
        # liquidity: uint128 (32 bytes) 
        # tick: int24 (32 bytes)
        
        if len(data) < 160:  # 5 * 32 bytes = 160 hex chars
            print(f"❌ Data too short: {len(data)} chars")
            return None
            
        # Extract each parameter
        amount0_hex = data[0:64]
        amount1_hex = data[64:128]
        sqrtPriceX96_hex = data[128:192]
        liquidity_hex = data[192:256]
        tick_hex = data[256:320]
        
        # Convert hex to integers (handle signed integers for amount0, amount1, tick)
        def hex_to_signed_int(hex_str: str) -> int:
            value = int(hex_str, 16)
            # Check if negative (two's complement)
            if value > 2**255 - 1:
                value = value - 2**256
            return value
            
        def hex_to_unsigned_int(hex_str: str) -> int:
            return int(hex_str, 16)
        
        decoded = {
            "amount0": hex_to_signed_int(amount0_hex),
            "amount1": hex_to_signed_int(amount1_hex),
            "sqrtPriceX96": hex_to_unsigned_int(sqrtPriceX96_hex),
            "liquidity": hex_to_unsigned_int(liquidity_hex),
            "tick": hex_to_signed_int(tick_hex),
            "sender": topics[1] if len(topics) > 1 else None,
            "recipient": topics[2] if len(topics) > 2 else None
        }
        
        print(f"✅ Decoded swap data: amount0={decoded['amount0']}, amount1={decoded['amount1']}")
        return decoded
        
    except Exception as e:
        print(f"❌ Error decoding swap event data: {e}")
        return None

def get_transaction_details(tx_hash: str, token_key: str = "emp") -> Optional[dict]:
    """Get transaction details from unified Etherscan V2 API"""
    token_config = get_token_config(token_key)
    if not token_config:
        print(f"Token configuration not found for {token_key}")
        return None
    
    chainid = token_config.get("chainid", 1)  # Default to Ethereum if not specified
    
    return unified_etherscan_api_call(
        module="proxy",
        action="eth_getTransactionByHash",
        chainid=chainid,
        txhash=tx_hash
    )

def get_token_order(pool_address: str, token_address: str, network: str, w3: Web3) -> Optional[str]:
    """
    Determine which token is token0 and which is token1 in the pool
    Returns: 'token0' if the tracked token is token0, 'token1' if it's token1
    """
    try:
        # Create pool contract instance
        pool_contract = w3.eth.contract(
            address=Web3.to_checksum_address(pool_address),
            abi=UNISWAP_POOL_ABI
        )
        
        # Get token0 and token1 addresses
        token0_address = pool_contract.functions.token0().call()
        token1_address = pool_contract.functions.token1().call()
        
        print(f"🔍 Pool {pool_address}:")
        print(f"  Token0: {token0_address}")
        print(f"  Token1: {token1_address}")
        print(f"  Tracked Token: {token_address}")
        
        # Compare addresses (case-insensitive)
        if token0_address.lower() == token_address.lower():
            print(f"✅ Tracked token is Token0")
            return 'token0'
        elif token1_address.lower() == token_address.lower():
            print(f"✅ Tracked token is Token1")
            return 'token1'
        else:
            print(f"❌ Tracked token not found in pool!")
            return None
            
    except Exception as e:
        print(f"❌ Error getting token order: {e}")
        return None

def get_last_5_transactions(token_key: str = "emp", w3: Web3 = None) -> Optional[List[Dict]]:
    """Get the last 5 buy/sell transactions from the Uniswap pool for a specific token"""
    token_config = get_token_config(token_key)
    if not token_config:
        print(f"Token configuration not found for {token_key}")
        return None
    
    if not w3:
        print(f"Web3 connection not provided for {token_key}")
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

def get_logs_via_etherscan(from_block: int, to_block: int, address: str, token_key: str = "emp") -> Optional[List]:
    """
    Get logs via unified Etherscan V2 API
    
    Args:
        from_block: Starting block number
        to_block: Ending block number
        address: Contract address to filter by
        token_key: Token key for chain configuration
    
    Returns:
        List of log entries or None if failed
    """
    token_config = get_token_config(token_key)
    if not token_config:
        print(f"Token configuration not found for {token_key}")
        return None
    
    chainid = token_config.get("chainid", 1)
    
    return unified_etherscan_api_call(
        module="logs",
        action="getLogs",
        chainid=chainid,
        fromBlock=from_block,
        toBlock=to_block,
        address=address
    )

def process_swap_event(event: Dict, tx_hash: str, token_key: str, w3: Web3) -> Tuple[str, str]:
    """
    Process a swap event and return formatted message and direction
    
    Args:
        event: Swap event data
        tx_hash: Transaction hash
        token_key: Token key for configuration
        w3: Web3 connection
    
    Returns:
        Tuple of (formatted_message, direction)
    """
    try:
        # Get token configuration
        token_config = get_token_config(token_key)
        if not token_config:
            return f"🔄 **New Swap Detected**\n\n🔗 [View Transaction](https://etherscan.io/tx/{tx_hash})", "🔄 SWAP"
        
        token_symbol = token_config["symbol"]
        explorer_url = token_config["explorer_url"]
        token_address = token_config["token_address"]
        pool_address = token_config["pool_address"]
        network = token_config["network"]
        
        # Get swap event data - handle different event structures
        if "args" in event and "amount0" in event["args"] and "amount1" in event["args"]:
            # Standard Uniswap V3 Swap event structure
            amount0_raw = event["args"]["amount0"]
            amount1_raw = event["args"]["amount1"]
        elif "data" in event and "topics" in event:
            # Raw log event - try to decode it
            print(f"[{token_key.upper()}] 🔍 Attempting to decode raw log data...")
            decoded_data = decode_swap_event_data(event["data"], event["topics"])
            
            if decoded_data and "amount0" in decoded_data and "amount1" in decoded_data:
                amount0_raw = decoded_data["amount0"]
                amount1_raw = decoded_data["amount1"]
                print(f"[{token_key.upper()}] ✅ Successfully decoded raw log data")
            else:
                print(f"[{token_key.upper()}] ❌ Failed to decode raw log data - this might be a non-Swap event (Mint/Burn/Flash)")
                return f"🔄 **Pool Activity Detected**\n\n🔗 [{tx_hash[:10]}...]({explorer_url}/tx/{tx_hash})", "POOL_ACTIVITY"
        else:
            # Unknown event structure
            print(f"[{token_key.upper()}] ⚠️ Unknown event structure: {event.keys()}")
            return f"🔄 **Transaction Detected**\n\n🔗 [{tx_hash[:10]}...]({explorer_url}/tx/{tx_hash})", "SWAP"
        
        # Determine token order in the pool
        print(f"[{token_key.upper()}] Determining token order for pool {pool_address}...")
        token_order = get_token_order(pool_address, token_address, network, w3)
        
        if not token_order:
            print(f"[{token_key.upper()}] ❌ CRITICAL: Could not determine token order. Aborting format.")
            return f"⚠️ **Swap Detected (Unknown Direction)**\n\n🔗 [{tx_hash[:10]}...]({explorer_url}/tx/{tx_hash})", "UNKNOWN"

        print(f"[{token_key.upper()}] ✅ Token is {token_order}")

        # Assign amounts based on token order
        if token_order == 'token0':
            tracked_token_amount_raw = amount0_raw
            eth_amount_raw = amount1_raw
        else:  # token_order == 'token1'
            tracked_token_amount_raw = amount1_raw
            eth_amount_raw = amount0_raw
            
        # Convert raw amounts to human-readable format (assuming 18 decimals for both)
        tracked_token_amount = abs(tracked_token_amount_raw) / (10 ** 18)
        eth_amount = abs(eth_amount_raw) / (10 ** 18)

        # Determine direction (BUY or SELL)
        if tracked_token_amount_raw < 0:
            direction = "🟢 BUY"
        elif tracked_token_amount_raw > 0:
            direction = "🔴 SELL"
        else:
            direction = "🔄 SWAP"

        print(f"[{token_key.upper()}] ✅ Detected {direction}: {tracked_token_amount:.3f} {token_symbol} for {eth_amount:.3f} ETH")

        # Get prices and calculate USD value
        token_usd_price, eth_usd_price = get_cached_prices("T" if token_symbol == "T" else "EMP")
        total_usd = eth_amount * eth_usd_price
        
        # Calculate the price per token from this specific transaction
        if tracked_token_amount > 0 and total_usd > 0:
            price_per_token = total_usd / tracked_token_amount
        else:
            price_per_token = 0  # Fallback

        # Build the message
        emoji_count = max(1, int(total_usd / 50)) if total_usd > 0 else 1
        action_emojis = ""

        if direction == "🟢 BUY":
            title = f"🟢 **BOUGHT ${token_symbol}** 🟢"
            # Build buy emojis (🍑🍒)
            for i in range(emoji_count):
                action_emojis += "🍑" if i % 2 == 0 else "🍒"
            
            details = (
                f"💰 **${total_usd:,.2f}** ({eth_amount:.3f} ETH)\n"
                f"💎 **{tracked_token_amount:,.3f} ${token_symbol}**\n"
            )

        elif direction == "🔴 SELL":
            title = f"🔴 **SOLD ${token_symbol}** 🔴"
            # Build sell emojis (🍆🍌)
            for i in range(emoji_count):
                action_emojis += "🍆" if i % 2 == 0 else "🍌"

            details = (
                f"💰 **${total_usd:,.2f}** ({eth_amount:.3f} ETH)\n"
                f"💎 **{tracked_token_amount:,.3f} ${token_symbol}**\n"
            )
        else:  # SWAP or UNKNOWN
            return f"🔄 **Swap Detected**\n\n🔗 [{tx_hash[:10]}...]({explorer_url}/tx/{tx_hash})", "SWAP"

        # Assemble the final message
        message = (
            f"{title}\n\n"
            f"{action_emojis}\n\n"
            f"{details}"
            f"💵 **${price_per_token:,.4f} per ${token_symbol}**\n\n"
            f"🔗 **Transaction:** [View TX]({explorer_url}/tx/{tx_hash})"
        )
        
        return message, direction
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR in process_swap_event for {token_key}: {e}")
        # Return a safe fallback message
        explorer_url = get_token_config(token_key).get("explorer_url", "https://etherscan.io")
        return f"⚠️ **Error processing transaction**\n\n🔗 [{tx_hash[:10]}...]({explorer_url}/tx/{tx_hash})", "ERROR"

def format_last_5_transactions(transactions: List[Dict], token_key: str = "emp", w3: Web3 = None) -> str:
    """Format the last 5 transactions into a readable message for a specific token"""
    if not transactions:
        return "❌ No recent buy/sell transactions found."
    
    token_config = get_token_config(token_key)
    if not token_config:
        return "❌ Token configuration not found."
    
    token_symbol = token_config["symbol"]
    network = token_config["network"]
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