#!/usr/bin/env python3
"""
Test script for PyCardano-based reward system
Tests sending ADA reward without Node.js subprocess
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.cardano_rewards import send_ada_reward, get_reward_wallet_info, is_reward_system_configured

async def test_reward_system():
    print("=" * 60)
    print("Testing Pure Python PyCardano Reward System")
    print("=" * 60)

    # Check configuration
    print("\n1. Checking configuration...")
    if not is_reward_system_configured():
        print("   ERROR: Blockfrost API key not configured!")
        return
    print("   ✓ Blockfrost API configured")

    # Get wallet info
    print("\n2. Getting reward wallet info...")
    wallet_info = get_reward_wallet_info()
    if not wallet_info.get("configured"):
        print(f"   ERROR: {wallet_info.get('error')}")
        return
    print(f"   ✓ Wallet address: {wallet_info['address']}")
    print(f"   ✓ Network: {wallet_info['network']}")

    # Send test reward to the pending entry's wallet
    recipient = "addr_test1qrfs04z8lgjspk2vl7zjurp02jpyawtv4g887hsvwynu4g3hs7mfqg2lk6rq48a4kaatu42g7q9cdq2xgm3m0ryrkswqsu8dad"
    amount = 1_000_000  # 1 ADA

    print(f"\n3. Sending {amount/1_000_000} ADA to:")
    print(f"   {recipient[:50]}...")

    result = await send_ada_reward(recipient, amount)

    print("\n4. Result:")
    if result.success:
        print(f"   ✓ SUCCESS!")
        print(f"   TX Hash: {result.tx_hash}")
        print(f"   Explorer: {result.explorer_url}")
    else:
        print(f"   ✗ FAILED: {result.error}")

    print("\n" + "=" * 60)
    return result

if __name__ == "__main__":
    result = asyncio.run(test_reward_system())
    sys.exit(0 if result and result.success else 1)