import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
import json
import os

# Global state for betting
active_bets = {}  # {token_key: {"price": float, "bets": {"user_id": "higher/lower"}}}
user_stats = {}   # {user_id: {"daily_points": int, "total_bets": int, "correct_bets": int}}
last_transaction_prices = {}  # {token_key: float}

# File paths for persistence
STATS_FILE = "user_stats.json"
BETS_FILE = "active_bets.json"

def load_data():
    """Load user stats and active bets from files"""
    global user_stats, active_bets
    
    # Load user stats
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                user_stats = json.load(f)
        except:
            user_stats = {}
    
    # Load active bets
    if os.path.exists(BETS_FILE):
        try:
            with open(BETS_FILE, 'r') as f:
                active_bets = json.load(f)
        except:
            active_bets = {}

def save_data():
    """Save user stats and active bets to files"""
    # Save user stats
    with open(STATS_FILE, 'w') as f:
        json.dump(user_stats, f)
    
    # Save active bets
    with open(BETS_FILE, 'w') as f:
        json.dump(active_bets, f)

def get_user_display_name(user) -> str:
    """Get user's display name for messages"""
    if user.username:
        return f"@{user.username}"
    elif user.first_name:
        return user.first_name
    else:
        return f"User {user.id}"

def create_betting_keyboard() -> InlineKeyboardMarkup:
    """Create inline keyboard for betting options"""
    keyboard = [
        [
            InlineKeyboardButton("🟢 HIGHER", callback_data="bet_higher"),
            InlineKeyboardButton("🔴 LOWER", callback_data="bet_lower")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_current_gmt_date() -> str:
    """Get current date in GMT timezone"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def reset_daily_stats():
    """Reset daily stats for all users"""
    global user_stats
    current_date = get_current_gmt_date()
    
    for user_id in user_stats:
        if "last_reset_date" not in user_stats[user_id]:
            user_stats[user_id]["last_reset_date"] = current_date
            user_stats[user_id]["daily_points"] = 0
        elif user_stats[user_id]["last_reset_date"] != current_date:
            user_stats[user_id]["last_reset_date"] = current_date
            user_stats[user_id]["daily_points"] = 0

def award_points_to_user(user_id: str, points: int = 1, username: str = None):
    """Award points to a user"""
    global user_stats
    
    user_id_str = str(user_id)
    if user_id_str not in user_stats:
        user_stats[user_id_str] = {
            "daily_points": 0,
            "total_bets": 0,
            "correct_bets": 0,
            "last_reset_date": get_current_gmt_date(),
            "username": username or f"User {user_id}"
        }
    elif username and "username" not in user_stats[user_id_str]:
        user_stats[user_id_str]["username"] = username
    
    user_stats[user_id_str]["daily_points"] += points
    user_stats[user_id_str]["correct_bets"] += 1
    user_stats[user_id_str]["total_bets"] += 1

def record_bet_for_user(user_id: str, username: str = None):
    """Record that a user placed a bet (for total_bets tracking)"""
    global user_stats
    
    user_id_str = str(user_id)
    if user_id_str not in user_stats:
        user_stats[user_id_str] = {
            "daily_points": 0,
            "total_bets": 0,
            "correct_bets": 0,
            "last_reset_date": get_current_gmt_date(),
            "username": username or f"User {user_id}"
        }
    elif username and "username" not in user_stats[user_id_str]:
        user_stats[user_id_str]["username"] = username
    
    user_stats[user_id_str]["total_bets"] += 1

def start_new_betting_round(token_key: str, price: float, chat_id: int, bot):
    """Start a new betting round for a token"""
    global active_bets, last_transaction_prices
    
    # Store the current price
    last_transaction_prices[token_key] = price
    
    # Create new betting round
    active_bets[token_key] = {
        "price": price,
        "bets": {},
        "chat_id": chat_id,
        "message_id": None
    }
    
    # Create betting message
    message = (
        f"🎲 **new betting round**\n"
        f"current price: **${price:,.4f}**\n"
        f"place your bets"
    )
    
    keyboard = create_betting_keyboard()
    
    return message, keyboard

def place_bet(token_key: str, user_id: int, choice: str, user) -> Tuple[bool, str]:
    """Place a bet for a user"""
    global active_bets
    
    if token_key not in active_bets:
        return False, "No active betting round for this token."
    
    user_id_str = str(user_id)
    
    # Check if user already bet
    if user_id_str in active_bets[token_key]["bets"]:
        user_display_name = get_user_display_name(user)
        return False, f"{user_display_name} tried to bet again"
    
    # Record the bet with user info
    user_display_name = get_user_display_name(user)
    active_bets[token_key]["bets"][user_id_str] = {
        "choice": choice,
        "display_name": user_display_name
    }
    record_bet_for_user(user_id, user_display_name)
    
    # Save data
    save_data()
    
    choice_emoji = "🟢" if choice == "higher" else "🔴"
    choice_text = "HIGHER" if choice == "higher" else "LOWER"
    
    return True, f"{choice_emoji} **{user_display_name}** bet on **{choice_text}**!"

def resolve_betting_round(token_key: str, new_price: float, bot) -> Optional[str]:
    """Resolve the current betting round and return result message"""
    global active_bets, last_transaction_prices
    
    if token_key not in active_bets:
        return None
    
    old_price = active_bets[token_key]["price"]
    bets = active_bets[token_key]["bets"]
    
    # Determine if price went higher or lower
    if new_price > old_price:
        winning_choice = "higher"
        price_direction = "⬆️"
    elif new_price < old_price:
        winning_choice = "lower"
        price_direction = "⬇️"
    else:
        winning_choice = "same"
        price_direction = "➡️"
    
    # Separate winners and losers
    winners = []
    losers = []
    
    for user_id_str, bet_info in bets.items():
        choice = bet_info["choice"]
        display_name = bet_info["display_name"]
        
        if choice == winning_choice:
            winners.append(display_name)
            award_points_to_user(user_id_str, username=display_name)
        else:
            losers.append(display_name)
    
    # Create result message
    result_message = (
        f"🏆 **BETTING RESULTS** 🏆\n\n"
        f"Previous Price: **${old_price:,.4f}**\n"
        f"New Price: **${new_price:,.4f}** {price_direction}\n\n"
    )
    
    if winning_choice == "same":
        result_message += "💰 **PRICE UNCHANGED** - No winners or losers!\n\n"
    else:
        if winners:
            result_message += f"✅ **WINNERS** ({winning_choice.upper()} bettors):\n"
            for display_name in winners:
                result_message += f"• {display_name}\n"
            result_message += "\n"
        
        if losers:
            result_message += f"❌ **LOSERS** ({'lower' if winning_choice == 'higher' else 'higher'} bettors):\n"
            for display_name in losers:
                result_message += f"• {display_name}\n"
            result_message += "\n"
        
        if winners:
            result_message += "🎉 Points awarded to winners!"
    
    # Clear the betting round
    del active_bets[token_key]
    save_data()
    
    return result_message

def get_daily_leaderboard(bot=None) -> str:
    """Get the current daily leaderboard"""
    reset_daily_stats()
    
    # Sort users by daily points (descending)
    sorted_users = sorted(
        user_stats.items(),
        key=lambda x: x[1]["daily_points"],
        reverse=True
    )
    
    if not sorted_users:
        return "📊 **DAILY LEADERBOARD** 📊\n\nNo bets placed today!"
    
    leaderboard = "📊 **DAILY LEADERBOARD** 📊\n\n"
    
    for i, (user_id, stats) in enumerate(sorted_users[:10], 1):  # Top 10
        if stats["daily_points"] > 0:
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏆"
            accuracy = (stats["correct_bets"] / stats["total_bets"] * 100) if stats["total_bets"] > 0 else 0
            
            # Try to get username from stored data first
            username = stats.get("username", None)
            
            # If no username stored, try to get it from active bets
            if not username:
                for token_key, bet_data in active_bets.items():
                    if user_id in bet_data["bets"]:
                        username = bet_data["bets"][user_id]["display_name"]
                        # Update the stored data with the username
                        user_stats[user_id]["username"] = username
                        save_data()
                        break
            
            # If still no username, use user ID
            if not username:
                username = f"User {user_id}"
            
            leaderboard += f"{emoji} {username}: {stats['daily_points']} points \n({stats['correct_bets']}/{stats['total_bets']} correct, {accuracy:.1f}%)\n\n"
    
    leaderboard += "\n📅 Daily stats reset at midnight GMT!"
    
    return leaderboard

def get_user_stats(user_id: int, user_display_name: str = None) -> str:
    """Get stats for a specific user"""
    reset_daily_stats()
    
    user_id_str = str(user_id)
    if user_id_str not in user_stats:
        display_name = user_display_name or f"User {user_id}"
        return f"📊 **{display_name} stats** 📊\n\nNo bets placed yet!"
    
    stats = user_stats[user_id_str]
    accuracy = (stats["correct_bets"] / stats["total_bets"] * 100) if stats["total_bets"] > 0 else 0
    
    # Use provided display name or try to get stored username
    if user_display_name:
        display_name = user_display_name
    else:
        display_name = stats.get("username", f"User {user_id}")
    
    return (
        f"📊 **{display_name} stats** 📊\n\n"
        f"🎯 Daily Points: {stats['daily_points']}\n"
        f"📈 Total Bets: {stats['total_bets']}\n"
        f"✅ Correct Bets: {stats['correct_bets']}\n"
        f"📊 Accuracy: {accuracy:.1f}%\n\n"
        f"📅 Daily stats reset at midnight GMT!"
    )

async def send_daily_leaderboard(bot, chat_id: int):
    """Send daily leaderboard and reset stats"""
    leaderboard = get_daily_leaderboard()
    await bot.send_message(chat_id=chat_id, text=leaderboard, parse_mode='Markdown')

async def schedule_daily_leaderboard(bot, chat_id: int):
    """Schedule daily leaderboard to be sent at midnight GMT"""
    while True:
        now = datetime.now(timezone.utc)
        # Calculate time until next midnight GMT
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        seconds_until_midnight = (tomorrow - now).total_seconds()
        
        # Wait until midnight
        await asyncio.sleep(seconds_until_midnight)
        
        # Send leaderboard
        try:
            await send_daily_leaderboard(bot, chat_id)
            print(f"📊 Daily leaderboard sent to chat {chat_id}")
        except Exception as e:
            print(f"❌ Error sending daily leaderboard: {e}")

# Load data on module import
load_data() 