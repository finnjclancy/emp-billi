#!/usr/bin/env python3

import os
import dotenv
import requests
from web3 import Web3

dotenv.load_dotenv()

ARBITRUM_RPC_URL = os.getenv("ARBITRUM_RPC_URL")

def check_pool_transactions(pool_address):
    """Check recent transactions on a pool address"""
    print(f"\n🔍 Checking transactions for pool: {pool_address}")
    
    if not ARBITRUM_RPC_URL:
        print("❌ ARBITRUM_RPC_URL not found in .env file")
        return
    
    try:
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
        
        # Look for recent transactions (last 1000 blocks)
        from_block = current_block - 1000
        to_block = current_block
        
        print(f"📊 Scanning blocks {from_block} to {to_block}...")
        
        try:
            # Get all logs for this address
            logs = w3.eth.get_logs({
                'address': pool_address,
                'fromBlock': from_block,
                'toBlock': to_block
            })
            
            print(f"📋 Found {len(logs)} total events")
            
            if logs:
                print("\n📊 Recent events:")
                for i, log in enumerate(logs[-5:], 1):  # Show last 5
                    print(f"  {i}. Block {log['blockNumber']}: {log['transactionHash'].hex()[:10]}...")
                    print(f"     Topics: {[topic.hex()[:10] + '...' for topic in log['topics']]}")
                    
                    # Get transaction details
                    try:
                        tx = w3.eth.get_transaction(log['transactionHash'])
                        print(f"     From: {tx['from'][:10]}...")
                        print(f"     To: {tx['to'][:10]}...")
                        print(f"     Value: {w3.from_wei(tx['value'], 'ether')} ETH")
                    except Exception as e:
                        print(f"     Error getting tx details: {e}")
                    print()
            else:
                print("ℹ️ No recent events found")
                
        except Exception as e:
            print(f"❌ Error getting logs: {e}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Main function"""
    print("🔍 Talos Pool Transaction Analyzer")
    print("=" * 40)
    
    # Check the pool addresses you provided
    pool_addresses = [
        "0xA7C147E5070F9C42f040Fa4E8a83FFF75df17a50",
        "0xdaAe914e4Bae2AAe4f536006C353117B90Fb37e3"
    ]
    
    for pool_address in pool_addresses:
        check_pool_transactions(pool_address)
    
    print("\n💡 Next steps:")
    print("1. If no events found, the pools might be inactive")
    print("2. Check if Talos is listed on other DEXs (SushiSwap, Camelot, etc.)")
    print("3. Look for Talos on other networks (Ethereum, Polygon, etc.)")
    print("4. Check if the token symbol is different (TALOS, TAL, etc.)")

if __name__ == "__main__":
    main() 