"""Check Solana devnet balance for funded test address."""

import json
from solana.rpc.api import Client
from solders.pubkey import Pubkey

# Load saved keypair
with open("test_solana_keypair.json", "r") as f:
    data = json.load(f)
    address = data["pubkey"]

print(f"=== Checking Balance for {address[:8]}... ===\n")

# Connect to devnet
client = Client("https://api.devnet.solana.com")
address_pubkey = Pubkey.from_string(address)

# Check SOL balance
sol_balance = 0
try:
    sol_balance = client.get_balance(address_pubkey).value / 1_000_000_000
    print(f"SOL Balance: {sol_balance:.4f} SOL")
    
    if sol_balance > 0:
        print("  ✅ SOL funding confirmed")
    else:
        print("  ⚠️ No SOL found (may be pending)")
        
except Exception as e:
    print(f"  ❌ Error checking SOL: {e}")

# Check USDC balance
USDC_MINT = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
usdc_balance = 0

try:
    mint_pubkey = Pubkey.from_string(USDC_MINT)
    
    # Get token accounts for this address
    from solana.rpc.types import TokenAccountOpts
    response = client.get_token_accounts_by_owner(
        address_pubkey,
        TokenAccountOpts(mint=mint_pubkey)
    )
    
    if response.value:
        # Found USDC account
        token_account = response.value[0]
        # Get account balance via token program
        token_pubkey = token_account.pubkey
        
        # Parse token amount from account data
        account_info = client.get_account_info(token_pubkey)
        if account_info.value and account_info.value.data:
            # Token account data structure:
            # bytes 64-71: amount (u64, little-endian)
            data_bytes = account_info.value.data
            amount = int.from_bytes(data_bytes[64:72], 'little')
            usdc_balance = amount / 1_000_000  # 6 decimals
            
            print(f"\nUSDC Balance: {usdc_balance:.6f} USDC")
            
            if usdc_balance >= 30:
                print("  ✅ USDC funding confirmed (enough for 30 USDC test)")
            elif usdc_balance > 0:
                print(f"  ⚠️ Only {usdc_balance:.6f} USDC (need 30 for full test)")
            else:
                print("  ⚠️ USDC account exists but empty")
    else:
        print("\nUSDC: No token account found")
        print("  ⚠️ May need to create ATA or USDC is still pending")
        
except Exception as e:
    print(f"\n  ❌ Error checking USDC: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*50)
if sol_balance > 0 and usdc_balance >= 30:
    print("✅ Ready for live 30 USDC split test!")
elif sol_balance > 0:
    print(f"⚠️  Have SOL, waiting for USDC (need 30, have {usdc_balance:.2f})")
else:
    print("⚠️  Waiting for confirmations...")

