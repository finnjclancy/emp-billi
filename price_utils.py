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
    OPTIMIZED VERSION: Uses hardcoded addresses to minimize API calls
    
    Returns:
        EMP price in USD as float or None if failed
    """
    try:
        api_key = ETHERSCAN_API_KEY
        if not api_key:
            print("❌ EMP Price Error: No Etherscan API key configured")
            return None
            
        base_url = "https://api.etherscan.io/api"
        
        # Hardcoded values for EMP/WETH pool (these never change)
        pool_address = "0xe092769bc1fa5262D4f48353f90890Dcc339BF80"
        emp_address = "0x39D5313C3750140E5042887413bA8AA6145a9bd2"  # token0 (lower address)
        weth_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"  # token1 (higher address)
        emp_decimals = 18
        weth_decimals = 18
        emp_is_token0 = True  # EMP address < WETH address
        
        print(f"🏊 Using EMP/WETH pool: {pool_address}")
        print(f"📍 EMP (token0): {emp_address}")
        print(f"📍 WETH (token1): {weth_address}")

        def eth_call(to: str, data: str, call_name: str = "unknown") -> Optional[str]:
            params = {
                'module': 'proxy',
                'action': 'eth_call',
                'to': to,
                'data': data,
                'tag': 'latest',
                'apikey': api_key
            }
            try:
                print(f"🔍 Making API call: {call_name}")
                r = requests.get(base_url, params=params, timeout=15)
                
                if r.status_code != 200:
                    print(f"❌ {call_name} - HTTP Error {r.status_code}: {r.text[:100]}")
                    return None
                
                response_data = r.json()
                
                # Check for API errors in response
                if 'status' in response_data and response_data['status'] == '0':
                    error_msg = response_data.get('message', 'Unknown API error')
                    print(f"❌ {call_name} - API Error: {error_msg}")
                    if 'rate limit' in error_msg.lower():
                        print("❌ Rate limit detected - try adding delays between calls")
                    elif 'invalid api key' in error_msg.lower():
                        print("❌ Invalid API key - check your ETHERSCAN_API_KEY")
                    return None
                
                result = response_data.get('result')
                if result:
                    print(f"✅ {call_name} - Success")
                    return result
                else:
                    print(f"❌ {call_name} - No result in response")
                    return None
                    
            except requests.exceptions.Timeout:
                print(f"❌ {call_name} - Request timeout (>15 seconds)")
                return None
            except requests.exceptions.RequestException as e:
                print(f"❌ {call_name} - Network error: {e}")
                return None
            except Exception as e:
                print(f"❌ {call_name} - Unexpected error: {e}")
                return None

        # STEP 1: Get slot0 (only contract call needed!)
        print("📊 Step 1/2: Getting pool price data...")
        slot0_data = eth_call(pool_address, '0x3850c7bd', "Pool slot0")
        if not slot0_data or slot0_data == '0x':
            print('❌ Step 1 Failed: Empty slot0 response - pool might be inactive')
            return None
        
        try:
            sqrtPriceX96 = int(slot0_data[2:66], 16)
            print(f"✅ Step 1 Complete: sqrtPriceX96 = {sqrtPriceX96}")
        except (ValueError, IndexError) as e:
            print(f'❌ Step 1 Failed: Cannot parse slot0 data: {e}')
            print(f"Raw slot0 data: {slot0_data}")
            return None

        # STEP 2: Get ETH price for USD conversion
        print("📊 Step 2/2: Getting ETH price for USD conversion...")
        eth_usd_price = eth_usd()
        if not eth_usd_price:
            print("❌ Step 2 Failed: Could not get ETH price for USD conversion")
            return None
        print(f"✅ Step 2 Complete: ETH price = ${eth_usd_price}")

        # Calculate price ratio from sqrtPriceX96
        print("🧮 Calculating price from pool data...")
        price_token1_per_token0 = (sqrtPriceX96 / 2**96) ** 2
        
        # Since both tokens have 18 decimals, no decimal adjustment needed
        # price_token1_per_token0 = WETH per EMP (since WETH is token1, EMP is token0)
        weth_per_emp = price_token1_per_token0
        emp_per_weth = 1 / weth_per_emp if weth_per_emp != 0 else 0
        
        print(f"💰 Pool ratio: {weth_per_emp:.10f} WETH per EMP")
        print(f"💰 Inverse: {emp_per_weth:.6f} EMP per WETH")
        
        # Final calculation: EMP price in USD
        emp_usd_price = eth_usd_price / emp_per_weth if emp_per_weth != 0 else 0
        
        print(f"🎉 SUCCESS: EMP price calculated = ${emp_usd_price:.6f}")
        print(f"⚡ Optimized: Only 2 API calls instead of 6!")
        return emp_usd_price
        
    except Exception as e:
        print(f"❌ FATAL ERROR in EMP price calculation: {type(e).__name__}: {e}")
        import traceback
        print("Full traceback:")
        traceback.print_exc()
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