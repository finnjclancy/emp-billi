import requests
import os
from typing import Optional, Dict, Any
from datetime import datetime

def get_arbitrum_transaction_details(tx_hash: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about an Arbitrum transaction
    
    Args:
        tx_hash (str): The transaction hash to look up
        
    Returns:
        Dict containing transaction details or None if failed
    """
    try:
        # Use Arbitrum RPC endpoint to get transaction details
        rpc_url = "https://arb1.arbitrum.io/rpc"
        
        # Get transaction details
        tx_payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionByHash",
            "params": [tx_hash],
            "id": 1
        }
        
        response = requests.post(rpc_url, json=tx_payload, timeout=10)
        print(f"🔍 RPC Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ RPC Error: {response.status_code}")
            return None
            
        data = response.json()
        print(f"🔍 RPC Response: {data}")
        
        if data.get('error'):
            print(f"❌ RPC Error: {data['error']}")
            return None
            
        tx_data = data.get('result')
        if not tx_data:
            print("❌ No transaction data returned")
            return None
            
        # Get transaction receipt for additional details
        receipt_payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionReceipt",
            "params": [tx_hash],
            "id": 2
        }
        
        receipt_response = requests.post(rpc_url, json=receipt_payload, timeout=10)
        receipt_data = receipt_response.json().get('result', {}) if receipt_response.status_code == 200 else {}
        
        # Format the transaction details
        details = {
            'hash': tx_hash,
            'block_number': int(tx_data.get('blockNumber', '0x0'), 16) if tx_data.get('blockNumber') else None,
            'from': tx_data.get('from', ''),
            'to': tx_data.get('to', ''),
            'value': int(tx_data.get('value', '0x0'), 16) / 10**18,  # Convert from wei to ETH
            'gas_price': int(tx_data.get('gasPrice', '0x0'), 16) / 10**9,  # Convert to gwei
            'gas_used': int(receipt_data.get('gasUsed', '0x0'), 16) if receipt_data.get('gasUsed') else None,
            'gas_limit': int(tx_data.get('gas', '0x0'), 16),
            'nonce': int(tx_data.get('nonce', '0x0'), 16),
            'input_data': tx_data.get('input', ''),
            'status': 'Success' if receipt_data.get('status') == '0x1' else 'Failed',
            'contract_address': receipt_data.get('contractAddress'),
            'logs_count': len(receipt_data.get('logs', [])),
            'timestamp': None,  # Would need additional API call for timestamp
            'network': 'Arbitrum One'
        }
        
        # Calculate gas cost
        if details['gas_used'] and details['gas_price']:
            details['gas_cost_eth'] = (details['gas_used'] * details['gas_price']) / 10**9
            details['gas_cost_usd'] = None  # Would need ETH price for USD conversion
        
        # Format addresses for readability
        details['from_short'] = f"{details['from'][:6]}...{details['from'][-4:]}" if details['from'] else ''
        details['to_short'] = f"{details['to'][:6]}...{details['to'][-4:]}" if details['to'] else ''
        
        return details
        
    except Exception as e:
        print(f"❌ Error getting transaction details: {e}")
        return None

def format_transaction_details(details: Dict[str, Any]) -> str:
    """
    Format transaction details into a readable string
    
    Args:
        details (Dict): Transaction details from get_arbitrum_transaction_details
        
    Returns:
        Formatted string
    """
    if not details:
        return "❌ No transaction details available"
    
    text = f"🔗 **Transaction Details**\n\n"
    text += f"📋 **Hash**: `{details['hash']}`\n"
    text += f"🌐 **Network**: {details['network']}\n"
    text += f"📦 **Block**: {details['block_number']:,}\n" if details['block_number'] else "📦 **Block**: Pending\n"
    text += f"✅ **Status**: {details['status']}\n\n"
    
    text += f"👤 **From**: `{details['from']}`\n"
    text += f"📤 **To**: `{details['to']}`\n\n"
    
    if details['value'] > 0:
        text += f"💰 **Value**: {details['value']:.6f} ETH\n"
    
    if details['gas_used']:
        text += f"⛽ **Gas Used**: {details['gas_used']:,}\n"
        text += f"⛽ **Gas Price**: {details['gas_price']:.2f} gwei\n"
        if details['gas_cost_eth']:
            text += f"💸 **Gas Cost**: {details['gas_cost_eth']:.6f} ETH\n"
    
    text += f"🔢 **Nonce**: {details['nonce']}\n"
    text += f"📝 **Logs**: {details['logs_count']}\n"
    
    if details['contract_address']:
        text += f"📄 **Contract**: `{details['contract_address']}`\n"
    
    text += f"\n🔗 **Explorer**: https://arbiscan.io/tx/{details['hash']}"
    
    return text

# Test the function with the provided transaction hash
if __name__ == "__main__":
    test_hash = "0xf0548a04cb29e5c594412650a375ca4449d4aed5e3a797ff75b5c51961400e10"
    print(f"🔍 Testing transaction: {test_hash}")
    print("=" * 50)
    
    details = get_arbitrum_transaction_details(test_hash)
    
    if details:
        print("✅ Transaction details retrieved successfully!")
        print("\n📊 Raw Data:")
        for key, value in details.items():
            print(f"  {key}: {value}")
        
        print("\n" + "=" * 50)
        print("📝 Formatted Output:")
        print(format_transaction_details(details))
    else:
        print("❌ Failed to get transaction details") 