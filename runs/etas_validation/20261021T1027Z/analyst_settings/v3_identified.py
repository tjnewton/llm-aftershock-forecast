"""V3 emulation of the Venezuela and Colombia versions with the identified analyst settings."""

import tomllib
from pathlib import Path

from laf import etas_validate as ev
from laf.etas import analyst_kwargs
from laf.oaf import parse_forecast

D = Path("data")
S = "20261021T1027Z"
RULES = tomllib.loads(Path("config/analyst_settings.toml").read_text())["rule"]
LEVELS = parse_forecast(
    Path("tests/golden/oaf_us6000u18k_1791593712688.json").read_bytes()
).fractileProbabilities

if __name__ == "__main__":
    for seq, name in (("us6000t7zp", "venezuela"), ("us6000tjl2", "colombia")):
        versions, bins = ev.run(D, S, only=[seq], settings=lambda s, d: analyst_kwargs(RULES, s, d))
        cmp = ev.compare(bins, LEVELS)
        cmp.to_parquet(Path(__file__).parent / f"v3_{name}_identified.parquet", index=False)
        s5, s6 = cmp[cmp.mag == 5], cmp[cmp.mag == 6]
        print(
            name,
            "all-M p90",
            round(cmp.d_official.quantile(0.9), 3),
            "M>=5 p90",
            round(s5.d_official.quantile(0.9), 3),
            "null",
            round(s5.d_null.quantile(0.9), 3),
            "dP(M>=5) p90",
            round((s5.p_ours - s5.p_official).abs().quantile(0.9), 3),
            "dP(M>=6) p90",
            round((s6.p_ours - s6.p_official).abs().quantile(0.9), 3),
        )
