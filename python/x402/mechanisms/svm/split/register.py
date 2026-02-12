"""Registration helpers for Solana split scheme."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from x402 import x402Client, x402Facilitator, x402ResourceServer

from ..signers import FacilitatorKeypairSigner, KeypairSigner
from .client import SplitSvmClient
from .facilitator import SplitSvmFacilitator
from .server import SplitSvmServer


def register_split_svm_client(
    client: "x402Client",
    signer: KeypairSigner,
    networks: list[str] | None = None,
) -> None:
    """Register Solana split scheme with an x402Client.

    Args:
        client: The x402Client instance.
        signer: Client signer for transaction signing.
        networks: Optional list of network patterns (defaults to ["solana:*"]).
    """
    if networks is None:
        networks = ["solana:*"]

    scheme = SplitSvmClient(signer=signer)
    for network in networks:
        client.register(network, scheme)


def register_split_svm_server(
    server: "x402ResourceServer",
    networks: list[str] | None = None,
    are_fees_sponsored: bool = True,
) -> None:
    """Register Solana split scheme with an x402ResourceServer.

    Args:
        server: The x402ResourceServer instance.
        networks: Optional list of network patterns (defaults to ["solana:*"]).
        are_fees_sponsored: Whether fees are sponsored by facilitator.
    """
    if networks is None:
        networks = ["solana:*"]

    scheme = SplitSvmServer(are_fees_sponsored=are_fees_sponsored)
    for network in networks:
        server.register(network, scheme)


def register_split_svm_facilitator(
    facilitator: "x402Facilitator",
    signer: FacilitatorKeypairSigner,
    networks: list[str] | None = None,
) -> None:
    """Register Solana split scheme with an x402Facilitator.

    Args:
        facilitator: The x402Facilitator instance.
        signer: Facilitator signer with RPC client.
        networks: Optional list of networks (defaults to mainnet/devnet/testnet).
    """
    if networks is None:
        networks = [
            "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",  # Mainnet
            "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1",  # Devnet
            "solana:4uhcVJyU9pJkvQyS88uRDiswHXSCkY3z",  # Testnet
        ]

    scheme = SplitSvmFacilitator(signer=signer)
    for network in networks:
        facilitator.register([network], scheme)
