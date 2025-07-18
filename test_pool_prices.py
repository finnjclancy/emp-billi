#!/usr/bin/env python3
"""
Test script to verify EMP and BTC pool price functions
"""

import os
import sys
import requests
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_eth_price() -> Optional[tuple[float, float]]:
    """Get current ETH price in USD using Etherscan API"""
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

def eth_usd() -> Optional[float]:
    """Get current ETH price in USD"""
    prices = get_eth_price()
    if prices:
        return prices[0]  # USD price
    return None

def get_emp_price_from_pool() -> Optional[float]:
    """Get EMP token price using Etherscan API and Uniswap V3 pool contract"""
    try:
        api_key = os.getenv('ETHERSCAN_API_KEY')
        base_url = "https://api.etherscan.io/api"
        pool_address = "0xe092769bc1fa5262D4f48353f90890Dcc339BF80"

        def eth_call(to, data):
            params = {
                'module': 'proxy',
                'action': 'eth_call',
                'to': to,
                'data': data,
                'tag': 'latest',
                'apikey': api_key
            }
            r = requests.get(base_url, params=params, timeout=10)
            if r.status_code == 200:
                result = r.json().get('result')
                return result
            return None

        # Get slot0 (price info)
        slot0_data = eth_call(pool_address, '0x3850c7bd')
        if not slot0_data or slot0_data == '0x':
            print('❌ Failed to get slot0 or empty response')
            return None
        
        try:
            sqrtPriceX96 = int(slot0_data[2:66], 16)
        except (ValueError, IndexError) as e:
            print(f'❌ Failed to parse sqrtPriceX96: {e}')
            return None

        # Get token addresses
        token0_addr = eth_call(pool_address, '0x0dfe1681')
        token1_addr = eth_call(pool_address, '0xd21220a7')
        if not token0_addr or not token1_addr:
            print('❌ Failed to get token addresses')
            return None
        
        token0 = '0x' + token0_addr[-40:]
        token1 = '0x' + token1_addr[-40:]

        # Get decimals
        token0_dec = eth_call(token0, '0x313ce567')
        token1_dec = eth_call(token1, '0x313ce567')
        if not token0_dec or not token1_dec:
            print('❌ Failed to get decimals')
            return None
        
        token0_decimals = int(token0_dec, 16)
        token1_decimals = int(token1_dec, 16)

        # Calculate prices with proper decimal handling
        price_token1_per_token0 = (sqrtPriceX96 / 2**96) ** 2
        
        # Adjust for decimals difference
        decimal_adjustment = 10 ** (token0_decimals - token1_decimals)
        price_token1_per_token0 *= decimal_adjustment
        
        # Determine which token is ETH/WETH
        weth_addresses = [
            '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH on Ethereum
            '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',  # WETH on Arbitrum
        ]
        
        token0_is_weth = token0.lower() in [addr.lower() for addr in weth_addresses]
        token1_is_weth = token1.lower() in [addr.lower() for addr in weth_addresses]
        
        # Get ETH price
        eth_usd_price = eth_usd()
        if not eth_usd_price:
            print("❌ Failed to get ETH price")
            return None
        
        if token0_is_weth:
            # WETH is token0, EMP is token1
            emp_per_weth = price_token1_per_token0  # EMP tokens per 1 WETH
            emp_usd_price = eth_usd_price / emp_per_weth if emp_per_weth != 0 else 0
        elif token1_is_weth:
            # WETH is token1, EMP is token0
            emp_per_weth = 1 / price_token1_per_token0  # EMP tokens per 1 WETH
            emp_usd_price = eth_usd_price / emp_per_weth if emp_per_weth != 0 else 0
        else:
            print("❌ No WETH found in pool")
            return None
        
        print(f"✅ EMP price from pool: ${emp_usd_price:.6f}")
        return emp_usd_price
        
    except Exception as e:
        print(f"❌ EMP price calculation failed: {e}")
        return None

def get_btc_price_from_pool() -> Optional[float]:
    """Get BTC token price using Etherscan API and Uniswap V3 pool contract"""
    try:
        api_key = os.getenv('ETHERSCAN_API_KEY')
        base_url = "https://api.etherscan.io/api"
        pool_address = "0xCBCdF9626bC03E24f779434178A73a0B4bad62eD"

        def eth_call(to, data):
            params = {
                'module': 'proxy',
                'action': 'eth_call',
                'to': to,
                'data': data,
                'tag': 'latest',
                'apikey': api_key
            }
            r = requests.get(base_url, params=params, timeout=10)
            if r.status_code == 200:
                result = r.json().get('result')
                return result
            return None

        # Get slot0 (price info)
        slot0_data = eth_call(pool_address, '0x3850c7bd')
        if not slot0_data or slot0_data == '0x':
            print('❌ Failed to get slot0 or empty response')
            return None
        
        try:
            sqrtPriceX96 = int(slot0_data[2:66], 16)
        except (ValueError, IndexError) as e:
            print(f'❌ Failed to parse sqrtPriceX96: {e}')
            return None

        # Get token addresses
        token0_addr = eth_call(pool_address, '0x0dfe1681')
        token1_addr = eth_call(pool_address, '0xd21220a7')
        if not token0_addr or not token1_addr:
            print('❌ Failed to get token addresses')
            return None
        
        token0 = '0x' + token0_addr[-40:]
        token1 = '0x' + token1_addr[-40:]

        # Get decimals
        token0_dec = eth_call(token0, '0x313ce567')
        token1_dec = eth_call(token1, '0x313ce567')
        if not token0_dec or not token1_dec:
            print('❌ Failed to get decimals')
            return None
        
        token0_decimals = int(token0_dec, 16)
        token1_decimals = int(token1_dec, 16)

        # Calculate prices with proper decimal handling
        price_token1_per_token0 = (sqrtPriceX96 / 2**96) ** 2
        
        # Adjust for decimals difference
        decimal_adjustment = 10 ** (token0_decimals - token1_decimals)
        price_token1_per_token0 *= decimal_adjustment
        
        # Determine which token is ETH/WETH
        weth_addresses = [
            '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH on Ethereum
            '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',  # WETH on Arbitrum
        ]
        
        token0_is_weth = token0.lower() in [addr.lower() for addr in weth_addresses]
        token1_is_weth = token1.lower() in [addr.lower() for addr in weth_addresses]
        
        # Get ETH price
        eth_usd_price = eth_usd()
        if not eth_usd_price:
            print("❌ Failed to get ETH price")
            return None
        
        if token0_is_weth:
            # WETH is token0, BTC is token1
            btc_per_weth = price_token1_per_token0  # BTC tokens per 1 WETH
            btc_usd_price = eth_usd_price / btc_per_weth if btc_per_weth != 0 else 0
        elif token1_is_weth:
            # WETH is token1, BTC is token0
            btc_per_weth = 1 / price_token1_per_token0  # BTC tokens per 1 WETH
            btc_usd_price = eth_usd_price / btc_per_weth if btc_per_weth != 0 else 0
        else:
            print("❌ No WETH found in pool")
            return None
        
        print(f"✅ BTC price from pool: ${btc_usd_price:.6f}")
        return btc_usd_price
        
    except Exception as e:
        print(f"❌ BTC price calculation failed: {e}")
        return None

def test_pool_prices():
    """Test both EMP and BTC pool price functions"""
    print("🧪 Testing Pool Price Functions")
    print("=" * 50)
    
    # Test ETH price first
    print("\n📊 Testing ETH Price:")
    eth_price = eth_usd()
    if eth_price:
        print(f"✅ ETH Price: ${eth_price:.2f}")
    else:
        print("❌ Failed to get ETH price")
        return
    
    # Test EMP price
    print("\n📊 Testing EMP Price:")
    emp_price = get_emp_price_from_pool()
    if emp_price:
        print(f"✅ EMP Price: ${emp_price:.6f}")
    else:
        print("❌ Failed to get EMP price")
    
    # Test BTC price
    print("\n📊 Testing BTC Price:")
    btc_price = get_btc_price_from_pool()
    if btc_price:
        print(f"✅ BTC Price: ${btc_price:.6f}")
    else:
        print("❌ Failed to get BTC price")
    
    print("\n" + "=" * 50)
    print("🎯 Summary:")
    if eth_price:
        print(f"   ETH: ${eth_price:.2f}")
    if emp_price:
        print(f"   EMP: ${emp_price:.6f}")
    if btc_price:
        print(f"   BTC: ${btc_price:.6f}")

if __name__ == "__main__":
    test_pool_prices() 