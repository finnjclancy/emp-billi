#!/usr/bin/env python3

import json

# Load existing user stats
with open('user_stats.json', 'r') as f:
    user_stats = json.load(f)

# Update existing users with usernames
# You can manually add usernames here
user_stats["6784470708"]["username"] = "@finn🥛"

# Save updated data
with open('user_stats.json', 'w') as f:
    json.dump(user_stats, f, indent=2)

print("✅ Updated user_stats.json with usernames")
print("Current data:")
print(json.dumps(user_stats, indent=2)) 