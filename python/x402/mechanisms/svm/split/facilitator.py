"""Solana (SVM) facilitator implementation for the Split payment scheme.

Verifies escrow transfer and executes distribution to recipients.
"""

import base64
import time
from typing import Any

from solana.rpc.api import Client
from solders.transaction import Transaction, VersionedTransaction
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from spl.token.constants import TOKEN_PROGRAM_ID  # type: ignore
from spl.token.instructions import TransferCheckedParams, transfer_checked  # type: ignore

from ..constants import DEFAULT_DECIMALS
from ..signers import FacilitatorKeypairSigner
from ..utils import (
    decode_transaction_from_payload,
    derive_ata,
    extract_transaction_info,
    get_network_config,
    normalize_network,
    validate_svm_address,
)
from .constants import SCHEME_SPLIT
from .types import SvmSplitConfig, calculate_split_amounts


class SplitSvmFacilitator:
    """Solana facilitator for the Split payment scheme.

    Verifies escrow transfer and executes distribution.
    """

    scheme = SCHEME_SPLIT

    def __init__(self, signer: FacilitatorKeypairSigner):
        self._signer = signer

    async def verify(
        self,
        payload: dict[str, Any],
        requirements: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify a split payment escrow transfer.

        Args:
            payload: PaymentPayload dictionary.
            requirements: PaymentRequirements dictionary.

        Returns:
            VerifyResponse dictionary.
        """
        try:
            # 1. Validate scheme
            if payload.get("scheme") != SCHEME_SPLIT:
                return self._invalid("unsupported_scheme")
            if requirements.get("scheme") != SCHEME_SPLIT:
                return self._invalid("unsupported_scheme")

            # 2. Parse split config
            split_config = self._parse_split_config(requirements)
            if split_config is None:
                return self._invalid("invalid_split_config")

            try:
                split_config.validate()
            except ValueError as e:
                return self._invalid(f"invalid_split_config: {e}")

            # 3. Validate recipient addresses
            for recipient in split_config.recipients:
                if not validate_svm_address(recipient.address):
                    return self._invalid(f"invalid_recipient_address: {recipient.address}")

            # 4. Verify escrow transaction structure
            network = normalize_network(requirements["network"])
            expected_mint = requirements["asset"]
            expected_recipient = requirements["payTo"]
            expected_amount = int(requirements["amount"])

            # Decode transaction
            tx_data = payload.get("transaction", "")
            if not tx_data:
                return self._invalid("missing_transaction")

            from ..types import ExactSvmPayload

            svm_payload = ExactSvmPayload(transaction=tx_data)
            tx = decode_transaction_from_payload(svm_payload)

            # Extract transfer info
            tx_info = extract_transaction_info(tx)
            if tx_info is None:
                return self._invalid("no_transfer_instruction_found")

            # Validate transfer parameters
            if tx_info.mint != expected_mint:
                return self._invalid(f"mint_mismatch: expected {expected_mint}, got {tx_info.mint}")

            # For split, destination should be facilitator (payTo)
            facilitator_pubkey = await self._signer.get_public_key()
            facilitator_addr = str(facilitator_pubkey)
            facilitator_ata = derive_ata(facilitator_addr, expected_mint, tx_info.token_program)

            if tx_info.destination_ata != facilitator_ata:
                return self._invalid(f"recipient_mismatch: expected facilitator ATA {facilitator_ata}")

            if tx_info.amount < expected_amount:
                return self._invalid(f"amount_insufficient: expected {expected_amount}, got {tx_info.amount}")

            # Fee payer should not be facilitator
            if tx_info.fee_payer == facilitator_addr:
                return self._invalid("fee_payer_is_facilitator")

            return {
                "is_valid": True,
                "payer": tx_info.payer,
            }

        except Exception as e:
            return self._invalid(f"unexpected_verify_error: {e}")

    async def settle(
        self,
        payload: dict[str, Any],
        requirements: dict[str, Any],
    ) -> dict[str, Any]:
        """Settle a split payment.

        1. Submit escrow transfer
        2. Execute distribution to recipients

        Args:
            payload: PaymentPayload dictionary.
            requirements: PaymentRequirements dictionary.

        Returns:
            SettleResponse dictionary.
        """
        network = normalize_network(requirements["network"])

        # Step 1: Verify
        verify_result = await self.verify(payload, requirements)
        if not verify_result.get("is_valid"):
            return {
                "success": False,
                "transaction": "",
                "network": network,
                "payer": verify_result.get("payer", ""),
                "extra": {"error": verify_result.get("invalid_reason", "verification_failed")},
            }

        payer = verify_result["payer"]

        # Step 2: Submit escrow transaction
        config = get_network_config(network)
        client = Client(config["rpc_url"])

        tx_data = payload["transaction"]
        tx_bytes = base64.b64decode(tx_data)

        from solders.transaction import VersionedTransaction

        tx = VersionedTransaction.from_bytes(tx_bytes)

        # Complete signing
        facilitator_keypair = await self._signer.get_keypair()
        tx.sign([facilitator_keypair], client.get_latest_blockhash().value.blockhash)

        # Submit
        result = client.send_raw_transaction(bytes(tx))
        tx_hash = str(result.value)

        # Wait for confirmation
        confirmed = self._wait_for_confirmation(client, tx_hash, timeout=30)
        if not confirmed:
            return {
                "success": False,
                "transaction": tx_hash,
                "network": network,
                "payer": payer,
                "extra": {"error": "escrow_confirmation_timeout"},
            }

        # Step 3: Execute distribution
        split_config = self._parse_split_config(requirements)
        total_amount = int(requirements["amount"])
        mint = requirements["asset"]

        splits = calculate_split_amounts(total_amount, split_config.recipients)

        # Build distribution transactions (one per recipient)
        distribution_hashes = []
        facilitator_addr = str(await self._signer.get_public_key())

        for recipient_addr, amount in splits:
            # Build transfer from facilitator to recipient
            source_ata = derive_ata(facilitator_addr, mint)
            dest_ata = derive_ata(recipient_addr, mint)

            transfer_ix = transfer_checked(
                TransferCheckedParams(
                    program_id=TOKEN_PROGRAM_ID,
                    source=Pubkey.from_string(source_ata),
                    mint=Pubkey.from_string(mint),
                    dest=Pubkey.from_string(dest_ata),
                    owner=await self._signer.get_public_key(),
                    amount=amount,
                    decimals=requirements.get("extra", {}).get("decimals", DEFAULT_DECIMALS),
                )
            )

            # Create and sign transaction
            dist_tx = Transaction()
            dist_tx.add(transfer_ix)
            dist_tx.recent_blockhash = client.get_latest_blockhash().value.blockhash
            dist_tx.sign(facilitator_keypair)

            # Submit
            dist_result = client.send_raw_transaction(bytes(dist_tx))
            dist_hash = str(dist_result.value)
            distribution_hashes.append(dist_hash)

            # Wait for confirmation
            self._wait_for_confirmation(client, dist_hash, timeout=30)

        # Return success with split details
        split_details = [
            {"address": addr, "amount": str(amt), "transaction": dist_hash}
            for (addr, amt), dist_hash in zip(splits, distribution_hashes)
        ]

        return {
            "success": True,
            "transaction": tx_hash,
            "network": network,
            "payer": payer,
            "extra": {
                "escrow_hash": tx_hash,
                "distributions": split_details,
            },
        }

    def _parse_split_config(self, requirements: dict[str, Any]) -> SvmSplitConfig | None:
        try:
            extra = requirements.get("extra", {})
            if isinstance(extra, dict) and "recipients" in extra:
                return SvmSplitConfig.from_dict(extra)
            return None
        except Exception:
            return None

    def _invalid(self, reason: str, payer: str | None = None) -> dict[str, Any]:
        return {"is_valid": False, "invalid_reason": reason, "payer": payer}

    def _wait_for_confirmation(self, client: Client, tx_hash: str, timeout: int = 30) -> bool:
        """Wait for transaction confirmation."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                result = client.get_transaction(tx_hash)
                if result.value:
                    return True
            except Exception:
                pass
            time.sleep(2)
        return False
