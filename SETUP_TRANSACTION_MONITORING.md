# Transaction Monitoring Setup

Your bot has been updated to automatically monitor Uniswap transactions for multiple tokens and post them to a Telegram group chat.

## Supported Tokens

### EMP (Empyreal) - Ethereum Mainnet
- **Pool Address**: `0xe092769bc1fa5262D4f48353f90890Dcc339BF80`
- **Network**: Ethereum Mainnet
- **Commands**: `/startmonitor`, `/stopmonitor`, `/last5`, `/test`

### Talos (T) - Arbitrum
- **Pool Address**: `0x30a538eFFD91ACeFb1b12CE9Bc0074eD18c9dFc9`
- **Network**: Arbitrum
- **Commands**: `/starttalos`, `/stoptalos`, `/last5talos`, `/testtalos`

## Required Environment Variables

Add these to your `.env` file:

```env
# Existing
TOKEN=your_telegram_bot_token_here

# Ethereum Mainnet (for EMP)
INFURA_URL=https://mainnet.infura.io/v3/your_infura_project_id

# Arbitrum (for Talos)
ARBITRUM_RPC_URL=https://arbitrum-mainnet.infura.io/v3/your_infura_project_id

# Optional: For better transaction details
ETHERSCAN_API_KEY=your_etherscan_api_key_here
```

## Setup Instructions

### 1. Add Bot to Group
1. Add your bot to the Telegram group where you want to post transactions
2. Make sure the bot has permission to send messages in the group

### 2. Get Infura API Key
1. Go to [Infura.io](https://infura.io)
2. Create a free account
3. Create a new project
4. Copy the mainnet endpoint URL for Ethereum
5. Copy the mainnet endpoint URL for Arbitrum
6. Add both to your `.env` file

### 3. Get Etherscan API Key (Optional)
1. Go to [Etherscan.io](https://etherscan.io)
2. Create a free account
3. Go to API Keys section
4. Create a new API key
5. Add it to your `.env` file as `ETHERSCAN_API_KEY`

## New Commands

### EMP (Ethereum) Commands
- `/startmonitor` - Start EMP transaction monitoring in the current group
- `/stopmonitor` - Stop EMP transaction monitoring
- `/last5` - Show last 5 EMP transactions
- `/test` - Test EMP blockchain connection

### Talos (Arbitrum) Commands
- `/starttalos` - Start Talos transaction monitoring in the current group
- `/stoptalos` - Stop Talos transaction monitoring
- `/last5talos` - Show last 5 Talos transactions
- `/testtalos` - Test Talos blockchain connection

**Note:** Just type `/startmonitor` or `/starttalos` in any group where you want to receive transaction updates!

## Features

- **Multi-Token Support**: Monitor both EMP (Ethereum) and Talos (Arbitrum)
- **Automatic Monitoring**: Starts automatically when bot runs
- **Real-time Updates**: Posts new swaps within ~12 seconds
- **Duplicate Prevention**: Avoids posting the same transaction twice
- **Rich Messages**: Shows swap direction, amounts, addresses, and explorer links
- **Error Handling**: Continues monitoring even if individual transactions fail
- **Network-Specific**: Uses appropriate RPC endpoints and block explorers

## Message Format

Each transaction post includes:
- 🟢 BUY or 🔴 SELL indicator
- Sender and recipient addresses (shortened)
- Token amounts
- Transaction value in ETH (if available)
- Direct link to appropriate block explorer
- Timestamp

## Installation

Install the new dependencies:

```bash
pip install -r requirements.txt
```

## Running

Start the bot as usual:

```bash
python bot.py
```

Then go to your Telegram group and type:
- `/startmonitor` to begin receiving EMP transaction updates
- `/starttalos` to begin receiving Talos transaction updates 