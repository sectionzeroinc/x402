"""
Solana Devnet Integration Test
Tests the existing SVM exact scheme implementation against Solana devnet
"""
import pytest
from solders.keypair import Keypair
from solana.rpc.api import Client
from x402.mechanisms.svm.exact import ExactSvmClientScheme, ExactSvmServerScheme
from x402.mechanisms.svm import KeypairSigner
from x402.mechanisms.svm.constants import NETWORK_CONFIGS

class TestSolanaDevnetConnection:
    """Test basic connectivity to Solana devnet"""
    
    def test_devnet_rpc_connection(self):
        """Verify we can connect to Solana devnet RPC"""
        client = Client("https://api.devnet.solana.com")
        resp = client.get_slot()
        slot = resp.value
        print(f"✅ Solana devnet RPC connected, slot: {slot}")
        assert slot > 0
    
    def test_get_latest_blockhash(self):
        """Verify we can get latest blockhash"""
        client = Client("https://api.devnet.solana.com")
        resp = client.get_latest_blockhash()
        blockhash = resp.value.blockhash
        print(f"✅ Latest blockhash: {blockhash}")
        assert blockhash is not None
    
    def test_generate_keypair(self):
        """Verify we can generate Solana keypairs"""
        kp = Keypair()
        print(f"✅ Generated keypair: {kp.pubkey()}")
        assert kp.pubkey() is not None


class TestSvmSchemeSetup:
    """Test SVM scheme initialization"""
    
    def test_client_scheme_init(self):
        """Verify client scheme can be initialized"""
        kp = Keypair()
        signer = KeypairSigner(kp)
        scheme = ExactSvmClientScheme(signer=signer)
        print(f"✅ Client scheme initialized")
        assert scheme is not None
    
    def test_server_scheme_init(self):
        """Verify server scheme can be initialized"""
        scheme = ExactSvmServerScheme()
        print(f"✅ Server scheme initialized")
        assert scheme is not None
    
    def test_network_configs(self):
        """Verify network configs exist for devnet"""
        devnet_config = NETWORK_CONFIGS.get('solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1')
        print(f"✅ Devnet config: {devnet_config}")
        assert devnet_config is not None
        assert 'rpc_url' in devnet_config
        assert devnet_config['rpc_url'] == 'https://api.devnet.solana.com'


class TestSolanaAirdrop:
    """Test Solana devnet airdrop (SOL faucet)"""
    
    @pytest.mark.integration
    def test_airdrop_sol(self):
        """Request SOL airdrop on devnet"""
        client = Client("https://api.devnet.solana.com")
        kp = Keypair()
        pubkey = kp.pubkey()
        
        print(f"Requesting SOL airdrop for {pubkey}...")
        
        # Request 1 SOL
        sig = client.request_airdrop(pubkey, 1_000_000_000)  # 1 SOL in lamports
        print(f"  Airdrop signature: {sig.value}")
        
        # Wait for confirmation
        import time
        time.sleep(5)
        
        # Check balance
        balance_resp = client.get_balance(pubkey)
        balance_sol = balance_resp.value / 1_000_000_000
        print(f"✅ Balance: {balance_sol} SOL")
        
        assert balance_sol >= 1.0
