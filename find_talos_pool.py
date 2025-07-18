import os
import asyncio
from web3 import Web3
import dotenv

dotenv.load_dotenv()

# Arbitrum configuration
ARBITRUM_RPC_URL = os.getenv("ARBITRUM_RPC_URL")

# Possible Talos token addresses
TALOS_TOKEN_ADDRESSES = [
    "0x4dAEa5B0Bc3DCB7528B6844Cda2c6F4eC5E6330c",  # Most common
    "0x4daeA5B0Bc3DCB7528B6844Cda2c6F4eC5E6330c",  # Alternative casing
]

# Common trading pairs
TRADING_PAIRS = [
    "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",  # WETH
    "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",  # USDC
    "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",  # USDT
]

# Fee tiers
FEE_TIERS = [500, 3000, 10000]

# Uniswap V3 Factory
FACTORY_ADDRESS = "0x1F98431c8aD98523631AE4a59f267346ea31F984"

# Factory ABI (minimal)
FACTORY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"}
        ],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

async def find_talos_pools():
    """Find all Talos pools on Arbitrum"""
    
    if not ARBITRUM_RPC_URL:
        print("❌ ARBITRUM_RPC_URL not set in .env file")
        print("Please create a .env file with your RPC URLs")
        return
    
    w3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC_URL))
    
    if not w3.is_connected():
        print("❌ Failed to connect to Arbitrum")
        return
    
    print("✅ Connected to Arbitrum")
    
    # Create factory contract
    factory_contract = w3.eth.contract(
        address=Web3.to_checksum_address(FACTORY_ADDRESS),
        abi=FACTORY_ABI
    )
    
    print(f"\n🔍 Searching for Talos pools...")
    print(f"Factory: {FACTORY_ADDRESS}")
    
    found_pools = []
    
    for talos_address in TALOS_TOKEN_ADDRESSES:
        print(f"\n📊 Checking Talos token: {talos_address}")
        
        for pair_token in TRADING_PAIRS:
            for fee in FEE_TIERS:
                try:
                    pool_address = factory_contract.functions.getPool(
                        Web3.to_checksum_address(talos_address),
                        Web3.to_checksum_address(pair_token),
                        fee
                    ).call()
                    
                    if pool_address != "0x0000000000000000000000000000000000000000":
                        print(f"✅ Found pool: {pool_address}")
                        print(f"   Token A: {talos_address}")
                        print(f"   Token B: {pair_token}")
                        print(f"   Fee: {fee}")
                        
                        # Test if this pool has recent activity
                        activity = await test_pool_activity(w3, pool_address)
                        found_pools.append({
                            'address': pool_address,
                            'token_a': talos_address,
                            'token_b': pair_token,
                            'fee': fee,
                            'activity': activity
                        })
                        
                except Exception as e:
                    print(f"❌ Error checking pool: {e}")
                    continue
    
    # Summary
    print(f"\n🎯 Summary:")
    print(f"Found {len(found_pools)} pools")
    
    for pool in found_pools:
        print(f"\n📊 Pool: {pool['address']}")
        print(f"   Pair: {pool['token_a']} <-> {pool['token_b']}")
        print(f"   Fee: {pool['fee']}")
        print(f"   Activity: {pool['activity']} events in last 1000 blocks")
        
        if pool['activity'] > 0:
            print(f"   🎉 RECOMMENDED: This pool has recent activity!")
            print(f"   Use this address in your bot: {pool['address']}")

async def test_pool_activity(w3, pool_address):
    """Test if a pool has recent activity"""
    
    try:
        current_block = w3.eth.block_number
        
        # Get all logs for this address
        all_logs = w3.eth.get_logs({
            'address': Web3.to_checksum_address(pool_address),
            'fromBlock': current_block - 1000,
            'toBlock': current_block
        })
        
        return len(all_logs)
        
    except Exception as e:
        print(f"   ❌ Error testing pool activity: {e}")
        return 0

if __name__ == "__main__":
    asyncio.run(find_talos_pools()) 