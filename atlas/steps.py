"""The pipeline: which SQL file runs, in what order, and where its output goes."""
from dataclasses import dataclass
from pathlib import Path

from .constants import DEFAULT_SRC, sql_params

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


@dataclass(frozen=True)
class Step:
    key: str
    file: str
    kind: str            # "build" writes a work table; "query" returns rows to a CSV
    output: str | None   # CSV name for "query" steps
    needs: tuple = ()    # work tables that must exist before a dry run can price this step
    optional: bool = False
    title: str = ""


STEPS = [
    Step("01", "01_build_accounts.sql", "build", None, (), False,
         "Accounts: balances, sent-tx flag, contract flag"),
    Step("02", "02_exposed_eth_summary.sql", "query", "02_exposed_eth_summary.csv", ("accounts",), False,
         "Headline exposed-ETH numbers"),
    Step("03", "03_exposure_distribution.sql", "query", "03_exposure_distribution.csv", ("accounts",), False,
         "Exposed ETH by balance size and last activity"),
    Step("04", "04_build_token_candidates.sql", "build", None, (), False,
         "Permit tokens and proxy candidates"),
    Step("05", "05_build_token_holdings.sql", "build", None, ("accounts", "token_candidates"), False,
         "Token balances of EOA holders"),
    Step("06", "06_permit_token_exposure.sql", "query", "06_permit_token_exposure.csv",
         ("token_holdings", "token_candidates"), False, "Per-token exposed holdings"),
    Step("07", "07_build_permit2_approvals.sql", "build", None, ("accounts",), True,
         "Live Permit2 approvals (large logs scan)"),
    Step("08", "08_permit2_summary.sql", "query", "08_permit2_summary.csv", ("permit2_approvals",), True,
         "Permit2 summary"),
]


def render(sql: str, work: str, src: str = DEFAULT_SRC, extra: dict | None = None) -> str:
    """Fill {{src}}, {{work}} and every constant. Raises if a placeholder is left over."""
    values = {"src": src, "work": work, **sql_params(), **(extra or {})}
    for name, value in values.items():
        sql = sql.replace("{{" + name + "}}", str(value))
    if "{{" in sql:
        start = sql.index("{{")
        raise ValueError(f"unfilled placeholder near: {sql[start:start + 40]!r}")
    return sql


def load(step_or_file, work: str, src: str = DEFAULT_SRC, extra: dict | None = None) -> str:
    name = step_or_file.file if isinstance(step_or_file, Step) else step_or_file
    return render((SQL_DIR / name).read_text(), work, src, extra)


def select(keys: list[str] | None, include_optional: bool) -> list[Step]:
    if keys:
        wanted = {k.zfill(2) for k in keys}
        return [s for s in STEPS if s.key in wanted]
    return [s for s in STEPS if include_optional or not s.optional]
