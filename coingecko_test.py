import requests

SYMBOL = "empyreal"

url = "https://api.coingecko.com/api/v3/coins/markets"
params = {
    "vs_currency": "usd",
    "ids": SYMBOL
}

response = requests.get(url, params=params)
print(f"Status code: {response.status_code}")
print("Full response:")
print(response.text) 