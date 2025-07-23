import requests
import time
from typing import Optional, Tuple
from config import ETHERSCAN_API_KEY, CACHE_DURATION

# Simple price cache to reduce API calls
price_cache = {}
price_cache_timestamp = 0

def unified_etherscan_api_call(module: str, action: str, chainid: int = 1, **params) -> Optional[dict]:
    """
    Make a unified Etherscan V2 API call
    
    Args:
        module: API module (e.g., 'proxy', 'logs', 'stats')
        action: API action (e.g., 'eth_getTransactionByHash', 'getLogs', 'ethprice')
        chainid: Chain ID (1 for Ethereum, 42161 for Arbitrum, etc.)
        **params: Additional parameters for the API call
    
    Returns:
        API response data or None if failed
    """
    if not ETHERSCAN_API_KEY:
        print("No Etherscan API key configured")
        return None
    
    url = "https://api.etherscan.io/v2/api"
    params = {
        "chainid": chainid,
        "module": module,
        "action": action,
        "apikey": ETHERSCAN_API_KEY,
        **params
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "1":
                return data.get("result")
            else:
                print(f"Etherscan API Error: {data.get('message', 'Unknown error')}")
                return None
        else:
            print(f"Etherscan API HTTP Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Etherscan API Error: {e}")
        return None

def get_eth_price() -> Optional[Tuple[float, float]]:
    """
    Get current ETH price in USD and BTC using unified Etherscan V2 API
    
    Returns:
        Tuple of (USD price, BTC price) or None if failed
        Example: (3428.49, 0.02876339)
    """
    try:
        result = unified_etherscan_api_call(
            module="stats",
            action="ethprice",
            chainid=1  # Use Ethereum for price data
        )
        
        if result:
            return (float(result['ethusd']), float(result['ethbtc']))
        else:
            print("ETH Price API Error: No result returned")
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

def get_emp_price_from_pool() -> Optional[float]:
    """
    Get EMP token price using Etherscan API and Uniswap V3 pool contract
    
    Returns:
        EMP price in USD as float or None if failed
    """
    try:
        api_key = ETHERSCAN_API_KEY
        base_url = "https://api.etherscan.io/api"
        pool_address = "0xe092769bc1fa5262D4f48353f90890Dcc339BF80"

        def eth_call(to: str, data: str) -> Optional[str]:
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

def get_cached_prices(token_symbol: str = None) -> Tuple[float, float]:
    """Get cached prices or fetch new ones if cache is expired"""
    global price_cache, price_cache_timestamp
    
    current_time = time.time()
    
    # Return cached prices if still valid
    if current_time - price_cache_timestamp < CACHE_DURATION and price_cache:
        if token_symbol == "T":
            # For Talos, we need ETH price for Arbitrum
            eth_price = price_cache.get("eth_usd_price", 0)
            print(f"Using cached prices - ETH: ${eth_price}")
            return 0, eth_price  # Return 0 for token price, ETH price for calculations
        else:
            # For EMP, return both prices
            emp_price = price_cache.get("emp_usd_price", 0)
            eth_price = price_cache.get("eth_usd_price", 0)
            print(f"Using cached prices - EMP: ${emp_price}, ETH: ${eth_price}")
            return emp_price, eth_price
    
    # Get ETH price using Etherscan API
    eth_usd_price = 0
    emp_usd_price = 0
    
    try:
        print("🔍 Getting ETH price from Etherscan API... (~1 credit)")
        eth_price = eth_usd()
        if eth_price:
            eth_usd_price = eth_price
            print(f"✅ Etherscan ETH price: ${eth_usd_price}")
        else:
            print("❌ Etherscan ETH price failed")
    except Exception as e:
        print(f"❌ Etherscan API failed: {e}")
    
    # For EMP price, use the new pool-based function
    if token_symbol != "T":  # Only get EMP price for EMP transactions
        try:
            print("🔍 Getting EMP price from pool contract... (~1 credit)")
            emp_price = get_emp_price_from_pool()
            if emp_price:
                emp_usd_price = emp_price
                print(f"✅ Pool-based EMP price: ${emp_usd_price}")
            else:
                print("❌ Pool-based EMP price failed")
        except Exception as e:
            print(f"❌ Pool-based EMP price failed: {e}")
    
    # Update cache with whatever we got
    price_cache = {
        "emp_usd_price": emp_usd_price,
        "eth_usd_price": eth_usd_price
    }
    price_cache_timestamp = current_time
    
    if token_symbol == "T":
        print(f"Final prices - ETH: ${eth_usd_price}")
        return 0, eth_usd_price  # Return 0 for token price, ETH price for calculations
    else:
        print(f"Final prices - EMP: ${emp_usd_price}, ETH: ${eth_usd_price}")
        return emp_usd_price, eth_usd_price

def get_btc_price_from_eth() -> Optional[float]:
    """
    Get BTC price using ETH price data from Etherscan API
    
    Returns:
        BTC price in USD as float or None if failed
    """
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

def get_return(current: float, target: float) -> float:
    """Calculate return percentage"""
    return ((target - current) / current) * 100

def format_percentage(value: float) -> str:
    """Format percentage value"""
    return f"{value:,.0f}" 