#!/usr/bin/env python3
"""
Test file for finding token values using Etherscan and pool contracts.
This demonstrates how to:
1. Get pool information from Uniswap V3 contracts
2. Calculate token ratios
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

    # Calculate prices
    price_token1_per_token0 = (sqrtPriceX96 / 2**96) ** 2
    if token0_decimals != token1_decimals:
        price_token1_per_token0 *= 10 ** (token0_decimals - token1_decimals)
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
        'price_token0_per_token1': price_token0_per_token1
    }

def calculate_token_usd_value(pool_info: Dict, eth_is_token0: bool = None) -> Optional[Dict]:
    """
    Calculate USD values for tokens in a pool
    
    Args:
        pool_info: Pool information from get_pool_info()
        eth_is_token0: True if ETH is token0, False if token1, None to auto-detect
        
    Returns:
        Dictionary with USD values for both tokens
    """
    # Get ETH price
    eth_usd_price = eth_usd()
    if not eth_usd_price:
        print("❌ Failed to get ETH price")
        return None
    
    # Determine which token is ETH
    if eth_is_token0 is None:
        # Auto-detect ETH (WETH)
        weth_addresses = [
            '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH on Ethereum
            '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',  # WETH on Arbitrum
        ]
        eth_is_token0 = pool_info['token0_address'].lower() in [addr.lower() for addr in weth_addresses]
        if not eth_is_token0:
            eth_is_token0 = pool_info['token1_address'].lower() in [addr.lower() for addr in weth_addresses]
    
    if eth_is_token0:
        # ETH is token0, other token is token1
        eth_price_in_pool = pool_info['price_token0_per_token1']  # How much ETH for 1 of other token
        other_token_price_in_eth = pool_info['price_token1_per_token0']  # How much other token for 1 ETH
        
        other_token_usd_price = eth_usd_price * other_token_price_in_eth
        eth_token_usd_price = eth_usd_price
        
        return {
            'eth_symbol': pool_info['token0_symbol'],
            'other_token_symbol': pool_info['token1_symbol'],
            'eth_usd_price': eth_token_usd_price,
            'other_token_usd_price': other_token_usd_price,
            'other_token_eth_ratio': other_token_price_in_eth,
            'eth_other_token_ratio': eth_price_in_pool
        }
    else:
        # ETH is token1, other token is token0
        eth_price_in_pool = pool_info['price_token1_per_token0']  # How much ETH for 1 of other token
        other_token_price_in_eth = pool_info['price_token0_per_token1']  # How much other token for 1 ETH
        
        other_token_usd_price = eth_usd_price * other_token_price_in_eth
        eth_token_usd_price = eth_usd_price
        
        return {
            'eth_symbol': pool_info['token1_symbol'],
            'other_token_symbol': pool_info['token0_symbol'],
            'eth_usd_price': eth_token_usd_price,
            'other_token_usd_price': other_token_usd_price,
            'other_token_eth_ratio': other_token_price_in_eth,
            'eth_other_token_ratio': eth_price_in_pool
        }

def test_pool_analysis(pool_address: str, pool_name: str = "Unknown Pool"):
    """
    Test comprehensive pool analysis including USD value calculation
    
    Args:
        pool_address: Pool contract address
        pool_name: Human-readable pool name
    """
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
    print(f"   Price (Token1/Token0): {pool_info['price_token1_per_token0']:.8f}")
    print(f"   Price (Token0/Token1): {pool_info['price_token0_per_token1']:.8f}")
    
    # Calculate USD values
    usd_values = calculate_token_usd_value(pool_info)
    if not usd_values:
        print("❌ Failed to calculate USD values")
        return
    
    print(f"\n💰 USD Value Analysis:")
    print(f"   ETH Symbol: {usd_values['eth_symbol']}")
    print(f"   Other Token: {usd_values['other_token_symbol']}")
    print(f"   ETH Price: ${usd_values['eth_usd_price']:.2f}")
    print(f"   {usd_values['other_token_symbol']} Price: ${usd_values['other_token_usd_price']:.6f}")
    print(f"   {usd_values['other_token_symbol']}/ETH Ratio: {usd_values['other_token_eth_ratio']:.8f}")
    print(f"   ETH/{usd_values['other_token_symbol']} Ratio: {usd_values['eth_other_token_ratio']:.8f}")
    
    # Show calculation breakdown
    print(f"\n🧮 Calculation Breakdown:")
    print(f"   {usd_values['other_token_symbol']} USD Price = ETH USD Price × {usd_values['other_token_symbol']}/ETH Ratio")
    print(f"   ${usd_values['other_token_usd_price']:.6f} = ${usd_values['eth_usd_price']:.2f} × {usd_values['other_token_eth_ratio']:.8f}")

def main():
    """Main test function"""
    print("🧪 Testing Token Value Calculation from Pool Contracts")
    print("=" * 70)
    
    # Test ETH price function
    print("\n📊 Current ETH Price:")
    eth_price = eth_usd()
    if eth_price:
        print(f"   ETH/USD: ${eth_price:.2f}")
    else:
        print("   ❌ Failed to get ETH price")
    
    # Test pools - using known working pools
    test_pools = [
        {
            "address": "0x8ad599c3A0ff1De082011EFDDc58f1908eb6e6D8",
            "name": "USDC/ETH (0.3%)"
        },
        {
            "address": "0x4e68Ccd3E89f51C3074ca5072bbAC773960dFa36",
            "name": "USDT/ETH (1%)"
        },
        {
            "address": "0x11b815efB8f581194ae79006d24E0d814B7697F6",
            "name": "WETH/USDT (0.3%)"
        }
    ]
    
    for pool in test_pools:
        test_pool_analysis(pool["address"], pool["name"])
        print("\n" + "-" * 70)

if __name__ == "__main__":
    main() 