#!/usr/bin/env python3

import os
import dotenv
from web3 import Web3

dotenv.load_dotenv()

# Test both Talos pool addresses
TALOS_POOL_ADDRESSES = [
    "0xA7C147E5070F9C42f040Fa4E8a83FFF75df17a50",  # New address
    "0xdaAe914e4Bae2AAe4f536006C353117B90Fb37e3"   # Original address
]
ARBITRUM_RPC_URL = os.getenv("ARBITRUM_RPC_URL")

def test_pool_address(pool_address):
    """Test a specific pool address"""
    print(f"\n🔍 Testing pool: {pool_address}")
    
    if not ARBITRUM_RPC_URL:
        print("❌ ARBITRUM_RPC_URL not found in .env file")
        return
    
    try:
        # Connect to Arbitrum
        w3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC_URL))
        
        if not w3.is_connected():
            print("❌ Failed to connect to Arbitrum")
            return
        
        # Get current block
        current_block = w3.eth.block_number
        
        # Check if contract exists
        contract_code = w3.eth.get_code(pool_address)
        if contract_code == b'':
            print("❌ Contract has no code (doesn't exist)")
            return
        
        print("✅ Contract exists and has code")
        
        # Get recent events (last 100 blocks)
        from_block = current_block - 100
        to_block = current_block
        
        # Get all events (raw logs)
        try:
            logs = w3.eth.get_logs({
                'address': pool_address,
                'fromBlock': from_block,
                'toBlock': to_block
            })
            
            print(f"📊 Found {len(logs)} total events in last 100 blocks")
            
            if logs:
                print("📋 Recent events:")
                for i, log in enumerate(logs[-3:], 1):  # Show last 3
                    print(f"  {i}. Block {log['blockNumber']}: {log['transactionHash'].hex()[:10]}...")
                    print(f"     Topics: {[topic.hex()[:10] + '...' for topic in log['topics']]}")
            else:
                print("ℹ️ No recent events found")
                
        except Exception as e:
            print(f"❌ Error getting raw logs: {e}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def test_talos_pools():
    """Test both Talos pool addresses"""
    print("🔍 Testing Talos pool addresses...")
    
    for pool_address in TALOS_POOL_ADDRESSES:
        test_pool_address(pool_address)

if __name__ == "__main__":
    test_talos_pools() 