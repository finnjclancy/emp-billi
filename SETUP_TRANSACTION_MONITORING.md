# Transaction Monitoring Setup

Your bot has been updated to automatically monitor Uniswap transactions for the pool `0x39D5313C3750140E5042887413bA8AA6145a9bd2` and post them to a Telegram group chat.

## Required Environment Variables

Add these to your `.env` file:

```env
# Existing
TOKEN=your_telegram_bot_token_here

# New variables for transaction monitoring
INFURA_URL=https://mainnet.infura.io/v3/your_infura_project_id
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
4. Copy the mainnet endpoint URL
5. Add it to your `.env` file as `INFURA_URL`

### 3. Get Etherscan API Key (Optional)
1. Go to [Etherscan.io](https://etherscan.io)
2. Create a free account
3. Go to API Keys section
4. Create a new API key
5. Add it to your `.env` file as `ETHERSCAN_API_KEY`

## New Commands

- `/startmonitor` - Start transaction monitoring in the current group
- `/stopmonitor` - Stop transaction monitoring

**Note:** Just type `/startmonitor` in any group where you want to receive transaction updates!

## Features

- **Automatic Monitoring**: Starts automatically when bot runs
- **Real-time Updates**: Posts new swaps within ~12 seconds
- **Duplicate Prevention**: Avoids posting the same transaction twice
- **Rich Messages**: Shows swap direction, amounts, addresses, and Etherscan links
- **Error Handling**: Continues monitoring even if individual transactions fail

## Message Format

Each transaction post includes:
- 🟢 BUY or 🔴 SELL indicator
- Sender and recipient addresses (shortened)
- Token amounts
- Transaction value in ETH (if available)
- Direct link to Etherscan
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

Then go to your Telegram group and type `/startmonitor` to begin receiving transaction updates! 