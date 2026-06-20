"""
Tests for processor.py — the heart of the reconciliation logic.

Run them all from the project folder with:   pytest
Each test follows the same shape:
    1. build a tiny, known input
    2. call the real function
    3. assert the output is exactly what we expect
"""
import pandas as pd
from reconciliation import processor


# ---------------------------------------------------------------------------
# TEST 1 — tokenize(): German name normalization
# ---------------------------------------------------------------------------
def test_tokenize_handles_umlauts_and_case():
    # "Müller" should become "muller" (ü -> u), lowercased, split into words.
    result = processor.tokenize("Müller GmbH")
    assert result == ["muller", "gmbh"]


def test_tokenize_empty_value_returns_empty_list():
    # Missing names (NaN) must not crash — they should give an empty list.
    assert processor.tokenize(None) == []


# ---------------------------------------------------------------------------
# TEST 2 — extract_receipt_and_order_id_from_five_digits():
#          small numbers = receipt, big numbers = order id
# ---------------------------------------------------------------------------
def test_extract_receipt_and_order_id():
    df = pd.DataFrame({"five_digits": [[11469, 21066], [], [99999]]})
    out = processor.extract_receipt_and_order_id_from_five_digits(df)

    # Row 0: 11469 < 12000 -> receipt;  21066 > 20000 -> order id
    assert out.loc[0, "receipt_number"] == 11469
    assert out.loc[0, "order_id"] == 21066
    # Row 1: nothing found. NOTE: pandas stores "missing" in a numeric column
    # as NaN (not None), so we check with pd.isna(), not `is None`.
    assert pd.isna(out.loc[1, "receipt_number"])
    assert pd.isna(out.loc[1, "order_id"])
    # Row 2: 99999 is > 20000 only -> order id, no receipt (missing -> NaN)
    assert pd.isna(out.loc[2, "receipt_number"])
    assert out.loc[2, "order_id"] == 99999


# ---------------------------------------------------------------------------
# Helpers to build tiny orders/bank tables for the matcher tests
# ---------------------------------------------------------------------------
# We pass real pd.Timestamp dates (exactly like the pipeline does after
# load_orders/load_bank parse them) — never raw strings, to avoid day/month
# ambiguity.
def _order(name_tokens, amount, date):
    return pd.DataFrame([{
        "name": "x", "amount_paid": amount, "date": pd.Timestamp(date),
        "tokenized_name": name_tokens, "receipt_number": 1, "order_id": 2,
    }])


def _payment(name_tokens, amount, date):
    return pd.DataFrame([{
        "client_name": "x", "amount": amount, "transaction_date": pd.Timestamp(date),
        "tokenized_name": name_tokens, "receipt_number": 1, "order_id": 2,
    }])


# ---------------------------------------------------------------------------
# TEST 3 — THE BUG WE FIXED: amount must match, even if name+date agree
# ---------------------------------------------------------------------------
def test_no_match_when_amount_is_wrong():
    orders = _order(["mueller"], amount=100.0, date="2025-10-01")
    bank   = _payment(["mueller"], amount=999.0, date="2025-10-02")  # name+date OK, amount WAY off

    unmatched_orders, unmatched_payments, matched = processor.match_by_name_and_amount(
        orders, bank, amount_tolerance=3.0, date_window_days=15
    )

    # Because the amount disagrees, nothing should match.
    assert len(matched) == 0
    assert len(unmatched_orders) == 1
    assert len(unmatched_payments) == 1


# ---------------------------------------------------------------------------
# TEST 4 — a real match: amount + name + date all agree
# ---------------------------------------------------------------------------
def test_match_when_all_three_agree():
    orders = _order(["mueller"], amount=100.0, date="2025-10-01")
    bank   = _payment(["mueller"], amount=100.0, date="2025-10-05")  # within €3 and 15 days

    unmatched_orders, unmatched_payments, matched = processor.match_by_name_and_amount(
        orders, bank, amount_tolerance=3.0, date_window_days=15
    )

    assert len(matched) == 1
    assert len(unmatched_orders) == 0
    assert len(unmatched_payments) == 0
