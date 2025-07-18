import requests
import os
from typing import Optional, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_eth_price() -> Optional[tuple[float, float]]:
    """
    Get current ETH price in USD and BTC using Etherscan API
    
    Returns:
        Tuple of (USD price, BTC price) or None if failed
        Example: (3428.49, 0.02876339)
    """
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
    """
    Get current ETH price in USD
    
    Returns:
        ETH price in USD as float or None if failed
        Example: 3411.23
    """
    prices = get_eth_price()
    if prices:
        return prices[0]  # USD price
    return None

def btc_usd() -> Optional[float]:
    """
    Get current BTC price in USD using ETH/BTC ratio
    
    Returns:
        BTC price in USD as float or None if failed
        Example: 119000.50
    """
    prices = get_eth_price()
    if prices:
        eth_usd_price, eth_btc_price = prices
        # Calculate BTC price: ETH_USD / ETH_BTC = BTC_USD
        btc_usd_price = eth_usd_price / eth_btc_price
        return btc_usd_price
    return None

def eth_btc() -> Optional[float]:
    """
    Get current ETH price in BTC
    
    Returns:
        ETH price in BTC as float or None if failed
        Example: 0.02865937
    """
    prices = get_eth_price()
    if prices:
        return prices[1]  # BTC price
    return None

def get_v3_pool_price(pool_address: str) -> Optional[dict]:
    """
    Get price info from a Uniswap V3 pool.
    Returns a dict with token0, token1, decimals, and price (token1 per token0 and token0 per token1).
    """
    import math
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

    # slot0() selector: 0x3850c7bd
    slot0_data = eth_call(pool_address, '0x3850c7bd')
    if not slot0_data:
        print('❌ Failed to get slot0')
        return None
    sqrtPriceX96 = int(slot0_data[2:66], 16)

    # token0() selector: 0x0dfe1681
    token0_addr = eth_call(pool_address, '0x0dfe1681')
    if not token0_addr:
        print('❌ Failed to get token0')
        return None
    token0 = '0x' + token0_addr[-40:]

    # token1() selector: 0xd21220a7
    token1_addr = eth_call(pool_address, '0xd21220a7')
    if not token1_addr:
        print('❌ Failed to get token1')
        return None
    token1 = '0x' + token1_addr[-40:]

    # decimals() selector: 0x313ce567
    token0_dec = eth_call(token0, '0x313ce567')
    token1_dec = eth_call(token1, '0x313ce567')
    if not token0_dec or not token1_dec:
        print('❌ Failed to get decimals')
        return None
    token0_decimals = int(token0_dec, 16)
    token1_decimals = int(token1_dec, 16)

    # name() selector: 0x06fdde03
    token0_name_data = eth_call(token0, '0x06fdde03')
    token1_name_data = eth_call(token1, '0x06fdde03')
    
    # Parse name from hex (this is a simplified version - in practice you'd need ABI decoding)
    def parse_name_from_hex(hex_data):
        if not hex_data or len(hex_data) < 66:
            return "Unknown"
        # Remove '0x' and get the length from the first 32 bytes
        data = hex_data[2:]
        # This is a simplified parser - actual ABI decoding would be more complex
        try:
            # For now, return a placeholder - proper ABI decoding would be needed
            return "Token"
        except:
            return "Unknown"
    
    token0_name = parse_name_from_hex(token0_name_data)
    token1_name = parse_name_from_hex(token1_name_data)

    # Calculate price
    price_token1_per_token0 = (sqrtPriceX96 / 2**96) ** 2
    # Adjust for decimals - only adjust if decimals are different
    if token0_decimals != token1_decimals:
        price_token1_per_token0 *= 10 ** (token0_decimals - token1_decimals)
    price_token0_per_token1 = 1 / price_token1_per_token0 if price_token1_per_token0 != 0 else None
    
    # Debug info
    print(f"Debug - sqrtPriceX96: {sqrtPriceX96}")
    print(f"Debug - raw price: {(sqrtPriceX96 / 2**96) ** 2}")
    print(f"Debug - adjusted price: {price_token1_per_token0}")

    return {
        'token0': token0,
        'token1': token1,
        'token0_name': token0_name,
        'token1_name': token1_name,
        'token0_decimals': token0_decimals,
        'token1_decimals': token1_decimals,
        'price_token1_per_token0': price_token1_per_token0,
        'price_token0_per_token1': price_token0_per_token1
    }

def get_pool_tokens(pool_address: str) -> Optional[dict]:
    """
    Get token symbols and addresses from a Uniswap V3 pool
    
    Args:
        pool_address: The Uniswap V3 pool contract address
        
    Returns:
        Dictionary with token0 and token1 symbols and addresses, or None if failed
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

    # token0() selector: 0x0dfe1681
    token0_addr = eth_call(pool_address, '0x0dfe1681')
    if not token0_addr:
        print('❌ Failed to get token0')
        return None
    token0 = '0x' + token0_addr[-40:]

    # token1() selector: 0xd21220a7
    token1_addr = eth_call(pool_address, '0xd21220a7')
    if not token1_addr:
        print('❌ Failed to get token1')
        return None
    token1 = '0x' + token1_addr[-40:]

    # symbol() selector: 0x95d89b41
    token0_symbol_data = eth_call(token0, '0x95d89b41')
    token1_symbol_data = eth_call(token1, '0x95d89b41')
    
    # Parse symbol from hex (proper ABI decoding)
    def decode_string_from_hex(hex_data):
        if not hex_data or len(hex_data) < 66:
            return "Unknown"
        
        try:
            # Remove '0x' prefix
            data = hex_data[2:]
            
            # Skip offset (first 32 bytes = 64 hex chars)
            if len(data) < 64:
                return "Unknown"
            
            # Get length (next 32 bytes)
            length_hex = data[64:128]
            length = int(length_hex, 16)
            
            # Get string data (next N bytes)
            string_hex = data[128:128 + (length * 2)]
            
            # Convert hex to ASCII
            string_bytes = bytes.fromhex(string_hex)
            return string_bytes.decode('utf-8')
        except Exception as e:
            print(f"Decoding error: {e}")
            return "Unknown"
    
    token0_symbol = decode_string_from_hex(token0_symbol_data)
    token1_symbol = decode_string_from_hex(token1_symbol_data)
    
    # Create pool name
    pool_name = f"{token0_symbol}/{token1_symbol}"
    
    return {
        'pool_name': pool_name,
        'token0_symbol': token0_symbol,
        'token1_symbol': token1_symbol,
        'token0_address': token0,
        'token1_address': token1
    }



if __name__ == "__main__":
    # Test all functions
    print("🧪 Testing Price Functions from Etherscan API")
    print("=" * 50)
    
    # Test main function
    print("\n📊 Main Function (get_eth_price):")
    prices = get_eth_price()
    if prices:
        usd_price, btc_price = prices
        print(f"ETH Price: ${usd_price:.2f} USD")
        print(f"ETH Price: {btc_price:.8f} BTC")
    else:
        print("❌ Failed to get ETH price")
    
    # Test individual functions
    print("\n📊 Individual Functions:")
    
    eth_usd_price = eth_usd()
    if eth_usd_price:
        print(f"ETH/USD: ${eth_usd_price:.2f}")
    else:
        print("❌ Failed to get ETH/USD")
    
    btc_usd_price = btc_usd()
    if btc_usd_price:
        print(f"BTC/USD: ${btc_usd_price:.2f}")
    else:
        print("❌ Failed to get BTC/USD")
    
    eth_btc_price = eth_btc()
    if eth_btc_price:
        print(f"ETH/BTC: {eth_btc_price:.8f}")
    else:
        print("❌ Failed to get ETH/BTC")
    


    print("\n📊 Uniswap V3 Pool Function:")
    v3_pool = "0xe092769bc1fa5262D4f48353f90890Dcc339BF80"  # USDC/ETH V3 pool
    v3_info = get_v3_pool_price(v3_pool)
    if v3_info:
        print(f"token0: {v3_info['token0_name']} ({v3_info['token0']}) - decimals: {v3_info['token0_decimals']}")
        print(f"token1: {v3_info['token1_name']} ({v3_info['token1']}) - decimals: {v3_info['token1_decimals']}")
        print(f"token1 per token0: {v3_info['price_token1_per_token0']}")
        print(f"token0 per token1: {v3_info['price_token0_per_token1']}")
    else:
        print("❌ Failed to get V3 pool price info")
    
    # Test the new pool tokens function
    print("\n📊 Pool Tokens Function:")
    pool_tokens = get_pool_tokens(v3_pool)
    if pool_tokens:
        print(f"Pool Name: {pool_tokens['pool_name']}")
        print(f"Token0: {pool_tokens['token0_symbol']} ({pool_tokens['token0_address']})")
        print(f"Token1: {pool_tokens['token1_symbol']} ({pool_tokens['token1_address']})")
    else:
        print("❌ Failed to get pool tokens")
