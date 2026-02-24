"""Generate Solana test keypair for devnet funding."""

from solders.keypair import Keypair
import json

# Generate client keypair
client_kp = Keypair()

print("=== Solana Devnet Test Address ===\n")
print("Send funds to this address:")
print(f"  {client_kp.pubkey()}")

print("\n📋 What to send:")
print("  1. SOL (for transaction fees):")
print(f"     - Amount: 1 SOL")
print(f"     - Faucet: https://faucet.solana.com/")
print(f"     - Address: {client_kp.pubkey()}")

print("\n  2. USDC (devnet, for the split test):")
print(f"     - Amount: 50 USDC")
print(f"     - Mint: 4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU")
print(f"     - Address: {client_kp.pubkey()}")
print(f"     - Faucet: https://spl-token-faucet.com/ (or Circle's devnet faucet)")

# Save keypair for later use
keypair_bytes = bytes(client_kp)
keypair_b58 = client_kp.secret().hex()

print(f"\n💾 Keypair saved to: test_solana_keypair.json")

with open("test_solana_keypair.json", "w") as f:
    json.dump({
        "pubkey": str(client_kp.pubkey()),
        "secret_hex": keypair_b58,
    }, f, indent=2)

print("\n✅ Copy the address above and fund it from the faucets")
print("   Once funded, we can run the live split test (30 USDC → 70/20/10)")
