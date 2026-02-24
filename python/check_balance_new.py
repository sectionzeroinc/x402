"""Check balance of funded Solana test address."""

import json
from solana.rpc.api import Client
from solders.pubkey import Pubkey
from solana.rpc.types import TokenAccountOpts

# Load keypair
with open("solana_test_keypair.json", "r") as f:
    data = json.load(f)
    address = data["pubkey"]

print(f"=== Balance Check for {address[:8]}... ===\n")

client = Client("https://api.devnet.solana.com")
address_pubkey = Pubkey.from_string(address)

# Check SOL
sol_balance = client.get_balance(address_pubkey).value / 1_000_000_000
print(f"SOL:  {sol_balance:.4f} SOL")

if sol_balance < 0.01:
    print("  ⚠️  Low SOL (may still be pending)")
else:
    print("  ✅ SOL confirmed")

# Check USDC
USDC_MINT = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
mint_pubkey = Pubkey.from_string(USDC_MINT)

try:
    response = client.get_token_accounts_by_owner(
        address_pubkey,
        TokenAccountOpts(mint=mint_pubkey)
    )
    
    if response.value:
        token_account = response.value[0]
        account_info = client.get_account_info(token_account.pubkey)
        
        if account_info.value and account_info.value.data:
            data_bytes = account_info.value.data
            amount = int.from_bytes(data_bytes[64:72], 'little')
            usdc_balance = amount / 1_000_000
            
            print(f"USDC: {usdc_balance:.6f} USDC")
            
            if usdc_balance >= 30:
                print("  ✅ USDC confirmed (enough for 30 USDC test)")
            elif usdc_balance > 0:
                print(f"  ⚠️  Only {usdc_balance:.2f} USDC (need 30)")
            else:
                print("  ⚠️  USDC account exists but empty")
        else:
            print("USDC: Account found but no data")
            usdc_balance = 0
    else:
        print("USDC: No token account found (may be pending)")
        usdc_balance = 0
        
except Exception as e:
    print(f"USDC: Error checking - {e}")
    usdc_balance = 0

print("\n" + "="*50)

if sol_balance >= 0.01 and usdc_balance >= 30:
    print("✅ Ready for live 30 USDC split test!")
    print("\nRun: python run_live_split.py")
elif sol_balance >= 0.01:
    print(f"⚠️  Have SOL, waiting for USDC")
    print(f"   Current: {usdc_balance:.2f} USDC, Need: 30 USDC")
    print("   (May still be pending, wait 10-30 seconds)")
else:
    print("⚠️  Waiting for transactions to confirm...")
    print("   Check again in 10-30 seconds")
