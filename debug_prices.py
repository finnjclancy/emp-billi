import requests

def test_price_fetching():
    """Test price fetching to see if that's the issue"""
    print("🧪 Testing Price Fetching")
    print("=" * 30)
    
    # Test EMP price
    try:
        emp_price_url = "https://api.coingecko.com/api/v3/simple/price?ids=empyreal&vs_currencies=usd"
        emp_response = requests.get(emp_price_url)
        print(f"EMP API Status: {emp_response.status_code}")
        if emp_response.status_code == 200:
            emp_data = emp_response.json()
            emp_usd_price = emp_data.get("empyreal", {}).get("usd", 0)
            print(f"EMP Price: ${emp_usd_price}")
        else:
            print(f"EMP API Error: {emp_response.text}")
            emp_usd_price = 0
    except Exception as e:
        print(f"EMP Price Error: {e}")
        emp_usd_price = 0
    
    # Test ETH price
    try:
        eth_price_url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
        eth_response = requests.get(eth_price_url)
        print(f"ETH API Status: {eth_response.status_code}")
        if eth_response.status_code == 200:
            eth_data = eth_response.json()
            eth_usd_price = eth_data.get("ethereum", {}).get("usd", 0)
            print(f"ETH Price: ${eth_usd_price}")
        else:
            print(f"ETH API Error: {eth_response.text}")
            eth_usd_price = 0
    except Exception as e:
        print(f"ETH Price Error: {e}")
        eth_usd_price = 0
    
    # Test calculations
    print("\n🧮 Testing Calculations:")
    emp_amount = 10.0  # Example EMP amount
    eth_amount = 0.5   # Example ETH amount
    
    emp_usd_value = emp_amount * emp_usd_price
    eth_usd_value = eth_amount * eth_usd_price
    
    print(f"EMP Amount: {emp_amount}")
    print(f"ETH Amount: {eth_amount}")
    print(f"EMP USD Value: ${emp_usd_value:.2f}")
    print(f"ETH USD Value: ${eth_usd_value:.2f}")
    
    return emp_usd_price, eth_usd_price

if __name__ == "__main__":
    test_price_fetching() 