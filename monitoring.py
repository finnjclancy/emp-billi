import asyncio
from typing import Dict, Optional
from web3 import Web3
from config import get_token_config, UNISWAP_POOL_ABI
from transaction_utils import process_swap_event, get_transaction_details, get_logs_via_etherscan, processed_transactions
from betting_system import start_new_betting_round, resolve_betting_round, schedule_daily_leaderboard
import os

# Store the group chat IDs when monitoring starts
monitoring_groups = {}

# Track monitoring tasks to properly stop them
monitoring_tasks = {}

async def monitor_transactions(bot, token_key: str = "emp", group_id: int = None, send_transaction_messages: bool = True):
    """Monitor Uniswap pool for new transactions for a specific token"""
    global monitoring_groups, processed_transactions, monitoring_tasks
    
    token_config = get_token_config(token_key)
    if not token_config:
        print(f"Token configuration not found for {token_key}")
        return
    
    network = token_config["network"]
    w3 = get_w3_connection(network)
    
    if not w3:
        print(f"Web3 not configured for {network}. Skipping transaction monitoring for {token_key}.")
        return
    
    if not group_id:
        print(f"No group chat ID set for {token_key}. Use /startmonitor in a group first.")
        return
    
    # Store the task reference for proper stopping
    task = asyncio.current_task()
    monitoring_tasks[token_key] = task
    
    try:
        # Create contract instance
        pool_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_config["pool_address"]),
            abi=UNISWAP_POOL_ABI
        )
        
        mode_text = "betting-only" if not send_transaction_messages else "full monitoring"
        print(f"Starting {mode_text} for {token_key} pool: {token_config['pool_address']}")
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
        
        # Set polling interval based on network
        if network == "ethereum":
            polling_interval = 15  # 15 seconds for Ethereum
            max_blocks_per_call = 5  # Process more blocks for Ethereum
            skip_threshold = 8  # Skip if more than 8 blocks behind
        else:  # arbitrum
            polling_interval = 1  # 1 second for Arbitrum
            max_blocks_per_call = 50  # Process up to 50 blocks for Arbitrum (conservative)
            skip_threshold = 100  # Skip if more than 100 blocks behind
        
        while token_key in monitoring_groups:  # Check if monitoring should continue
            try:
                # Get new blocks with rate limiting
                try:
                    print(f"🔍 [{token_key.upper()}] Getting current block number... (1 credit)")
                    current_block = w3.eth.block_number
                    print(f"✅ [{token_key.upper()}] Current block: {current_block}")
                except Exception as e:
                    if "429" in str(e) or "Too Many Requests" in str(e):
                        print(f"⚠️ Rate limited by {network} provider for {token_key}, continuing immediately...")
                        continue
                    else:
                        print(f"❌ Error getting block number for {token_key}: {e}")
                        await asyncio.sleep(10)
                        continue
                
                if current_block > latest_block:
                    # Check for swap events in new blocks (smaller batches for efficiency)
                    try:
                        blocks_to_process = current_block - latest_block
                        
                        # Skip processing if too many blocks to avoid rate limits
                        if blocks_to_process > skip_threshold:
                            print(f"⚠️ [{token_key.upper()}] Too many blocks to process ({blocks_to_process}), skipping to avoid rate limits. Latest: {latest_block}, Current: {current_block}")
                            latest_block = current_block - 2  # Skip to last 2 blocks
                            continue
                        
                        # Process blocks in smaller batches
                        blocks_processed = 0
                        while blocks_processed < blocks_to_process:
                            batch_size = min(max_blocks_per_call, blocks_to_process - blocks_processed)
                            start_block = latest_block + blocks_processed + 1
                            end_block = start_block + batch_size - 1
                            
                            print(f"🔍 [{token_key.upper()}] Getting events from blocks {start_block}-{end_block} ({batch_size} blocks)... (~10 credits)")
                            
                            try:
                                # Get events from the pool contract
                                events = pool_contract.events.Swap.get_logs(
                                    fromBlock=start_block,
                                    toBlock=end_block
                                )
                                
                                if not events:
                                    print(f"🔍 [{token_key.upper()}] No Swap events found, checking for other event types...")
                                    # Try getting logs via Etherscan as fallback
                                    events = get_logs_via_etherscan(
                                        token_config["pool_address"],
                                        start_block,
                                        end_block,
                                        token_key
                                    )
                                    if events is None:
                                        events = []
                                
                                print(f"✅ [{token_key.upper()}] Retrieved logs via Web3")
                                print(f"✅ [{token_key.upper()}] Found {len(events)} events from blocks {start_block} to {end_block} for {token_key.upper()} on {network.upper()}")
                                
                                # Process each event
                                for event in events:
                                    await process_transaction_event(event, token_key, group_id, bot, w3, send_transaction_messages)
                                
                                blocks_processed += batch_size
                                
                            except Exception as e:
                                if "429" in str(e) or "Too Many Requests" in str(e):
                                    print(f"⚠️ Rate limited during event processing for {token_key}, waiting 30 seconds...")
                                    await asyncio.sleep(30)
                                    continue
                                else:
                                    print(f"❌ Error processing events for {token_key}: {e}")
                                    blocks_processed += batch_size
                                    continue
                        
                        latest_block = current_block
                        
                    except Exception as e:
                        if "429" in str(e) or "Too Many Requests" in str(e):
                            print(f"⚠️ Rate limited during block processing for {token_key}, waiting 30 seconds...")
                            await asyncio.sleep(30)
                            continue
                        else:
                            print(f"❌ Error processing blocks for {token_key}: {e}")
                            await asyncio.sleep(10)
                            continue
                
                # Wait before next poll
                await asyncio.sleep(polling_interval)
                
            except Exception as e:
                print(f"❌ Error in monitoring loop for {token_key}: {e}")
                await asyncio.sleep(10)
                continue
    
    except asyncio.CancelledError:
        print(f"🏁 Monitoring task cancelled for {token_key}")
    except Exception as e:
        print(f"❌ Error in monitoring task for {token_key}: {e}")
    finally:
        # Clean up task reference
        if token_key in monitoring_tasks:
            del monitoring_tasks[token_key]
        print(f"🏁 Monitoring task ended for {token_key}")

async def monitor_transactions_buy_only(bot, token_key: str, group_id: int):
    """Monitor transactions for buy-only betting - processes all transactions but only uses buys for betting"""
    try:
        print(f"🟢 [{token_key.upper()}] Starting BUY-ONLY transaction monitoring for group {group_id}")
        print(f"📡 SERVER LOG: Starting {token_key.upper()} BUY-ONLY monitoring for group {group_id}")
        
        token_config = get_token_config(token_key)
        network = token_config["network"]
        
        # Initialize Web3 connection
        w3 = get_w3_connection(network)
        if not w3 or not w3.is_connected():
            print(f"❌ Failed to connect to {network} network")
            return
        
        # Store the group ID and task
        monitoring_groups[token_key] = group_id
        
        # Create contract instance
        pool_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_config["pool_address"]),
            abi=UNISWAP_POOL_ABI
        )
        
        # Get starting block
        latest_block = w3.eth.block_number - 1
        MONITORING_INTERVAL = 5  # seconds
        skip_threshold = 500
        max_blocks_per_call = 50
        
        print(f"✅ [{token_key.upper()}] Connected to {network} network. Starting buy-only monitoring from block {latest_block}")
        
        while token_key in monitoring_groups and monitoring_groups[token_key] == group_id:
            try:
                current_block = w3.eth.block_number
                print(f"🔍 [{token_key.upper()}] Getting current block number... (1 credit)")
                print(f"✅ [{token_key.upper()}] Current block: {current_block}")
                
                if current_block > latest_block:
                    blocks_to_process = current_block - latest_block
                    
                    if blocks_to_process > skip_threshold:
                        print(f"⚠️ [{token_key.upper()}] Too many blocks to process ({blocks_to_process}), skipping to avoid rate limits. Latest: {latest_block}, Current: {current_block}")
                        latest_block = current_block - 2
                        continue
                    
                    # Process blocks in batches
                    blocks_processed = 0
                    while blocks_processed < blocks_to_process:
                        batch_size = min(max_blocks_per_call, blocks_to_process - blocks_processed)
                        start_block = latest_block + blocks_processed + 1
                        end_block = start_block + batch_size - 1
                        
                        print(f"🔍 [{token_key.upper()}] Getting events from blocks {start_block}-{end_block} ({batch_size} blocks) for buy-only... (~10 credits)")
                        
                        try:
                            # Get events from the pool contract
                            events = pool_contract.events.Swap.get_logs(
                                fromBlock=start_block,
                                toBlock=end_block
                            )
                            
                            if not events:
                                print(f"🔍 [{token_key.upper()}] No Swap events found, checking for other event types...")
                                events = get_logs_via_etherscan(
                                    token_config["pool_address"],
                                    start_block,
                                    end_block,
                                    token_key
                                )
                                if events is None:
                                    events = []
                            
                            print(f"✅ [{token_key.upper()}] Retrieved logs via Web3")
                            print(f"✅ [{token_key.upper()}] Found {len(events)} events from blocks {start_block} to {end_block} for {token_key.upper()} (buy-only mode)")
                            
                            # Process each event in buy-only mode
                            for event in events:
                                await process_transaction_event_buy_only(event, token_key, group_id, bot, w3)
                            
                            blocks_processed += batch_size
                            
                        except Exception as e:
                            if "429" in str(e) or "Too Many Requests" in str(e):
                                print(f"⚠️ Rate limited during buy-only event processing for {token_key}, waiting 30 seconds...")
                                await asyncio.sleep(30)
                                continue
                            else:
                                print(f"❌ Error processing buy-only events for {token_key}: {e}")
                                blocks_processed += batch_size
                                continue
                    
                    latest_block = current_block
                
                await asyncio.sleep(MONITORING_INTERVAL)
                
            except Exception as e:
                if "429" in str(e) or "Too Many Requests" in str(e):
                    print(f"⚠️ Rate limited in buy-only monitoring for {token_key}, waiting 30 seconds...")
                    await asyncio.sleep(30)
                    continue
                else:
                    print(f"❌ Error in buy-only monitoring loop for {token_key}: {e}")
                    await asyncio.sleep(5)
                    continue
                    
    except Exception as e:
        print(f"❌ Critical error in monitor_transactions_buy_only for {token_key}: {e}")
    finally:
        print(f"🏁 Buy-only monitoring task ended for {token_key}")

async def process_transaction_event(event: Dict, token_key: str, group_id: int, bot, w3: Web3, send_transaction_messages: bool = True):
    """Process a single transaction event"""
    try:
        # Get transaction hash
        tx_hash = event.get('transactionHash', 'unknown')
        if isinstance(tx_hash, bytes):
            tx_hash = tx_hash.hex()
        
        # Skip if we've already processed this transaction
        if tx_hash in processed_transactions[token_key]:
            print(f"⏭️ [{token_key.upper()}] Skipping already processed transaction: {tx_hash[:10]}...")
            return
        
        # Add to processed set
        processed_transactions[token_key].add(tx_hash)
        
        print(f"🔍 [{token_key.upper()}] Processing new transaction: {tx_hash[:10]}...")
        
        # Process the swap event to get formatted message and price
        result = process_swap_event(event, tx_hash, token_key, w3)
        
        if len(result) == 3:
            message, direction, price_per_token = result
        else:
            message, direction = result
            price_per_token = None
        
        # Send transaction message if enabled
        if send_transaction_messages:
            # Get token config for images
            token_config = get_token_config(token_key)
            
            # Process both BUY and SELL transactions
            if direction == "🔴 SELL":
                try:
                    # Use sell-specific image
                    image_path = token_config["sell_image"]
                    if os.path.exists(image_path):
                        with open(image_path, 'rb') as photo:
                            await bot.send_photo(
                                chat_id=group_id,
                                photo=photo,
                                caption=message,
                                parse_mode='Markdown'
                            )
                        print(f"📤 [{token_key.upper()}] Posted SELL transaction with image: {tx_hash[:10]}...")
                    else:
                        # Fallback to text-only
                        await bot.send_message(
                            chat_id=group_id,
                            text=message,
                            parse_mode='Markdown',
                            disable_web_page_preview=True
                        )
                        print(f"📤 [{token_key.upper()}] Posted SELL transaction (text-only): {tx_hash[:10]}...")
                except Exception as e:
                    print(f"❌ Error sending SELL message for {token_key}: {e}")
                    
            elif direction == "🟢 BUY":
                try:
                    # Use buy-specific image
                    image_path = token_config["buy_image"]
                    if os.path.exists(image_path):
                        with open(image_path, 'rb') as photo:
                            await bot.send_photo(
                                chat_id=group_id,
                                photo=photo,
                                caption=message,
                                parse_mode='Markdown'
                            )
                        print(f"📤 [{token_key.upper()}] Posted BUY transaction with image: {tx_hash[:10]}...")
                    else:
                        # Fallback to text-only
                        await bot.send_message(
                            chat_id=group_id,
                            text=message,
                            parse_mode='Markdown',
                            disable_web_page_preview=True
                        )
                        print(f"📤 [{token_key.upper()}] Posted BUY transaction (text-only): {tx_hash[:10]}...")
                except Exception as e:
                    print(f"❌ Error sending BUY message for {token_key}: {e}")
            else:
                # Handle other transaction types (SWAP, etc.)
                try:
                    await bot.send_message(
                        chat_id=group_id,
                        text=message,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                    print(f"📤 [{token_key.upper()}] Posted SWAP transaction: {tx_hash[:10]}...")
                except Exception as e:
                    print(f"❌ Error sending text-only message for {token_key}: {e}")
        else:
            print(f"🎲 [{token_key.upper()}] Skipping transaction message (betting-only mode): {tx_hash[:10]}...")
        
        # Small delay to avoid rate limits
        await asyncio.sleep(1)
        
        # Handle betting system with transaction price
        await handle_betting_for_transaction(token_key, price_per_token, group_id, bot)
        
    except Exception as e:
        print(f"❌ Error processing transaction event for {token_key}: {e}")

async def process_transaction_event_buy_only(event: Dict, token_key: str, group_id: int, bot, w3: Web3):
    """Process a single transaction event for buy-only betting mode"""
    try:
        # Get transaction hash
        tx_hash = event.get('transactionHash', 'unknown')
        if isinstance(tx_hash, bytes):
            tx_hash = tx_hash.hex()
        
        # Skip if we've already processed this transaction
        if tx_hash in processed_transactions[token_key]:
            print(f"⏭️ [{token_key.upper()}] Skipping already processed transaction (buy-only): {tx_hash[:10]}...")
            return
        
        # Add to processed set
        processed_transactions[token_key].add(tx_hash)
        
        print(f"🔍 [{token_key.upper()}] Processing new transaction for buy-only betting: {tx_hash[:10]}...")
        
        # Process the swap event to get formatted message and price
        result = process_swap_event(event, tx_hash, token_key, w3)
        
        if len(result) == 3:
            message, direction, price_per_token = result
        else:
            message, direction = result
            price_per_token = None
        
        # Never send transaction messages in buy-only mode
        print(f"🟢 [{token_key.upper()}] Skipping transaction message (buy-only mode): {tx_hash[:10]}... Direction: {direction}")
        
        # Small delay to avoid rate limits
        await asyncio.sleep(1)
        
        # Handle buy-only betting system - only process BUY transactions for betting
        await handle_buy_only_betting_for_transaction(token_key, price_per_token, group_id, bot, direction)
        
    except Exception as e:
        print(f"❌ Error processing transaction event for buy-only {token_key}: {e}")

async def handle_betting_for_transaction(token_key: str, transaction_price: float, group_id: int, bot):
    """Handle betting system for a new transaction using the transaction price"""
    try:
        print(f"🎲 [{token_key.upper()}] Starting betting system with transaction price: ${transaction_price}")
        
        if transaction_price is None or transaction_price <= 0:
            print(f"❌ [{token_key.upper()}] Invalid transaction price: {transaction_price}")
            return
        
        # First, resolve any existing betting round
        result_message = resolve_betting_round(token_key, transaction_price, bot)
        if result_message:
            print(f"🏆 [{token_key.upper()}] Resolving betting round...")
            await bot.send_message(
                chat_id=group_id,
                text=result_message,
                parse_mode='Markdown'
            )
            await asyncio.sleep(2)  # Small delay between messages
        
        # Start new betting round
        print(f"🎲 [{token_key.upper()}] Starting new betting round...")
        betting_message, keyboard = start_new_betting_round(token_key, transaction_price, group_id, bot)
        await bot.send_message(
            chat_id=group_id,
            text=betting_message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        print(f"✅ [{token_key.upper()}] Betting round started successfully!")
        
    except Exception as e:
        print(f"❌ Error handling betting for {token_key}: {e}")
        import traceback
        traceback.print_exc()

async def handle_buy_only_betting_for_transaction(token_key: str, transaction_price: float, group_id: int, bot, direction: str):
    """Handle buy-only betting system - only processes BUY transactions for betting"""
    try:
        # Only process BUY transactions for betting
        if direction != "🟢 BUY":
            print(f"🔴 [{token_key.upper()}] Skipping SELL transaction for buy-only betting: direction={direction}")
            return
        
        print(f"🟢 [{token_key.upper()}] Processing BUY transaction for buy-only betting with price: ${transaction_price}")
        
        if transaction_price is None or transaction_price <= 0:
            print(f"❌ [{token_key.upper()}] Invalid transaction price: {transaction_price}")
            return
        
        # First, resolve any existing betting round
        result_message = resolve_betting_round(token_key, transaction_price, bot)
        if result_message:
            print(f"🏆 [{token_key.upper()}] Resolving betting round with BUY...")
            await bot.send_message(
                chat_id=group_id,
                text=result_message,
                parse_mode='Markdown'
            )
            await asyncio.sleep(2)  # Small delay between messages
        
        # Start new betting round
        print(f"🟢 [{token_key.upper()}] Starting new betting round from BUY...")
        betting_message, keyboard = start_new_betting_round(token_key, transaction_price, group_id, bot)
        await bot.send_message(
            chat_id=group_id,
            text=betting_message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        print(f"✅ [{token_key.upper()}] Buy-only betting round started successfully!")
        
    except Exception as e:
        print(f"❌ Error handling buy-only betting for {token_key}: {e}")
        import traceback
        traceback.print_exc()

def get_w3_connection(network: str) -> Optional[Web3]:
    """Get Web3 connection for a specific network"""
    from config import INFURA_URL, ARBITRUM_RPC_URL
    
    if network == "ethereum" and INFURA_URL:
        return Web3(Web3.HTTPProvider(INFURA_URL))
    elif network == "arbitrum" and ARBITRUM_RPC_URL:
        return Web3(Web3.HTTPProvider(ARBITRUM_RPC_URL))
    else:
        return None

def get_monitoring_status() -> Dict:
    """Get current monitoring status"""
    status = {
        "active_monitoring": {},
        "processed_transactions": {}
    }
    
    # Check active monitoring for each token
    for token_key in ["emp", "talos"]:
        token_config = get_token_config(token_key)
        if token_config:
            status["active_monitoring"][token_key] = {
                "active": token_key in monitoring_groups,
                "group_id": monitoring_groups.get(token_key),
                "pool_address": token_config["pool_address"],
                "network": token_config["network"]
            }
            status["processed_transactions"][token_key] = len(processed_transactions.get(token_key, set()))
    
    return status 