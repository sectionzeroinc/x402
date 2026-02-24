"""Verify the saved keypair can be loaded and used for signing."""

import json
import base58
from solders.keypair import Keypair

# Load the saved keypair
with open("solana_test_keypair.json", "r") as f:
    data = json.load(f)

print("=== Keypair Verification ===\n")
print(f"Address: {data['pubkey']}\n")

# Decode and reload the full secret
secret_b58 = data['secret_base58']
secret_bytes = base58.b58decode(secret_b58)

print(f"Secret length: {len(secret_bytes)} bytes")

if len(secret_bytes) == 64:
    print("✅ Full 64-byte secret saved (can sign transactions)\n")
    
    # Test reload
    kp = Keypair.from_bytes(secret_bytes)
    print(f"Reloaded address: {kp.pubkey()}")
    print(f"Match: {'✅' if str(kp.pubkey()) == data['pubkey'] else '❌'}\n")
    
    print("📋 Fund this address:")
    print(f"   {data['pubkey']}\n")
    print("1. SOL: https://faucet.solana.com/")
    print("2. USDC: https://faucet.circle.com/ (select Solana Devnet)")
    
else:
    print(f"❌ Only {len(secret_bytes)} bytes saved (need 64)")
