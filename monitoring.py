import asyncio
from typing import Dict, Optional
from web3 import Web3
from config import get_token_config, UNISWAP_POOL_ABI
from transaction_utils import process_swap_event, get_transaction_details, get_logs_via_etherscan, processed_transactions

# Store the group chat IDs when monitoring starts
monitoring_groups = {}

# Track monitoring tasks to properly stop them
monitoring_tasks = {}

async def monitor_transactions(bot, token_key: str = "emp", group_id: int = None):
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
                        
                        if blocks_to_process > max_blocks_per_call:
                            # Process in chunks
                            total_chunks = (blocks_to_process + max_blocks_per_call - 1) // max_blocks_per_call
                            print(f"📊 [{token_key.upper()}] Processing {blocks_to_process} blocks in {total_chunks} chunks of {max_blocks_per_call} blocks each")
                            
                            for chunk_start in range(latest_block + 1, current_block + 1, max_blocks_per_call):
                                chunk_end = min(chunk_start + max_blocks_per_call - 1, current_block)
                                chunk_size = chunk_end - chunk_start + 1
                                estimated_credits = max(10, chunk_size * 2)  # Base 10 + 2 per block
                                
                                # Get swap events from this chunk
                                print(f"🔍 [{token_key.upper()}] Getting events from blocks {chunk_start}-{chunk_end} ({chunk_size} blocks)... (~{estimated_credits} credits)")
                                
                                # Try to get Swap events first
                                swap_events = pool_contract.events.Swap.get_logs(
                                    fromBlock=chunk_start,
                                    toBlock=chunk_end
                                )
                                
                                # If no Swap events, try other event types
                                if len(swap_events) == 0:
                                    print(f"🔍 [{token_key.upper()}] No Swap events found, checking for other event types...")
                                    
                                    # Try to get any events from this contract using Web3 first, then fallback to Etherscan API
                                    all_logs = None
                                    try:
                                        all_logs = w3.eth.get_logs({
                                            'address': Web3.to_checksum_address(token_config["pool_address"]),
                                            'fromBlock': chunk_start,
                                            'toBlock': chunk_end
                                        })
                                        print(f"✅ [{token_key.upper()}] Retrieved logs via Web3")
                                    except Exception as e:
                                        print(f"⚠️ Web3 get_logs failed for {token_key}: {e}")
                                        # Fallback to Etherscan API
                                        try:
                                            print(f"🔍 [{token_key.upper()}] Trying Etherscan API fallback...")
                                            all_logs = get_logs_via_etherscan(
                                                chunk_start, 
                                                chunk_end, 
                                                token_config["pool_address"], 
                                                token_key
                                            )
                                            if all_logs:
                                                print(f"✅ [{token_key.upper()}] Retrieved logs via Etherscan API")
                                            else:
                                                print(f"❌ Etherscan API also failed for {token_key}")
                                        except Exception as e2:
                                            print(f"❌ Etherscan API fallback also failed for {token_key}: {e2}")
                                    
                                    if all_logs and len(all_logs) > 0:
                                        print(f"✅ [{token_key.upper()}] Found {len(all_logs)} total events from blocks {chunk_start} to {chunk_end} for {token_key.upper()} on {network.upper()}")
                                        
                                        # Process these as generic events
                                        for log in all_logs:
                                            # Convert generic log to event format
                                            event = {
                                                "transactionHash": log["transactionHash"],
                                                "blockNumber": log["blockNumber"],
                                                "data": log.get("data", ""),
                                                "topics": log.get("topics", [])
                                            }
                                            await process_transaction_event(event, token_key, group_id, bot, w3)
                                    
                                    else:
                                        print(f"✅ [{token_key.upper()}] Found 0 events from blocks {chunk_start} to {chunk_end} for {token_key.upper()} on {network.upper()}")
                                else:
                                    print(f"✅ [{token_key.upper()}] Found {len(swap_events)} events from blocks {chunk_start} to {chunk_end} for {token_key.upper()} on {network.upper()}")
                                    
                                    for event in swap_events:
                                        await process_transaction_event(event, token_key, group_id, bot, w3)
                        else:
                            # Process all blocks in one call (small range)
                            estimated_credits = max(10, blocks_to_process * 2)  # Base 10 + 2 per block
                            print(f"🔍 [{token_key.upper()}] Getting events from blocks {latest_block + 1}-{current_block} ({blocks_to_process} blocks)... (~{estimated_credits} credits)")
                            
                            # Try to get Swap events first
                            swap_events = pool_contract.events.Swap.get_logs(
                                fromBlock=latest_block + 1,
                                toBlock=current_block
                            )
                            
                            # If no Swap events, try other event types
                            if len(swap_events) == 0:
                                print(f"🔍 [{token_key.upper()}] No Swap events found, checking for other event types...")
                                
                                # Try to get any events from this contract using Web3 first, then fallback to Etherscan API
                                all_logs = None
                                try:
                                    all_logs = w3.eth.get_logs({
                                        'address': Web3.to_checksum_address(token_config["pool_address"]),
                                        'fromBlock': latest_block + 1,
                                        'toBlock': current_block
                                    })
                                    print(f"✅ [{token_key.upper()}] Retrieved logs via Web3")
                                except Exception as e:
                                    print(f"⚠️ Web3 get_logs failed for {token_key}: {e}")
                                    # Fallback to Etherscan API
                                    try:
                                        print(f"🔍 [{token_key.upper()}] Trying Etherscan API fallback...")
                                        all_logs = get_logs_via_etherscan(
                                            latest_block + 1, 
                                            current_block, 
                                            token_config["pool_address"], 
                                            token_key
                                        )
                                        if all_logs:
                                            print(f"✅ [{token_key.upper()}] Retrieved logs via Etherscan API")
                                        else:
                                            print(f"❌ Etherscan API also failed for {token_key}")
                                    except Exception as e2:
                                        print(f"❌ Etherscan API fallback also failed for {token_key}: {e2}")
                                
                                if all_logs and len(all_logs) > 0:
                                    print(f"✅ [{token_key.upper()}] Found {len(all_logs)} total events from blocks {latest_block + 1} to {current_block} for {token_key.upper()} on {network.upper()}")
                                    
                                    # Process these as generic events
                                    for log in all_logs:
                                        # Convert generic log to event format
                                        event = {
                                            "transactionHash": log["transactionHash"],
                                            "blockNumber": log["blockNumber"],
                                            "data": log.get("data", ""),
                                            "topics": log.get("topics", [])
                                        }
                                        await process_transaction_event(event, token_key, group_id, bot, w3)
                                
                                else:
                                    print(f"✅ [{token_key.upper()}] Found 0 events from blocks {latest_block + 1} to {current_block} for {token_key.upper()} on {network.upper()}")
                            else:
                                print(f"✅ [{token_key.upper()}] Found {len(swap_events)} events from blocks {latest_block + 1} to {current_block} for {token_key.upper()} on {network.upper()}")
                                
                                for event in swap_events:
                                    await process_transaction_event(event, token_key, group_id, bot, w3)
                        
                        # Update latest block
                        latest_block = current_block
                        
                    except Exception as e:
                        if "429" in str(e) or "Too Many Requests" in str(e):
                            print(f"⚠️ Rate limited while processing events for {token_key}, waiting 30 seconds...")
                            await asyncio.sleep(30)
                        else:
                            print(f"❌ Error processing events for {token_key}: {e}")
                            await asyncio.sleep(10)
                
                # Wait before next poll
                await asyncio.sleep(polling_interval)
                
            except Exception as e:
                print(f"❌ Unexpected error in monitoring loop for {token_key}: {e}")
                await asyncio.sleep(10)
    
    except asyncio.CancelledError:
        print(f"🛑 Monitoring task cancelled for {token_key}")
    except Exception as e:
        print(f"❌ Fatal error in monitoring task for {token_key}: {e}")
    finally:
        # Clean up task reference
        if token_key in monitoring_tasks:
            del monitoring_tasks[token_key]
        print(f"🏁 Monitoring task ended for {token_key}")

async def process_transaction_event(event: Dict, token_key: str, group_id: int, bot, w3: Web3):
    """Process a single transaction event and send message to group"""
    try:
        tx_hash = event["transactionHash"].hex()
        
        # Avoid duplicate processing
        if tx_hash in processed_transactions[token_key]:
            return
        
        processed_transactions[token_key].add(tx_hash)
        
        # Get transaction details
        print(f"🔍 [{token_key.upper()}] Getting transaction details for {tx_hash[:10]}... (1 credit)")
        tx_details = get_transaction_details(tx_hash, token_key)
        print(f"✅ [{token_key.upper()}] Transaction details retrieved")
        
        # Format and send message
        message_result = process_swap_event(event, tx_hash, token_key, w3)
        
        if isinstance(message_result, tuple):
            message, direction = message_result
        else:
            message = message_result
            direction = "🔄 SWAP"
        
        # Get token config for image paths
        token_config = get_token_config(token_key)
        
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
                print(f"📤 [{token_key.upper()}] Posted SELL transaction with image: {tx_hash[:10]}...")
            except Exception as e:
                print(f"❌ Error sending message with image for {token_key}: {e}")
                # Fallback to text-only if image fails
                try:
                    await bot.send_message(
                        chat_id=group_id,
                        text=message,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                    print(f"📤 [{token_key.upper()}] Posted SELL transaction (text-only): {tx_hash[:10]}...")
                except Exception as e2:
                    print(f"❌ Error sending text-only message for {token_key}: {e2}")
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
                print(f"📤 [{token_key.upper()}] Posted BUY transaction with image: {tx_hash[:10]}...")
            except Exception as e:
                print(f"❌ Error sending message with image for {token_key}: {e}")
                # Fallback to text-only if image fails
                try:
                    await bot.send_message(
                        chat_id=group_id,
                        text=message,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                    print(f"📤 [{token_key.upper()}] Posted BUY transaction (text-only): {tx_hash[:10]}...")
                except Exception as e2:
                    print(f"❌ Error sending text-only message for {token_key}: {e2}")
        else:
            # For other swap types, send text-only
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
        
        # Small delay to avoid rate limits
        await asyncio.sleep(1)
        
    except Exception as e:
        print(f"❌ Error processing transaction event for {token_key}: {e}")

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
    """Get current monitoring status for all tokens"""
    status = {
        "active_monitoring": {},
        "web3_connections": {},
        "processed_transactions": {}
    }
    
    # Check monitoring status for each token
    from config import get_all_token_keys
    for token_key in get_all_token_keys():
        token_config = get_token_config(token_key)
        network = token_config["network"]
        w3 = get_w3_connection(network)
        
        # Check Web3 connection
        try:
            if w3:
                latest_block = w3.eth.block_number
                status["web3_connections"][network] = {
                    "connected": True,
                    "latest_block": latest_block
                }
            else:
                status["web3_connections"][network] = {
                    "connected": False,
                    "error": "No RPC URL configured"
                }
        except Exception as e:
            status["web3_connections"][network] = {
                "connected": False,
                "error": str(e)
            }
        
        # Check monitoring status
        if token_key in monitoring_groups:
            status["active_monitoring"][token_key] = {
                "active": True,
                "group_id": monitoring_groups[token_key],
                "pool_address": token_config["pool_address"],
                "network": network
            }
        else:
            status["active_monitoring"][token_key] = {
                "active": False
            }
        
        # Check processed transactions
        status["processed_transactions"][token_key] = len(processed_transactions.get(token_key, set()))
    
    return status 