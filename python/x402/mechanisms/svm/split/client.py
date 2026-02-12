"""Solana (SVM) client implementation for the Split payment scheme.

Builds the escrow transfer (client → facilitator) for a split payment.
"""

from typing import Any

from solders.instruction import Instruction  # type: ignore
from solders.keypair import Keypair  # type: ignore
from solders.message import Message  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.transaction import Transaction  # type: ignore
from spl.token.constants import TOKEN_PROGRAM_ID  # type: ignore
from spl.token.instructions import TransferCheckedParams, transfer_checked  # type: ignore

from ..constants import DEFAULT_DECIMALS
from ..signers import KeypairSigner
from ..utils import derive_ata, normalize_network, validate_svm_address
from .constants import SCHEME_SPLIT


class SplitSvmClient:
    """Solana client for the Split payment scheme.

    Builds the escrow transfer transaction (client → facilitator).
    """

    scheme = SCHEME_SPLIT

    def __init__(self, signer: KeypairSigner):
        self._signer = signer

    async def create_payment_payload(
        self,
        requirements: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a payment payload for a split payment.

        Builds the escrow transfer: client sends total amount to facilitator.

        Args:
            requirements: PaymentRequirements dictionary.

        Returns:
            PaymentPayload dictionary with transaction and metadata.

        Raises:
            ValueError: If validation fails.
        """
        network = normalize_network(requirements["network"])
        asset = requirements["asset"]
        pay_to = requirements["payTo"]
        amount = int(requirements["amount"])

        # Validate
        if not validate_svm_address(asset):
            raise ValueError(f"Invalid SPL token mint: {asset}")
        if not validate_svm_address(pay_to):
            raise ValueError(f"Invalid facilitator address: {pay_to}")

        # Get decimals from default asset or use provided
        decimals = requirements.get("extra", {}).get("decimals", DEFAULT_DECIMALS)

        # Get payer
        payer_pubkey = await self._signer.get_public_key()
        payer = str(payer_pubkey)

        # Derive ATAs
        source_ata = derive_ata(payer, asset)
        destination_ata = derive_ata(pay_to, asset)

        # Build TransferChecked instruction
        transfer_ix = transfer_checked(
            TransferCheckedParams(
                program_id=TOKEN_PROGRAM_ID,
                source=Pubkey.from_string(source_ata),
                mint=Pubkey.from_string(asset),
                dest=Pubkey.from_string(destination_ata),
                owner=payer_pubkey,
                amount=amount,
                decimals=decimals,
            )
        )

        # Create message
        message = Message([transfer_ix], payer_pubkey)

        # Create transaction
        tx = Transaction([self._signer.keypair], message)

        # Sign
        await self._signer.sign_transaction(tx)

        # Serialize to base64
        import base64
        tx_bytes = bytes(tx)
        tx_base64 = base64.b64encode(tx_bytes).decode()

        return {
            "scheme": SCHEME_SPLIT,
            "network": network,
            "transaction": tx_base64,
            "extra": {
                "payer": payer,
                "amount": str(amount),
                "mint": asset,
                "sourceAta": source_ata,
                "destinationAta": destination_ata,
            },
        }
