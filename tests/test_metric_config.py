"""An audit budget is a count of human reviews, so a config that implies a fractional one is refused.

`slots` used to be `max(1, round(audit_rate * horizon))`. Both halves lied. `round` turned a stated
7% of 50 into 4 audits, an effective 8%, with nothing recording the substitution — and it rounds
halves to even, so 2.5 became 2 while 3.5 became 4. The `max(1, ...)` then turned a deliberate zero
budget into one free audit, which is the shape `outcome.py` exists to prevent: a number nobody asked
for, in the direction that flatters the protocol.
"""

from __future__ import annotations

import pytest

from pipeline.config import MetricConfig


class TestABudgetThatDividesTheHorizonIsAccepted:
    def test_a_tenth_of_fifty_submissions_is_five_audits(self):
        assert MetricConfig(audit_rate=0.10, horizon=50).slots == 5

    def test_the_paper_rate_of_two_percent_is_one_audit(self):
        assert MetricConfig(audit_rate=0.02, horizon=50).slots == 1

    def test_auditing_everything_is_the_whole_horizon(self):
        assert MetricConfig(audit_rate=1.0, horizon=50).slots == 50


class TestAFractionalBudgetIsRefusedRatherThanRounded:
    def test_seven_percent_of_fifty_names_both_workable_rates(self):
        with pytest.raises(ValueError) as raised:
            MetricConfig(audit_rate=0.07, horizon=50)
        message = str(raised.value)
        assert "3.5 audits" in message
        assert "0.06" in message and "0.08" in message

    @pytest.mark.parametrize("rate", [0.05, 0.07, 0.15, 0.33])
    def test_a_rate_that_does_not_divide_the_horizon_is_refused(self, rate):
        with pytest.raises(ValueError):
            MetricConfig(audit_rate=rate, horizon=30)

    def test_a_half_is_refused_rather_than_rounded_to_even(self):
        with pytest.raises(ValueError):
            MetricConfig(audit_rate=0.05, horizon=50)


class TestStatingTheCountDirectlyBypassesTheRate:
    """`audit_slots` is the budget itself, so it is never checked against `audit_rate`."""

    def test_an_explicit_count_is_taken_as_given(self):
        assert MetricConfig(audit_rate=0.07, horizon=50, audit_slots=4).slots == 4

    def test_an_explicit_count_may_not_exceed_the_horizon(self):
        with pytest.raises(ValueError):
            MetricConfig(horizon=50, audit_slots=51)


class TestNoBudgetMeansNoAudit:
    def test_a_zero_rate_buys_zero_audits_and_is_not_raised_to_one(self):
        assert MetricConfig(audit_rate=0.0, horizon=50).slots == 0
