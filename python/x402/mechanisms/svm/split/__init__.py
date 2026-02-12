"""Solana (SVM) split payment scheme.

Enables multi-recipient payments where a single escrow transfer
is distributed to multiple recipients based on basis points (e.g.,
70% artist, 20% producer, 10% platform).
"""

from x402.mechanisms.svm.split.client import SplitSvmClient
from x402.mechanisms.svm.split.facilitator import SplitSvmFacilitator
from x402.mechanisms.svm.split.register import (
    register_split_svm_client,
    register_split_svm_facilitator,
    register_split_svm_server,
)
from x402.mechanisms.svm.split.server import SplitSvmServer
from x402.mechanisms.svm.split.types import (
    SvmSplitConfig,
    SvmSplitRecipient,
    calculate_split_amounts,
)

__all__ = [
    # Types
    "SvmSplitConfig",
    "SvmSplitRecipient",
    "calculate_split_amounts",
    # Schemes
    "SplitSvmClient",
    "SplitSvmServer",
    "SplitSvmFacilitator",
    # Registration
    "register_split_svm_client",
    "register_split_svm_server",
    "register_split_svm_facilitator",
]
