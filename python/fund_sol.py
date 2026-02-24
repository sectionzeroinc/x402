"""Request SOL from Solana devnet faucet."""

import json
from solana.rpc.api import Client
from solders.pubkey import Pubkey
import time

# Load keypair
with open("solana_test_keypair.json", "r") as f:
    data = json.load(f)
    address = data["pubkey"]

print(f"=== Requesting SOL for {address[:8]}... ===\n")

client = Client("https://api.devnet.solana.com")
address_pubkey = Pubkey.from_string(address)

# Request SOL airdrop
print("1. Requesting 2 SOL from devnet faucet...")
try:
    sig = client.request_airdrop(address_pubkey, 2_000_000_000)  # 2 SOL
    print(f"   Transaction: {sig.value}")
    print("   Waiting for confirmation...")
    
    time.sleep(5)
    
    # Check balance
    balance = client.get_balance(address_pubkey).value / 1_000_000_000
    print(f"   ✅ Balance: {balance:.4f} SOL")
    
except Exception as e:
    print(f"   ❌ Airdrop failed: {e}")
    print("   (Faucet may be rate-limited)")

print("\n2. For USDC, you'll need to use the web faucet:")
print("   https://spl-token-faucet.com/")
print(f"   Paste address: {address}")
print("   Request 30-50 USDC")

print("\n3. After USDC arrives, run:")
print("   python check_balance_new.py")
print("   (to verify both SOL + USDC)")
