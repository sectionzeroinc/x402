"""Constants for Solana (SVM) split scheme."""

# Scheme identifier
SCHEME_SPLIT = "split"

# Default timeout for split payments (in seconds)
DEFAULT_TIMEOUT_SECONDS = 300

# Error codes
# Escrow validation
ERR_INVALID_ESCROW_PAYLOAD = "invalid_split_svm_escrow_payload"
ERR_ESCROW_AMOUNT_INSUFFICIENT = "invalid_split_svm_escrow_amount_insufficient"
ERR_INVALID_ESCROW_RECIPIENT = "invalid_split_svm_escrow_recipient_mismatch"

# Distribution validation
ERR_INVALID_DISTRIBUTION = "invalid_split_svm_distribution"
ERR_RECIPIENT_MISMATCH = "invalid_split_svm_recipient_mismatch"
ERR_DISTRIBUTION_AMOUNT_MISMATCH = "invalid_split_svm_distribution_amount_mismatch"
