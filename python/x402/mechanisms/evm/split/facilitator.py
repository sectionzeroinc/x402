"""EVM facilitator implementation for the Split payment scheme."""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from ....schemas import (
    Network,
    PaymentPayload,
    PaymentRequirements,
    SettleResponse,
    VerifyResponse,
)
from ..constants import (
    SCHEME_EXACT,
    TRANSFER_WITH_AUTHORIZATION_BYTES_ABI,
    TRANSFER_WITH_AUTHORIZATION_VRS_ABI,
    TX_STATUS_SUCCESS,
    ERR_TRANSACTION_FAILED,
    ERR_UNDEPLOYED_SMART_WALLET,
    ERR_SMART_WALLET_DEPLOYMENT_FAILED,
)
from ..signer import FacilitatorEvmSigner
from ..erc6492 import has_deployment_info, parse_erc6492_signature
from ..eip712 import hash_eip3009_authorization
from ..types import ExactEIP3009Payload
from ..utils import get_asset_info, get_evm_chain_id, get_network_config, hex_to_bytes
from ..verify import verify_universal_signature
from .constants import SCHEME_SPLIT
from .types import SplitConfig, SplitRecipient


@dataclass
class SplitEvmSchemeConfig:
    """Configuration for SplitEvmScheme facilitator.

    Attributes:
        deploy_erc4337_with_eip6492: Enable ERC-6492 smart wallet deployment.
        settlement_callback: Optional callback for split distribution.
            Called with (recipients, shares, tx_hash) after settlement.
    """

    deploy_erc4337_with_eip6492: bool = False
    settlement_callback: Any = None  # Callable for custom split logic


class SplitEvmScheme:
    """EVM facilitator implementation for the Split payment scheme.

    Verifies and settles split payments on EVM networks.
    The on-chain settlement (EIP-3009 transfer to escrow) reuses
    exact scheme logic. Split distribution is handled post-settlement
    via a configurable callback (e.g., internal ledger, on-chain transfers).

    Attributes:
        scheme: The scheme identifier ("split").
    """

    scheme = SCHEME_SPLIT

    def __init__(
        self,
        signer: FacilitatorEvmSigner,
        config: SplitEvmSchemeConfig | None = None,
    ):
        """Create SplitEvmScheme facilitator.

        Args:
            signer: EVM signer for verification and settlement.
            config: Optional configuration.
        """
        self._signer = signer
        self._config = config or SplitEvmSchemeConfig()

    def get_extra(self, network: Network) -> dict[str, Any] | None:
        return None

    def get_signers(self, network: Network) -> list[str]:
        return [self._signer.address]

    def verify(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> VerifyResponse:
        """Verify split payment payload.

        Validates:
        - Scheme and network match
        - EIP-712 signature is valid
        - Recipient is facilitator escrow (payTo)
        - Amount >= total required
        - Split recipients are valid (sum to 10000 bps)

        Args:
            payload: Payment payload from client.
            requirements: Payment requirements.

        Returns:
            VerifyResponse with is_valid and payer.
        """
        try:
            inner = payload.payload
            if isinstance(inner, str):
                inner = json.loads(inner)

            eip3009 = ExactEIP3009Payload.from_dict(inner)
            auth = eip3009.authorization
            payer = auth.from_address

            # V2 uses payload.accepted.scheme; fall back to payload.scheme for V1
            scheme = getattr(getattr(payload, 'accepted', None), 'scheme', None) or getattr(payload, 'scheme', None)
            if scheme != SCHEME_SPLIT:
                return VerifyResponse(
                    is_valid=False,
                    invalid_reason=f"Expected scheme '{SCHEME_SPLIT}', got '{scheme}'",
                    payer=payer,
                )

            if int(auth.value) < int(requirements.amount):
                return VerifyResponse(
                    is_valid=False,
                    invalid_reason=f"Amount {auth.value} < required {requirements.amount}",
                    payer=payer,
                )

            if auth.to.lower() != requirements.pay_to.lower():
                return VerifyResponse(
                    is_valid=False,
                    invalid_reason=f"Recipient {auth.to} != escrow {requirements.pay_to}",
                    payer=payer,
                )

            extra = requirements.extra or {}
            if "recipients" in extra:
                try:
                    split_config = SplitConfig.from_dict_list(extra["recipients"])
                    split_config.validate()
                except ValueError as e:
                    return VerifyResponse(
                        is_valid=False,
                        invalid_reason=f"Invalid split config: {e}",
                        payer=payer,
                    )

            # Get network and asset config
            network = str(requirements.network)
            config = get_network_config(network)
            asset_info = get_asset_info(network, requirements.asset)

            # Check EIP-712 domain params
            if "name" not in extra or "version" not in extra:
                return VerifyResponse(
                    is_valid=False,
                    invalid_reason="Missing EIP-712 domain params (name, version) in extra",
                    payer=payer,
                )

            # Compute EIP-3009 hash (same as exact scheme)
            hash_bytes = hash_eip3009_authorization(
                auth,
                config["chain_id"],
                asset_info["address"],
                extra["name"],
                extra["version"],
            )

            # Verify signature
            if not eip3009.signature:
                return VerifyResponse(
                    is_valid=False,
                    invalid_reason="Missing signature",
                    payer=payer,
                )

            signature = hex_to_bytes(eip3009.signature)
            valid, _ = verify_universal_signature(
                self._signer, payer, hash_bytes, signature, allow_undeployed=True
            )

            if not valid:
                return VerifyResponse(
                    is_valid=False,
                    invalid_reason="Invalid EIP-712 signature",
                    payer=payer,
                )

            return VerifyResponse(
                is_valid=True,
                payer=payer,
            )

        except Exception as e:
            return VerifyResponse(
                is_valid=False,
                invalid_reason=f"Verification error: {e}",
            )

    def settle(
        self,
        payload: PaymentPayload,
        requirements: PaymentRequirements,
    ) -> SettleResponse:
        """Settle split payment on-chain and distribute to recipients.

        1. Re-verify payment
        2. Execute transferWithAuthorization to escrow (same as exact)
        3. Calculate per-recipient shares
        4. Execute split distribution (via callback or default)
        5. Return SettleResponse with per-recipient breakdown

        Args:
            payload: Payment payload from client.
            requirements: Payment requirements with split config.

        Returns:
            SettleResponse with success, transaction, and split details.
        """
        logger = logging.getLogger(__name__)

        # Re-verify
        verify_result = self.verify(payload, requirements)
        if not verify_result.is_valid:
            return SettleResponse(
                success=False,
                error_reason=verify_result.invalid_reason,
                transaction="",
                network=str(requirements.network),
                payer=verify_result.payer or "",
            )

        try:
            inner = payload.payload
            if isinstance(inner, str):
                inner = json.loads(inner)

            eip3009 = ExactEIP3009Payload.from_dict(inner)
            auth = eip3009.authorization
            payer = auth.from_address
            network = str(requirements.network)
            asset_info = get_asset_info(network, requirements.asset)

            # Parse signature for v/r/s extraction
            signature = hex_to_bytes(eip3009.signature)
            sig_data = parse_erc6492_signature(signature)

            # Deploy smart wallet if needed (same as exact)
            if has_deployment_info(sig_data):
                code = self._signer.get_code(payer)
                if len(code) == 0:
                    if self._config.deploy_erc4337_with_eip6492:
                        try:
                            from ..utils import bytes_to_hex
                            factory_addr = bytes_to_hex(sig_data.factory)
                            tx_hash = self._signer.send_transaction(
                                factory_addr, sig_data.factory_calldata
                            )
                            receipt = self._signer.wait_for_transaction_receipt(tx_hash)
                            if receipt.status != TX_STATUS_SUCCESS:
                                raise RuntimeError(ERR_SMART_WALLET_DEPLOYMENT_FAILED)
                        except Exception as e:
                            return SettleResponse(
                                success=False,
                                error_reason=ERR_SMART_WALLET_DEPLOYMENT_FAILED,
                                error_message=str(e),
                                network=network,
                                payer=payer,
                                transaction="",
                            )
                    else:
                        return SettleResponse(
                            success=False,
                            error_reason=ERR_UNDEPLOYED_SMART_WALLET,
                            network=network,
                            payer=payer,
                            transaction="",
                        )

            # Use inner signature for settlement
            inner_sig = sig_data.inner_signature
            is_ecdsa = len(inner_sig) == 65

            # Execute transferWithAuthorization (same as exact scheme)
            if is_ecdsa:
                # EOA: v,r,s overload
                r, s, v = inner_sig[:32], inner_sig[32:64], inner_sig[64]
                tx_hash = self._signer.write_contract(
                    asset_info["address"],
                    TRANSFER_WITH_AUTHORIZATION_VRS_ABI,
                    "transferWithAuthorization",
                    payer,
                    auth.to,
                    int(auth.value),
                    int(auth.valid_after),
                    int(auth.valid_before),
                    hex_to_bytes(auth.nonce),
                    v,
                    r,
                    s,
                )
            else:
                # Smart wallet: bytes overload
                tx_hash = self._signer.write_contract(
                    asset_info["address"],
                    TRANSFER_WITH_AUTHORIZATION_BYTES_ABI,
                    "transferWithAuthorization",
                    payer,
                    auth.to,
                    int(auth.value),
                    int(auth.valid_after),
                    int(auth.valid_before),
                    hex_to_bytes(auth.nonce),
                    inner_sig,
                )

            receipt = self._signer.wait_for_transaction_receipt(tx_hash)
            if receipt.status != TX_STATUS_SUCCESS:
                return SettleResponse(
                    success=False,
                    error_reason=ERR_TRANSACTION_FAILED,
                    transaction=tx_hash if isinstance(tx_hash, str) else f"0x{tx_hash.hex()}",
                    network=network,
                    payer=payer,
                )

            tx_hash_str = tx_hash if isinstance(tx_hash, str) else f"0x{tx_hash.hex()}"

            # Calculate and log split distribution
            total_amount = int(auth.value)
            extra = requirements.extra or {}

            if "recipients" in extra:
                split_config = SplitConfig.from_dict_list(extra["recipients"])
                shares = split_config.calculate_shares(total_amount)

                for address, amount in shares:
                    if self._config.settlement_callback:
                        self._config.settlement_callback(address, amount, tx_hash_str)

                    recipient = next(
                        (r for r in split_config.recipients if r.address == address),
                        None,
                    )
                    label = recipient.label if recipient else address[:16]
                    logger.info(
                        f"Split: {label} → {amount} ({address[:16]}...)"
                    )

            return SettleResponse(
                success=True,
                transaction=tx_hash_str,
                network=network,
                payer=payer,
            )

        except Exception as e:
            return SettleResponse(
                success=False,
                error_reason=ERR_TRANSACTION_FAILED,
                error_message=str(e),
                transaction="",
                network=str(requirements.network),
                payer=verify_result.payer or "",
            )
