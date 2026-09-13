from rb_interbank.addressing import (
    display_account,
    parse_address,
    ticker_candidates,
)


def test_parse_colon_bank_and_short_account():
    assert parse_address("DRB:MDBZ") == ("DRB", "MDBZ")
    assert parse_address("drb/mdbz") == ("DRB", "MDBZ")


def test_hyphen_is_a_ticker_not_a_bank_split():
    assert parse_address("DRB-MDBZ") == (None, "DRB-MDBZ")


def test_drb_short_name_expands_to_canonical_ticker():
    assert ticker_candidates("DRB", "MDBZ") == ["MDBZ", "DRB-MDBZ"]
    assert ticker_candidates("DRB", "DRB-MDBZ") == ["DRB-MDBZ", "MDBZ"]


def test_vdrb_has_no_forced_prefix_expansion_when_prefix_empty():
    assert ticker_candidates("VDRB", "JDSV", prefix="") == ["JDSV"]


def test_display_strips_house_prefix():
    assert display_account("DRB", "DRB-MDBZ") == "MDBZ"
    assert display_account("VDRB", "JDSV") == "JDSV"
