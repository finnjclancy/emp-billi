#!/usr/bin/env python3
"""
Corrected test file for finding EMP token value using Etherscan and pool contracts.
This demonstrates how to:
1. Get pool information from the EMP/ETH Uniswap V3 contract
2. Calculate EMP token ratio to ETH with proper interpretation
3. Convert to USD using ETH price
"""

import os
import requests
from typing import Optional, Dict, Tuple
from dotenv import load_dotenv
from price import get_eth_price, eth_usd

# Load environment variables
load_dotenv()

def get_pool_info(pool_address: str) -> Optional[Dict]:
    """
    Get comprehensive pool information including tokens, prices, and ratios
    
    Args:
        pool_address: The Uniswap V3 pool contract address
        
    Returns:
        Dictionary with pool information or None if failed
    """
    api_key = os.getenv('ETHERSCAN_API_KEY')
    base_url = "https://api.etherscan.io/api"

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

    # Get token symbols
    token0_symbol_data = eth_call(token0, '0x95d89b41')
    token1_symbol_data = eth_call(token1, '0x95d89b41')
    
    def decode_string_from_hex(hex_data):
        if not hex_data or len(hex_data) < 66:
            return "Unknown"
        try:
            data = hex_data[2:]
            if len(data) < 64:
                return "Unknown"
            length_hex = data[64:128]
            length = int(length_hex, 16)
            string_hex = data[128:128 + (length * 2)]
            string_bytes = bytes.fromhex(string_hex)
            return string_bytes.decode('utf-8')
        except Exception as e:
            return "Unknown"
    
    token0_symbol = decode_string_from_hex(token0_symbol_data)
    token1_symbol = decode_string_from_hex(token1_symbol_data)

    # Get decimals
    token0_dec = eth_call(token0, '0x313ce567')
    token1_dec = eth_call(token1, '0x313ce567')
    if not token0_dec or not token1_dec:
        print('❌ Failed to get decimals')
        return None
    
    token0_decimals = int(token0_dec, 16)
    token1_decimals = int(token1_dec, 16)

    # Calculate prices with proper decimal handling
    # Uniswap V3 price calculation
    price_token1_per_token0 = (sqrtPriceX96 / 2**96) ** 2
    
    # Adjust for decimals difference
    decimal_adjustment = 10 ** (token0_decimals - token1_decimals)
    price_token1_per_token0 *= decimal_adjustment
    
    price_token0_per_token1 = 1 / price_token1_per_token0 if price_token1_per_token0 != 0 else None

    return {
        'pool_address': pool_address,
        'token0_symbol': token0_symbol,
        'token1_symbol': token1_symbol,
        'token0_address': token0,
        'token1_address': token1,
        'token0_decimals': token0_decimals,
        'token1_decimals': token1_decimals,
        'price_token1_per_token0': price_token1_per_token0,
        'price_token0_per_token1': price_token0_per_token1,
        'sqrtPriceX96': sqrtPriceX96
    }

def calculate_emp_usd_value_corrected(pool_info: Dict) -> Optional[Dict]:
    """
    Calculate USD values for EMP token using ETH price with correct interpretation
    
    Args:
        pool_info: Pool information from get_pool_info()
        
    Returns:
        Dictionary with USD values for EMP token
    """
    # Get ETH price
    eth_usd_price = eth_usd()
    if not eth_usd_price:
        print("❌ Failed to get ETH price")
        return None
    
    # Determine which token is ETH/WETH
    weth_addresses = [
        '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH on Ethereum
        '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',  # WETH on Arbitrum
    ]
    
    token0_is_weth = pool_info['token0_address'].lower() in [addr.lower() for addr in weth_addresses]
    token1_is_weth = pool_info['token1_address'].lower() in [addr.lower() for addr in weth_addresses]
    
    if token0_is_weth:
        # WETH is token0, EMP is token1
        weth_symbol = pool_info['token0_symbol']
        emp_symbol = pool_info['token1_symbol']
        
        # For WETH as token0:
        # price_token1_per_token0 = how much EMP for 1 WETH
        # price_token0_per_token1 = how much WETH for 1 EMP
        emp_per_weth = pool_info['price_token1_per_token0']  # EMP tokens per 1 WETH
        weth_per_emp = pool_info['price_token0_per_token1']  # WETH per 1 EMP token
        
        # Calculate USD prices
        # If 1 WETH = $X and 1 WETH = Y EMP, then 1 EMP = $X / Y
        emp_usd_price = eth_usd_price / emp_per_weth if emp_per_weth != 0 else 0
        weth_usd_price = eth_usd_price
        
        return {
            'weth_symbol': weth_symbol,
            'emp_symbol': emp_symbol,
            'weth_usd_price': weth_usd_price,
            'emp_usd_price': emp_usd_price,
            'emp_per_weth': emp_per_weth,
            'weth_per_emp': weth_per_emp,
            'weth_decimals': pool_info['token0_decimals'],
            'emp_decimals': pool_info['token1_decimals']
        }
    
    elif token1_is_weth:
        # WETH is token1, EMP is token0
        weth_symbol = pool_info['token1_symbol']
        emp_symbol = pool_info['token0_symbol']
        
        # For WETH as token1:
        # price_token0_per_token1 = how much EMP for 1 WETH
        # price_token1_per_token0 = how much WETH for 1 EMP
        emp_per_weth = pool_info['price_token0_per_token1']  # EMP tokens per 1 WETH
        weth_per_emp = pool_info['price_token1_per_token0']  # WETH per 1 EMP token
        
        # Calculate USD prices
        # If 1 WETH = $X and 1 WETH = Y EMP, then 1 EMP = $X / Y
        emp_usd_price = eth_usd_price / emp_per_weth if emp_per_weth != 0 else 0
        weth_usd_price = eth_usd_price
        
        return {
            'weth_symbol': weth_symbol,
            'emp_symbol': emp_symbol,
            'weth_usd_price': weth_usd_price,
            'emp_usd_price': emp_usd_price,
            'emp_per_weth': emp_per_weth,
            'weth_per_emp': weth_per_emp,
            'weth_decimals': pool_info['token1_decimals'],
            'emp_decimals': pool_info['token0_decimals']
        }
    
    else:
        print("❌ No WETH found in pool")
        return None

def test_emp_pool_analysis_corrected():
    """
    Test comprehensive EMP pool analysis with corrected price interpretation
    """
    pool_address = "0xe092769bc1fa5262D4f48353f90890Dcc339BF80"
    pool_name = "EMP/ETH Pool"
    
    print(f"\n🔍 Analyzing Pool: {pool_name}")
    print(f"📍 Address: {pool_address}")
    print("=" * 60)
    
    # Get pool information
    pool_info = get_pool_info(pool_address)
    if not pool_info:
        print("❌ Failed to get pool information")
        return
    
    print(f"📊 Pool Information:")
    print(f"   Token0: {pool_info['token0_symbol']} ({pool_info['token0_address']})")
    print(f"   Token1: {pool_info['token1_symbol']} ({pool_info['token1_address']})")
    print(f"   Token0 Decimals: {pool_info['token0_decimals']}")
    print(f"   Token1 Decimals: {pool_info['token1_decimals']}")
    print(f"   sqrtPriceX96: {pool_info['sqrtPriceX96']}")
    print(f"   Price (Token1/Token0): {pool_info['price_token1_per_token0']:.8f}")
    print(f"   Price (Token0/Token1): {pool_info['price_token0_per_token1']:.8f}")
    
    # Calculate USD values with corrected interpretation
    usd_values = calculate_emp_usd_value_corrected(pool_info)
    if not usd_values:
        print("❌ Failed to calculate USD values")
        return
    
    print(f"\n💰 USD Value Analysis (Corrected):")
    print(f"   WETH Symbol: {usd_values['weth_symbol']}")
    print(f"   EMP Symbol: {usd_values['emp_symbol']}")
    print(f"   WETH Price: ${usd_values['weth_usd_price']:.2f}")
    print(f"   EMP Price: ${usd_values['emp_usd_price']:.6f}")
    print(f"   EMP per WETH: {usd_values['emp_per_weth']:.8f}")
    print(f"   WETH per EMP: {usd_values['weth_per_emp']:.8f}")
    
    # Show calculation breakdown
    print(f"\n🧮 Calculation Breakdown:")
    print(f"   EMP USD Price = WETH USD Price ÷ EMP per WETH")
    print(f"   ${usd_values['emp_usd_price']:.6f} = ${usd_values['weth_usd_price']:.2f} ÷ {usd_values['emp_per_weth']:.8f}")
    
    # Show what this means in practical terms
    print(f"\n💡 Practical Example:")
    print(f"   1 {usd_values['weth_symbol']} = ${usd_values['weth_usd_price']:.2f}")
    print(f"   1 {usd_values['emp_symbol']} = ${usd_values['emp_usd_price']:.6f}")
    print(f"   1 {usd_values['weth_symbol']} = {usd_values['emp_per_weth']:.6f} {usd_values['emp_symbol']}")
    print(f"   1 {usd_values['emp_symbol']} = {usd_values['weth_per_emp']:.8f} {usd_values['weth_symbol']}")
    
    # Show the key insight
    print(f"\n🎯 Key Insight:")
    print(f"   The pool shows that 1 {usd_values['weth_symbol']} = {usd_values['emp_per_weth']:.6f} {usd_values['emp_symbol']}")
    print(f"   Since 1 {usd_values['weth_symbol']} = ${usd_values['weth_usd_price']:.2f}, then:")
    print(f"   1 {usd_values['emp_symbol']} = ${usd_values['emp_usd_price']:.6f}")

def main():
    """Main test function"""
    print("🧪 Testing EMP Token Value Calculation (Corrected)")
    print("=" * 70)
    
    # Test ETH price function
    print("\n📊 Current ETH Price:")
    eth_price = eth_usd()
    if eth_price:
        print(f"   ETH/USD: ${eth_price:.2f}")
    else:
        print("   ❌ Failed to get ETH price")
    
    # Test EMP pool analysis with corrected interpretation
    test_emp_pool_analysis_corrected()

if __name__ == "__main__":
    main() 