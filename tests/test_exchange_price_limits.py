from tradingagents.agents.utils import exchange_rules


def test_price_limit_matches_board_and_st_rules():
    assert exchange_rules.price_limit_pct("600000.SH") == 10.0
    assert exchange_rules.price_limit_pct("300750.SZ") == 20.0
    assert exchange_rules.price_limit_pct("688981.SH") == 20.0
    assert exchange_rules.price_limit_pct("832000.BJ") == 30.0
    assert exchange_rules.price_limit_pct("600000.SH", is_st=True) == 5.0


def test_new_listing_without_price_limit_is_not_marked_anomalous():
    assert exchange_rules.is_price_change_anomalous(
        44.0,
        "600000.SH",
        listing_days=3,
    ) is False


def test_only_change_beyond_legal_limit_is_anomalous():
    assert exchange_rules.is_price_change_anomalous(19.95, "300750.SZ") is False
    assert exchange_rules.is_price_change_anomalous(21.0, "300750.SZ") is True
