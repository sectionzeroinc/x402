"""Test Solana RPC connectivity after http/ → http_api/ rename."""

# Test that we can now import Solana RPC without http.client conflict
try:
    from solana.rpc.api import Client
    from solders.keypair import Keypair
    
    print("✅ Solana RPC imports successful (http conflict resolved)")
    
    # Test RPC connectivity
    client = Client("https://api.devnet.solana.com")
    slot = client.get_slot().value
    
    print(f"✅ Connected to Solana devnet (slot: {slot})")
    
    # Test keypair generation
    kp = Keypair()
    print(f"✅ Keypair generation working: {str(kp.pubkey())[:8]}...")
    
    print("\n🎉 HTTP directory rename successful!")
    print("   Solana RPC imports now work correctly")
    
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("   HTTP directory conflict may still exist")
except Exception as e:
    print(f"⚠️  RPC connection failed: {e}")
    print("   (Imports work, but devnet may be unavailable)")
