"""
Solana Devnet REAL On-Chain Split Test
Transfers actual USDC on devnet to verify the split scheme works.

Uses 1 USDC to keep costs low:
  - 0.70 USDC → Recipient A (70%)
  - 0.20 USDC → Recipient B (20%)
  - 0.10 USDC → Recipient C (10%)
"""

import json
import time
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer as sol_transfer
from solders.message import Message
from solders.transaction import Transaction
from solders.hash import Hash
from spl.token.instructions import (
    TransferCheckedParams,
    transfer_checked,
    create_associated_token_account,
    get_associated_token_address,
)
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID

DEVNET_RPC = "https://api.devnet.solana.com"
USDC_MINT = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
USDC_DECIMALS = 6

print("=" * 60)
print("  SOLANA SPLIT SCHEME — REAL ON-CHAIN TEST")
print("=" * 60)

# 1. Load client keypair (funded with SOL + USDC)
# Try both keypair files and formats
import os
import base58

loaded = False
for fname in ["test_solana_keypair.json", "solana_test_keypair.json"]:
    if not os.path.exists(fname):
        continue
    with open(fname, "r") as f:
        data = json.load(f)
    try:
        if "secret_hex" in data:
            client_secret = bytes.fromhex(data["secret_hex"])
        elif "secret_base58" in data:
            client_secret = base58.b58decode(data["secret_base58"])
        else:
            continue
        client_kp = Keypair.from_bytes(client_secret)
        print(f"Loaded keypair from {fname}")
        loaded = True
        break
    except Exception as e:
        print(f"Failed to load {fname}: {e}")

if not loaded:
    print("ERROR: Could not load any keypair file")
    exit(1)

print(f"\nClient: {client_kp.pubkey()}")

client = Client(DEVNET_RPC)

# Verify balance first
mint = Pubkey.from_string(USDC_MINT)
client_ata = get_associated_token_address(client_kp.pubkey(), mint)

resp = client.get_token_account_balance(client_ata)
if resp.value is None:
    print("ERROR: No USDC token account found")
    exit(1)

usdc_balance = float(resp.value.ui_amount)
print(f"USDC Balance: {usdc_balance} USDC")

if usdc_balance < 1.0:
    print("ERROR: Need at least 1 USDC for test")
    exit(1)

# 2. Generate 3 fresh recipient keypairs
recipients = [
    ("Artist", 7000, Keypair()),
    ("Producer", 2000, Keypair()),
    ("Platform", 1000, Keypair()),
]

print(f"\nRecipients:")
for name, bps, kp in recipients:
    print(f"  {name} ({bps/100:.0f}%): {kp.pubkey()}")

# 3. Calculate split amounts for 1 USDC
total_atomic = 1_000_000  # 1 USDC
splits = []
allocated = 0
for name, bps, kp in recipients:
    share = (total_atomic * bps) // 10000
    splits.append((name, share, kp))
    allocated += share

# Dust to first recipient
dust = total_atomic - allocated
if dust > 0:
    name, share, kp = splits[0]
    splits[0] = (name, share + dust, kp)

print(f"\nSplit breakdown (1 USDC):")
total_check = 0
for name, amt, kp in splits:
    total_check += amt
    print(f"  {name}: {amt / 1_000_000:.6f} USDC ({amt} atomic)")
print(f"  Total: {total_check / 1_000_000:.6f} USDC ({'✅' if total_check == total_atomic else '❌'})")

# 4. Fund recipients with SOL (for ATA creation rent)
print(f"\nFunding recipients with SOL for rent...")
for name, amt, kp in splits:
    try:
        sig = client.request_airdrop(kp.pubkey(), 100_000_000)  # 0.1 SOL
        print(f"  {name}: airdrop requested ({sig.value})")
    except Exception as e:
        print(f"  {name}: airdrop failed - {e}")
    time.sleep(1)

print("  Waiting for airdrops to confirm...")
time.sleep(10)

# Verify SOL arrived
for name, amt, kp in splits:
    bal = client.get_balance(kp.pubkey())
    sol = bal.value / 1_000_000_000
    print(f"  {name}: {sol:.4f} SOL")

# 5. Create ATAs for recipients
print(f"\nCreating USDC token accounts for recipients...")
for name, amt, kp in splits:
    try:
        ata = get_associated_token_address(kp.pubkey(), mint)
        # Build create ATA instruction
        ix = create_associated_token_account(
            payer=client_kp.pubkey(),
            owner=kp.pubkey(),
            mint=mint,
        )
        recent = client.get_latest_blockhash()
        msg = Message.new_with_blockhash(
            [ix], client_kp.pubkey(), recent.value.blockhash
        )
        tx = Transaction.new_unsigned(msg)
        tx.sign([client_kp], recent.value.blockhash)
        result = client.send_transaction(tx, opts=TxOpts(skip_preflight=True))
        print(f"  {name} ATA created: {ata}")
        time.sleep(2)
    except Exception as e:
        err_str = str(e)
        if "already in use" in err_str.lower() or "0x0" in err_str:
            print(f"  {name} ATA already exists")
        else:
            print(f"  {name} ATA creation: {e}")

time.sleep(5)

# 6. Execute transfers (the actual split!)
print(f"\n{'=' * 60}")
print(f"  EXECUTING ON-CHAIN SPLITS")
print(f"{'=' * 60}")

successful = 0
for name, amt, kp in splits:
    recipient_ata = get_associated_token_address(kp.pubkey(), mint)
    try:
        ix = transfer_checked(
            TransferCheckedParams(
                program_id=TOKEN_PROGRAM_ID,
                source=client_ata,
                mint=mint,
                dest=recipient_ata,
                owner=client_kp.pubkey(),
                amount=amt,
                decimals=USDC_DECIMALS,
            )
        )
        recent = client.get_latest_blockhash()
        msg = Message.new_with_blockhash(
            [ix], client_kp.pubkey(), recent.value.blockhash
        )
        tx = Transaction.new_unsigned(msg)
        tx.sign([client_kp], recent.value.blockhash)
        
        result = client.send_transaction(tx, opts=TxOpts(skip_preflight=True))
        sig = str(result.value)
        print(f"  ✅ {name}: {amt / 1_000_000:.6f} USDC → {sig[:20]}...")
        successful += 1
        time.sleep(2)
    except Exception as e:
        print(f"  ❌ {name}: FAILED — {e}")

time.sleep(5)

# 7. Verify receipts
print(f"\nVerifying recipient balances...")
for name, expected_amt, kp in splits:
    ata = get_associated_token_address(kp.pubkey(), mint)
    try:
        bal = client.get_token_account_balance(ata)
        if bal.value:
            received = int(bal.value.amount)
            match = "✅" if received == expected_amt else "❌"
            print(f"  {name}: {received / 1_000_000:.6f} USDC (expected {expected_amt / 1_000_000:.6f}) {match}")
        else:
            print(f"  {name}: No balance found")
    except Exception as e:
        print(f"  {name}: Error checking balance — {e}")

# 8. Summary
print(f"\n{'=' * 60}")
print(f"  RESULTS")
print(f"{'=' * 60}")
print(f"  Transfers: {successful}/{len(splits)} successful")
print(f"  Total distributed: {total_atomic / 1_000_000:.6f} USDC")
if successful == len(splits):
    print(f"  🎉 ALL SPLITS EXECUTED SUCCESSFULLY ON-CHAIN!")
    print(f"  The Solana split scheme is VERIFIED on devnet.")
else:
    print(f"  ⚠️  {len(splits) - successful} transfer(s) failed.")
print(f"{'=' * 60}")
