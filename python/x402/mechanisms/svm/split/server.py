"""Solana (SVM) server implementation for the Split payment scheme."""

from typing import Any

from ..constants import DEFAULT_DECIMALS
from ..utils import normalize_network, validate_svm_address
from .types import SvmSplitRecipient

# Split scheme identifier
SCHEME_SPLIT = "split"


class SplitSvmServer:
    """Solana server for the Split payment scheme.

    Handles price parsing and split payment requirements construction.
    """

    scheme = SCHEME_SPLIT

    def __init__(self, are_fees_sponsored: bool = True):
        self._are_fees_sponsored = are_fees_sponsored

    def create_payment_requirements(
        self,
        network: str,
        asset: str,
        pay_to: str,
        amount: str | int,
        recipients: list[dict[str, Any]],
        max_timeout_seconds: int = 300,
        decimals: int = DEFAULT_DECIMALS,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create PaymentRequirements for a split Solana payment.

        Args:
            network: CAIP-2 network identifier (e.g., 'solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1').
            asset: SPL Token mint address.
            pay_to: Facilitator escrow address.
            amount: Total payment amount (human-readable or atomic).
            recipients: List of {address, bps} dicts.
            max_timeout_seconds: Max timeout in seconds.
            decimals: Token decimals (default 6 for USDC).
            description: Optional payment description.

        Returns:
            PaymentRequirements dictionary.

        Raises:
            ValueError: If validation fails.
        """
        # Validate and normalize network to CAIP-2
        try:
            network = normalize_network(network)
        except ValueError:
            raise ValueError(f"Not a Solana network: {network}")

        if not validate_svm_address(asset):
            raise ValueError(f"Invalid SPL token mint address: {asset}")

        if not validate_svm_address(pay_to):
            raise ValueError(f"Invalid facilitator address: {pay_to}")

        # Validate recipients
        if not recipients:
            raise ValueError("At least one recipient is required")

        total_bps = 0
        for r in recipients:
            addr = r.get("address", "")
            bps = int(r.get("bps", 0))
            if not validate_svm_address(addr):
                raise ValueError(f"Invalid recipient address: {addr}")
            if bps < 1 or bps > 10000:
                raise ValueError(f"Invalid bps {bps} for {addr}")
            total_bps += bps

        if total_bps != 10000:
            raise ValueError(f"Recipient bps must sum to 10000, got {total_bps}")

        # Convert amount to atomic units if needed
        if isinstance(amount, (int, float)):
            atomic_amount = str(int(amount * (10**decimals)))
        else:
            atomic_amount = str(amount)

        return {
            "scheme": SCHEME_SPLIT,
            "network": network,
            "amount": atomic_amount,
            "asset": asset,
            "payTo": pay_to,
            "maxTimeoutSeconds": max_timeout_seconds,
            "extra": {
                "areFeesSponsored": self._are_fees_sponsored,
                "recipients": recipients,
            },
        }
