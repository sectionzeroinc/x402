"""Unit tests for Solana (SVM) split scheme."""

import pytest

from x402.mechanisms.svm.split.types import (
    SvmSplitConfig,
    SvmSplitRecipient,
    calculate_split_amounts,
)


class TestSvmSplitCalculations:
    """Test split amount calculations."""

    def test_basic_70_20_10_split(self):
        """Test 70/20/10 split with 30 USDC."""
        recipients = [
            SvmSplitRecipient("Artist123", 7000),
            SvmSplitRecipient("Producer456", 2000),
            SvmSplitRecipient("Platform789", 1000),
        ]

        # 30 USDC = 30_000_000 (6 decimals)
        splits = calculate_split_amounts(30_000_000, recipients)

        assert len(splits) == 3
        
        # Artist: 70% = 21 USDC
        assert splits[0] == ("Artist123", 21_000_000)
        
        # Producer: 20% = 6 USDC
        assert splits[1] == ("Producer456", 6_000_000)
        
        # Platform: 10% = 3 USDC (gets dust)
        assert splits[2] == ("Platform789", 3_000_000)
        
        # Verify total
        total = sum(amt for _, amt in splits)
        assert total == 30_000_000

    def test_dust_handling(self):
        """Test that dust goes to last recipient."""
        recipients = [
            SvmSplitRecipient("A", 3333),  # 33.33%
            SvmSplitRecipient("B", 3333),  # 33.33%
            SvmSplitRecipient("C", 3334),  # 33.34%
        ]

        splits = calculate_split_amounts(100, recipients)
        
        # A: floor(100 * 3333 / 10000) = 33
        assert splits[0] == ("A", 33)
        
        # B: floor(100 * 3333 / 10000) = 33
        assert splits[1] == ("B", 33)
        
        # C: remainder = 100 - 33 - 33 = 34 (gets dust)
        assert splits[2] == ("C", 34)
        
        # Total must equal original
        total = sum(amt for _, amt in splits)
        assert total == 100


class TestSvmSplitRecipient:
    """Test recipient validation."""

    def test_valid_recipient(self):
        """Test valid recipient creation."""
        r = SvmSplitRecipient("TestAddr123", 5000)
        r.validate()  # Should not raise

    def test_invalid_bps_too_low(self):
        """Test that bps < 1 is invalid."""
        r = SvmSplitRecipient("TestAddr123", 0)
        with pytest.raises(ValueError, match="bps must be 1-10000"):
            r.validate()

    def test_invalid_bps_too_high(self):
        """Test that bps > 10000 is invalid."""
        r = SvmSplitRecipient("TestAddr123", 10001)
        with pytest.raises(ValueError, match="bps must be 1-10000"):
            r.validate()

    def test_empty_address(self):
        """Test that empty address is invalid."""
        r = SvmSplitRecipient("", 5000)
        with pytest.raises(ValueError, match="address cannot be empty"):
            r.validate()


class TestSvmSplitConfig:
    """Test split configuration."""

    def test_valid_config(self):
        """Test valid split configuration."""
        recipients = [
            SvmSplitRecipient("A", 7000),
            SvmSplitRecipient("B", 2000),
            SvmSplitRecipient("C", 1000),
        ]
        config = SvmSplitConfig(recipients=recipients)
        config.validate()  # Should not raise

    def test_bps_must_sum_to_10000(self):
        """Test that bps must total 10000."""
        recipients = [
            SvmSplitRecipient("A", 5000),
            SvmSplitRecipient("B", 3000),  # Total = 8000 ❌
        ]
        config = SvmSplitConfig(recipients=recipients)
        with pytest.raises(ValueError, match="must sum to 10000"):
            config.validate()

    def test_empty_recipients(self):
        """Test that at least one recipient is required."""
        config = SvmSplitConfig(recipients=[])
        with pytest.raises(ValueError, match="At least one recipient is required"):
            config.validate()

    def test_from_dict(self):
        """Test config creation from dict."""
        data = {
            "recipients": [
                {"address": "A", "bps": 7000},
                {"address": "B", "bps": 3000},
            ]
        }
        config = SvmSplitConfig.from_dict(data)
        assert len(config.recipients) == 2
        assert config.recipients[0].address == "A"
        assert config.recipients[0].bps == 7000
