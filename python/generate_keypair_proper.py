"""Generate Solana keypair with FULL secret saved (64 bytes)."""

from solders.keypair import Keypair
import json
import base58

# Generate new keypair
kp = Keypair()

print("=== New Solana Test Keypair ===\n")
print(f"Address: {kp.pubkey()}\n")

# Save FULL 64-byte secret (private + public)
keypair_full = bytes(kp)  # ✅ Complete 64 bytes
keypair_b58 = base58.b58encode(keypair_full).decode('ascii')

data = {
    "pubkey": str(kp.pubkey()),
    "secret_base58": keypair_b58,  # ✅ Full secret for signing
}

with open("solana_test_keypair.json", "w") as f:
    json.dump(data, f, indent=2)

print("💾 Saved to: solana_test_keypair.json")
print("   (Includes full 64-byte secret for signing)\n")

print("📋 Fund this address:")
print(f"   {kp.pubkey()}\n")

print("1. SOL Faucet:")
print("   https://faucet.solana.com/")
print("   → Request 1-2 SOL\n")

print("2. USDC Faucet:")
print("   https://spl-token-faucet.com/")
print("   → Request 30-50 USDC\n")

# Verify we can reload and sign
print("✅ Verification: Keypair can be reloaded for signing")
reloaded = Keypair.from_bytes(keypair_full)
print(f"   Reloaded pubkey: {reloaded.pubkey()}")
print(f"   Match: {'✅' if str(reloaded.pubkey()) == str(kp.pubkey()) else '❌'}")
