"""Types for Solana (SVM) split scheme."""

from dataclasses import dataclass
from typing import Any


@dataclass
class SvmSplitRecipient:
    """A recipient in a split payment on Solana."""

    address: str  # Solana address (base58)
    bps: int  # Basis points (1-10000)

    def validate(self) -> None:
        if not self.address:
            raise ValueError("Recipient address cannot be empty")
        if self.bps < 1 or self.bps > 10000:
            raise ValueError(f"bps must be 1-10000, got {self.bps}")


@dataclass
class SvmSplitConfig:
    """Configuration for a Solana split payment."""

    recipients: list[SvmSplitRecipient]

    def validate(self) -> None:
        if not self.recipients:
            raise ValueError("At least one recipient is required")

        total_bps = sum(r.bps for r in self.recipients)
        if total_bps != 10000:
            raise ValueError(f"Recipient bps must sum to 10000, got {total_bps}")

        for r in self.recipients:
            r.validate()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SvmSplitConfig":
        recipients = [
            SvmSplitRecipient(
                address=r["address"],
                bps=int(r["bps"]),
            )
            for r in data.get("recipients", [])
        ]
        return cls(recipients=recipients)


def calculate_split_amounts(
    total_amount: int,
    recipients: list[SvmSplitRecipient],
) -> list[tuple[str, int]]:
    """Calculate per-recipient amounts from total and basis points.

    Uses floor division. Remainder (dust) goes to the last recipient
    to match Stellar split behavior.

    Args:
        total_amount: Total amount in atomic units (e.g., 30 USDC = 30_000_000 for 6 decimals)
        recipients: List of split recipients

    Returns:
        List of (address, amount) tuples.
    """
    splits: list[tuple[str, int]] = []
    allocated = 0

    for i, recipient in enumerate(recipients):
        # Last recipient gets remainder to handle dust
        if i == len(recipients) - 1:
            amount = total_amount - allocated
        else:
            amount = (total_amount * recipient.bps) // 10000
            allocated += amount

        splits.append((recipient.address, amount))

    return splits
