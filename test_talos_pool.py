import os
import asyncio
from web3 import Web3
import dotenv

dotenv.load_dotenv()

# Arbitrum configuration
ARBITRUM_RPC_URL = os.getenv("ARBITRUM_RPC_URL")
TALOS_POOL_ADDRESS = "0xdaAe914e4Bae2AAe4f536006C353117B90Fb37e3"

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

async def test_talos_pool():
    """Test the Talos pool to verify it's working correctly"""
    
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
    
    # Create contract instance
    pool_contract = w3.eth.contract(
        address=Web3.to_checksum_address(TALOS_POOL_ADDRESS),
        abi=UNISWAP_POOL_ABI
    )
    
    print(f"🔍 Testing pool: {TALOS_POOL_ADDRESS}")
    
    # Test different time ranges to find recent transactions
    test_ranges = [100, 500, 1000, 5000, 10000]
    
    for block_range in test_ranges:
        print(f"\n🧪 Testing last {block_range} blocks...")
        
        try:
            # Get events for the block range
            events = pool_contract.events.Swap.get_logs(
                fromBlock=current_block - block_range,
                toBlock=current_block
            )
            
            print(f"✅ Found {len(events)} Swap events in last {block_range} blocks")
            
            if len(events) > 0:
                print(f"🎉 Found transactions! Latest event:")
                latest_event = events[-1]
                print(f"   Block: {latest_event['blockNumber']}")
                print(f"   TX Hash: {latest_event['transactionHash'].hex()}")
                print(f"   Amount0: {latest_event['args']['amount0']}")
                print(f"   Amount1: {latest_event['args']['amount1']}")
                print(f"   SqrtPriceX96: {latest_event['args']['sqrtPriceX96']}")
                print(f"   Liquidity: {latest_event['args']['liquidity']}")
                print(f"   Tick: {latest_event['args']['tick']}")
                break
            else:
                print(f"❌ No events found in last {block_range} blocks")
                
        except Exception as e:
            print(f"❌ Error testing {block_range} blocks: {e}")
            break
    
    # Also test with a broader ABI to see if we can get any events
    print(f"\n🔍 Testing with broader event search...")
    
    # Try to get all events from the contract
    try:
        all_events = pool_contract.events.Swap.get_logs(
            fromBlock=current_block - 1000,
            toBlock=current_block
        )
        print(f"📊 Total Swap events in last 1000 blocks: {len(all_events)}")
        
        if len(all_events) == 0:
            print("⚠️  No Swap events found. This could mean:")
            print("   1. The pool address is incorrect")
            print("   2. The pool has no recent activity")
            print("   3. The ABI is incorrect")
            print("   4. The pool uses a different event signature")
            
    except Exception as e:
        print(f"❌ Error getting all events: {e}")

if __name__ == "__main__":
    asyncio.run(test_talos_pool()) 