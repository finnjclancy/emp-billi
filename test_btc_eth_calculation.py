#!/usr/bin/env python3
"""
Test script to verify BTC price calculation from ETH data
"""

import os
import requests
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_eth_price() -> Optional[tuple[float, float]]:
    """Get current ETH price in USD and BTC using Etherscan API"""
    try:
        api_key = os.getenv('ETHERSCAN_API_KEY')
        base_url = "https://api.etherscan.io/api"
        
        params = {
            'module': 'stats',
            'action': 'ethprice',
            'apikey': api_key
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == '1' and data.get('result'):
                result = data['result']
                return (float(result['ethusd']), float(result['ethbtc']))
            else:
                print(f"ETH Price API Error: {data}")
                return None
        else:
            print(f"ETH Price API Error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"ETH Price Error: {e}")
        return None

def get_btc_price_from_eth() -> Optional[float]:
    """Get BTC price using ETH price data from Etherscan API"""
    try:
        # Get ETH price data (includes ETH/BTC ratio)
        prices = get_eth_price()
        if not prices:
            print("❌ Failed to get ETH price data")
            return None
        
        eth_usd_price, eth_btc_price = prices
        
        # Calculate BTC price: ETH_USD / ETH_BTC = BTC_USD
        btc_usd_price = eth_usd_price / eth_btc_price
        
        print(f"✅ BTC price from ETH: ${btc_usd_price:.6f}")
        return btc_usd_price
        
    except Exception as e:
        print(f"❌ BTC price calculation failed: {e}")
        return None

def test_btc_calculation():
    """Test BTC price calculation from ETH data"""
    print("🧪 Testing BTC Price Calculation from ETH Data")
    print("=" * 50)
    
    # Get ETH price data
    print("\n📊 Getting ETH price data:")
    prices = get_eth_price()
    if prices:
        eth_usd_price, eth_btc_price = prices
        print(f"✅ ETH/USD: ${eth_usd_price:.2f}")
        print(f"✅ ETH/BTC: {eth_btc_price:.8f}")
    else:
        print("❌ Failed to get ETH price data")
        return
    
    # Calculate BTC price
    print("\n📊 Calculating BTC price:")
    btc_price = get_btc_price_from_eth()
    if btc_price:
        print(f"✅ BTC/USD: ${btc_price:.2f}")
    else:
        print("❌ Failed to calculate BTC price")
    
    # Show the calculation
    print(f"\n🧮 Calculation:")
    print(f"   BTC_USD = ETH_USD ÷ ETH_BTC")
    print(f"   ${btc_price:.2f} = ${eth_usd_price:.2f} ÷ {eth_btc_price:.8f}")
    
    # Verify the calculation
    calculated_btc = eth_usd_price / eth_btc_price
    print(f"\n✅ Verification: ${calculated_btc:.2f}")

if __name__ == "__main__":
    test_btc_calculation() 