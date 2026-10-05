"""Every SQL file renders completely and parses as BigQuery SQL."""
import re
from decimal import Decimal

import pytest

from atlas import constants as K

from atlas import steps

sqlglot = pytest.importorskip("sqlglot")

FILES = sorted(p.name for p in steps.SQL_DIR.glob("*.sql"))
EXTRA = {"top_n": 50, "random_n": 200}


@pytest.mark.parametrize("name", FILES)
def test_renders_and_parses(name):
    sql = steps.load(name, "myproj.atlas", extra=EXTRA)
    assert "{{" not in sql
    parsed = sqlglot.parse(sql, read="bigquery")
    assert parsed and all(p is not None for p in parsed)


def test_every_step_file_exists():
    for s in steps.STEPS:
        assert (steps.SQL_DIR / s.file).exists(), s.file


def test_unfilled_placeholder_raises():
    with pytest.raises(ValueError):
        steps.render("SELECT {{nope}}", "p.w")


def test_constants_land_in_sql():
    sql = steps.load("04_build_token_candidates.sql", "p.w")
    assert "63d505accf" in sql and "7050c9e0f4ca" in sql
    sql7 = steps.load("07_build_permit2_approvals.sql", "p.w")
    assert "0x000000000000000000000000000000000022d473030f116ddee9f6b43ac78ba3" in sql7


def test_select_default_skips_optional():
    keys = [s.key for s in steps.select(None, False)]
    assert keys == ["01", "02", "03", "04", "05", "06"]
    assert [s.key for s in steps.select(["7"], False)] == ["07"]


@pytest.mark.parametrize("name", FILES)
def test_bignumeric_literals_fit(name):
    """Regression: step 05 once cast '1e45' to BIGNUMERIC, which exceeds its range (~5.79e38)
    and fails at run time. Every BIGNUMERIC literal must be inside the type's range."""
    sql = steps.load(name, "myproj.atlas", extra=EXTRA)
    for lit in re.findall(r"CAST\('([^']*)' AS BIGNUMERIC\)", sql):
        assert abs(Decimal(lit)) <= Decimal(K.BIGNUMERIC_MAX), (name, lit)


def test_amount_split_bounds_every_leg():
    """hi * SPLIT + lo reconstructs any in-range amount, and per-leg parts stay small
    enough that summing a billion legs cannot overflow BIGNUMERIC."""
    split, top = int(K.AMOUNT_SPLIT), int(Decimal(K.BIGNUMERIC_MAX))
    for v in (0, 1, split - 1, split, 10 ** 33 + 7, top):
        hi, lo = divmod(v, split)
        assert hi * split + lo == v and 0 <= lo < split
    assert (top // split) * 10 ** 9 < top and split * 10 ** 9 < top


def test_holdings_sum_is_overflow_safe():
    sql = steps.load("05_build_token_holdings.sql", "p.w")
    assert "SAFE_CAST(t.value AS BIGNUMERIC)" in sql and "SAFE_ADD(SAFE_MULTIPLY(" in sql
    assert "balance_overflow" in sql
    assert "amount_overflow" in steps.load("06_permit_token_exposure.sql", "p.w")
