#!/usr/bin/env python3

from betting_system import get_daily_leaderboard, load_data

# Load the data
load_data()

# Test the leaderboard function
print("Testing get_daily_leaderboard()...")
try:
    leaderboard = get_daily_leaderboard()
    print("✅ Leaderboard generated successfully:")
    print("=" * 50)
    print(leaderboard)
    print("=" * 50)
except Exception as e:
    print(f"❌ Error generating leaderboard: {e}")
    import traceback
    traceback.print_exc() 