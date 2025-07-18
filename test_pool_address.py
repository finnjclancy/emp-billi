import os
import asyncio
from web3 import Web3
import dotenv

dotenv.load_dotenv()

# Arbitrum configuration
ARBITRUM_RPC_URL = os.getenv("ARBITRUM_RPC_URL")

async def test_pool_address(pool_address):
    """Test any pool address for activity"""
    
    if not ARBITRUM_RPC_URL:
        print("❌ ARBITRUM_RPC_URL not set in .env file")
        return
    
    w3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC_URL))
    
    if not w3.is_connected():
        print("❌ Failed to connect to Arbitrum")
        return
    
    print("✅ Connected to Arbitrum")
    
    # Get current block
    current_block = w3.eth.block_number
    print(f"📦 Current block: {current_block}")
    
    # Check if the contract exists
    try:
        code = w3.eth.get_code(Web3.to_checksum_address(pool_address))
        if code == b'':
            print(f"❌ Contract {pool_address} has no code - it doesn't exist!")
            return
        else:
            print(f"✅ Contract {pool_address} exists and has code")
    except Exception as e:
        print(f"❌ Error checking contract: {e}")
        return
    
    # Check for recent activity
    print(f"\n🔍 Checking for recent activity...")
    
    try:
        # Get all logs for this address
        all_logs = w3.eth.get_logs({
            'address': Web3.to_checksum_address(pool_address),
            'fromBlock': current_block - 1000,
            'toBlock': current_block
        })
        
        print(f"📊 Found {len(all_logs)} total events in last 1000 blocks")
        
        if len(all_logs) > 0:
            print(f"🎉 Found activity! Latest event:")
            latest_log = all_logs[-1]
            print(f"   Block: {latest_log['blockNumber']}")
            print(f"   TX Hash: {latest_log['transactionHash'].hex()}")
            print(f"   Topics: {[topic.hex() for topic in latest_log['topics']]}")
            
            print(f"\n✅ This pool address is ACTIVE and can be used in your bot!")
            print(f"   Pool Address: {pool_address}")
        else:
            print(f"❌ No events found in last 1000 blocks")
            print(f"   This pool might be inactive or the address might be incorrect")
            
    except Exception as e:
        print(f"❌ Error getting logs: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python test_pool_address.py <pool_address>")
        print("Example: python test_pool_address.py 0xA7C147E5070F9C42f040Fa4E8a83FFF75df17a50")
        sys.exit(1)
    
    pool_address = sys.argv[1]
    asyncio.run(test_pool_address(pool_address)) 