#!/usr/bin/env python3
"""
Test script to verify the EMP price function in bot.py
"""

from bot import get_emp_price_from_pool

def test_emp_price():
    print("🧪 Testing EMP price function from bot.py")
    print("=" * 50)
    
    try:
        price = get_emp_price_from_pool()
        if price:
            print(f"✅ EMP Price: ${price:.6f}")
            return True
        else:
            print("❌ Failed to get EMP price")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_emp_price() 