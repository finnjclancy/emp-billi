import os
import dotenv
from typing import Dict, Any

# Load environment variables
dotenv.load_dotenv()

# Environment variables
TOKEN = os.getenv("TOKEN")
INFURA_URL = os.getenv("INFURA_URL")
ARBITRUM_RPC_URL = os.getenv("ARBITRUM_RPC_URL")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

# Default settings
TARGET_PRICE = 3333
IMAGE_PATH = "logo.jpg"
CACHE_DURATION = 60  # Cache prices for 60 seconds

# Token configurations
TOKENS = {
    "emp": {
        "name": "Empyreal",
        "symbol": "EMP",
        "token_address": "0x39D5313C3750140E5042887413bA8AA6145a9bd2",  # Real EMP token address
        "pool_address": "0xe092769bc1fa5262D4f48353f90890Dcc339BF80",
        "network": "ethereum",
        "chainid": 1,  # Ethereum chain ID
        "rpc_url": INFURA_URL,
        "explorer_url": "https://etherscan.io",
        "target_price": 3333,
        "logo_path": "logo.jpg",
        "buy_image": "buy.jpg",
        "sell_image": "sold.jpg"
    },
    "talos": {
        "name": "Talos",
        "symbol": "T",
        "token_address": "0x30a538eFFD91ACeFb1b12CE9Bc0074eD18c9dFc9",  # Talos token address
        "pool_address": "0xdaAe914e4Bae2AAe4f536006C353117B90Fb37e3",  # Talos pool address
        "network": "arbitrum",
        "chainid": 42161,  # Arbitrum chain ID
        "rpc_url": ARBITRUM_RPC_URL,
        "explorer_url": "https://arbiscan.io",
        "target_price": 1000,  # You can adjust this
        "logo_path": "logo.jpg",  # You can add a Talos logo later
        "buy_image": "buy.jpg",
        "sell_image": "sold.jpg"
    }
}

# Uniswap V3 Pool ABI (expanded for different event types)
UNISWAP_POOL_ABI = [
    # Token functions
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    # Events
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "sender", "type": "address"},
            {"indexed": True, "name": "recipient", "type": "address"},
            {"indexed": False, "name": "amount0", "type": "int256"},
            {"indexed": False, "name": "amount1", "type": "int256"},
            {"indexed": False, "name": "sqrtPriceX96", "type": "uint160"},
            {"indexed": False, "name": "liquidity", "type": "uint128"},
            {"indexed": False, "name": "tick", "type": "int24"}
        ],
        "name": "Swap",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": True, "name": "tickLower", "type": "int24"},
            {"indexed": True, "name": "tickUpper", "type": "int24"},
            {"indexed": False, "name": "amount", "type": "uint128"},
            {"indexed": False, "name": "amount0", "type": "uint256"},
            {"indexed": False, "name": "amount1", "type": "uint256"}
        ],
        "name": "Mint",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": True, "name": "tickLower", "type": "int24"},
            {"indexed": True, "name": "tickUpper", "type": "int24"},
            {"indexed": False, "name": "amount", "type": "uint128"},
            {"indexed": False, "name": "amount0", "type": "uint256"},
            {"indexed": False, "name": "amount1", "type": "uint256"}
        ],
        "name": "Burn",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "sender", "type": "address"},
            {"indexed": True, "name": "recipient", "type": "address"},
            {"indexed": False, "name": "amount0", "type": "uint256"},
            {"indexed": False, "name": "amount1", "type": "uint256"},
            {"indexed": False, "name": "paid0", "type": "uint256"},
            {"indexed": False, "name": "paid1", "type": "uint256"}
        ],
        "name": "Flash",
        "type": "event"
    }
]

def get_token_config(token_key: str) -> Dict[str, Any]:
    """Get token configuration by key"""
    return TOKENS.get(token_key, {})

def get_all_token_keys() -> list:
    """Get all available token keys"""
    return list(TOKENS.keys())

def validate_config() -> bool:
    """Validate that all required environment variables are set"""
    required_vars = ["TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        return False
    
    return True 