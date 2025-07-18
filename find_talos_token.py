import os
import asyncio
from web3 import Web3
import dotenv

dotenv.load_dotenv()

# Arbitrum configuration
ARBITRUM_RPC_URL = os.getenv("ARBITRUM_RPC_URL")

async def find_talos_token():
    """Find the correct Talos token address on Arbitrum"""
    
    if not ARBITRUM_RPC_URL:
        print("❌ ARBITRUM_RPC_URL not set in .env file")
        print("Please create a .env file with your RPC URLs")
        return
    
    w3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC_URL))
    
    if not w3.is_connected():
        print("❌ Failed to connect to Arbitrum")
        return
    
    print("✅ Connected to Arbitrum")
    
    # Get current block
    current_block = w3.eth.block_number
    print(f"📦 Current block: {current_block}")
    
    print(f"\n🔍 Searching for Talos token...")
    print(f"Please check these sources for the correct Talos token address:")
    print(f"\n1. **CoinGecko**: https://www.coingecko.com/en/coins/talos")
    print(f"2. **Arbiscan**: Search for 'Talos' in the search bar")
    print(f"3. **Uniswap**: Go to app.uniswap.org and search for 'Talos'")
    print(f"4. **DEXScreener**: https://dexscreener.com/arbitrum and search for 'Talos'")
    
    print(f"\n💡 Common places to find token addresses:")
    print(f"   - Token contract address on Arbiscan")
    print(f"   - Pool addresses in transaction details")
    print(f"   - Token addresses in swap transactions")
    
    print(f"\n🔧 Once you have the token address, you can:")
    print(f"   1. Update the find_talos_pool.py script with the correct address")
    print(f"   2. Run it again to find the pools")
    print(f"   3. Update your bot.py with the correct pool address")

if __name__ == "__main__":
    asyncio.run(find_talos_token()) 