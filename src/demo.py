import sys

import pandas as pd

from sspi import SSPI
from sspi.errors import ImputationError

pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 12)
pd.set_option("display.float_format", "{:.4f}".format)

REFRESH_SOURCES = "--refresh" in sys.argv
LAND_INDICATORS = ["NITROG", "DEFRST", "CARBON"]
FAO_DATASETS = ["UNFAO_FRSTLV", "UNFAO_FRSTAV", "UNFAO_CRBNLV", "UNFAO_CRBNAV"]
FOCUS = ["MYS", "SGP", "CHE", "AUT", "USA", "BRA", "IDN", "KEN"]


def banner(title):
    print(f"\n{'=' * 100}\n{title}\n{'=' * 100}")


sspi = SSPI()
names = {c.code: c.name for c in sspi.countries.countries()}
sspi49 = list(sspi.country_group("SSPI49").members)

# --------------------
# 0. WHAT AM I LOOKING AT  (metadata, no database needed)
# --------------------
banner("0. METADATA")
for code in LAND_INDICATORS:
    ind = sspi.indicator(code)
    print(
        f"{code} ({ind.name}, {ind.pillar_code}/{ind.category_code}): datasets {list(ind.dataset_codes)}, goalposts ({ind.lower_goalpost}, {ind.upper_goalpost})"
    )
print("executable today:", sspi.executable_indicators())
print(f"SSPI49 has {len(sspi49)} members; MYS belongs to {sspi.country('MYS').groups}")

# --------------------
# 1. INGEST  (source -> canonical observations in PostgreSQL)
# --------------------
banner("1. INGEST")
if REFRESH_SOURCES:
    epi = sspi.ingest("EPI_NITROG")  # Yale EPI 2026 archive
    fao = sspi.ingest(
        FAO_DATASETS
    )  # one FAOSTAT bulk download shared by all four; FRSTAV/CRBNAV are 1990s means derived from the levels
    for run in (epi, fao):
        print(f"fetched {list(run.source_fetches)} -> {run.counts}")
        for d in run.per_dataset:
            print(
                f"  {d.dataset_code:<13} {d.observations_written:>5} rows   {len(d.skipped_areas):>3} unmapped areas skipped   {d.missing_values} empty values dropped"
            )
else:
    print(
        "using stored observations (pass --refresh to re-download the EPI and FAOSTAT sources)"
    )

stored = pd.concat(
    [sspi.query(datasets=["EPI_NITROG"]), sspi.query(datasets=FAO_DATASETS)]
)
print(
    stored.groupby("dataset_code").agg(
        rows=("value", "size"),
        countries=("country_code", "nunique"),
        first=("year", "min"),
        last=("year", "max"),
        unit=("unit", "first"),
    )
)

# Where did a value come from? Provenance travels with every row.
row = sspi.query(
    datasets=["UNFAO_FRSTAV"],
    countries=["MYS"],
    years=(2022, 2022),
    include_provenance=True,
)
print(
    "\nUNFAO_FRSTAV MYS 2022:",
    row.value[0],
    row.unit[0],
    {k: row.provenance[0][k] for k in ("derived_from", "derivation", "baseline_years")},
)

# --------------------
# 2. RUN  (observations -> indicator scores, imputation included, persisted)
# --------------------
banner("2. RUN")
for code in LAND_INDICATORS:
    try:
        run = sspi.run(code)
        print(
            f"{code}: {run.written} scores written ({len(run.observed_scores)} observed, {len(run.imputed_scores)} imputed, {len(run.unscored)} country-years unscored)"
        )
    except ImputationError as error:
        # A legacy imputation rule that no longer fits the source data stops the run and writes nothing; the message names the
        # entry in docs/methodology-conflicts.md.
        print(
            f"{code}: STOPPED, nothing written (pending methodology decision)\n    {error}"
        )

# --------------------
# 3. QUERY  (read-only, tidy DataFrames)
# --------------------
banner("3. QUERY")
print(
    sspi.query(
        indicators=["NITROG"], countries=["MYS", "SGP", "CHE"], years=(2021, 2023)
    )
)

print("\nThe inputs behind a score:")
print(
    sspi.query(
        indicators=["NITROG"],
        countries=["MYS"],
        years=(2023, 2023),
        include_inputs=True,
    ).inputs[0]
)

print("\nIndicators with no persisted scores come back empty, not as an error:")
print(f"  BIODIV -> {len(sspi.query(indicators=['BIODIV']))} rows (not run in this demo)")

# --------------------
# 4. ANALYSE  (pandas on the frames)
# --------------------
nitrog = sspi.query(indicators=["NITROG"])
nitrog["country"] = nitrog.country_code.map(names)

banner("4a. NITROG 2023 league table, SSPI49 countries")
latest = (
    nitrog[(nitrog.year == 2023) & nitrog.country_code.isin(sspi49)]
    .sort_values("score", ascending=False)
    .reset_index(drop=True)
)
latest.index += 1
print(latest[["country_code", "country", "score"]].head(8).to_string())
print("...")
print(latest[["country_code", "country", "score"]].tail(5).to_string())

banner("4b. Biggest NITROG movers 2000 -> 2023 (all countries)")
wide = nitrog.pivot(index="country_code", columns="year", values="score")
movers = pd.DataFrame(
    {
        "country": wide.index.map(names),
        "score_2000": wide[2000],
        "score_2023": wide[2023],
    }
).dropna()
movers["change"] = movers.score_2023 - movers.score_2000
print("improved most:\n" + movers.nlargest(5, "change").to_string())
print("\ndeclined most:\n" + movers.nsmallest(5, "change").to_string())

banner("4c. NITROG trend: SSPI49 vs everyone else (mean score by year)")
nitrog["group"] = nitrog.country_code.isin(sspi49).map({True: "SSPI49", False: "other"})
trend = nitrog[nitrog.year >= 2000].groupby(["year", "group"]).score.mean().unstack()
print(trend.loc[[2000, 2005, 2010, 2015, 2020, 2023]].to_string())

banner(
    "4d. Forest and carbon stock in 2022 versus the 1990s baseline (source data, not SSPI scores)"
)
fao = stored[stored.dataset_code.isin(FAO_DATASETS)].pivot(
    index=["country_code", "year"], columns="dataset_code", values="value"
)
change = fao.loc[(slice(None), 2022), :].droplevel("year")
change = pd.DataFrame(
    {
        "country": change.index.map(names),
        "forest_1000ha_2022": change.UNFAO_FRSTLV,
        "forest_vs_1990s_pct": (change.UNFAO_FRSTLV - change.UNFAO_FRSTAV)
        / change.UNFAO_FRSTAV
        * 100,
        "carbon_vs_1990s_pct": (change.UNFAO_CRBNLV - change.UNFAO_CRBNAV)
        / change.UNFAO_CRBNAV
        * 100,
    }
).dropna()
print(
    "largest net forest loss:\n"
    + change.nsmallest(6, "forest_vs_1990s_pct").to_string()
)
print(
    "\nlargest net forest gain:\n"
    + change.nlargest(6, "forest_vs_1990s_pct").to_string()
)
print("\nfocus countries:\n" + change[change.index.isin(FOCUS)].to_string())

banner(
    "4e. Cross-pillar: does nitrogen management track water management? (2023 scores)"
)
watman = sspi.query(indicators=["WATMAN"], years=(2023, 2023)).set_index("country_code")
both = pd.concat(
    [
        nitrog[nitrog.year == 2023].set_index("country_code").score.rename("NITROG"),
        watman.score.rename("WATMAN"),
        watman.imputed.rename("WATMAN_imputed"),
    ],
    axis=1,
).dropna()
print(
    f"{len(both)} countries with both scores; Pearson r = {both.NITROG.corr(both.WATMAN):.3f}; {int(both.WATMAN_imputed.sum())} WATMAN scores are imputed"
)
both["country"] = both.index.map(names)
print(both[both.index.isin(FOCUS)].to_string())

banner("4f. Export for a notebook or a colleague")
out = nitrog.drop(columns="group").to_csv(index=False)
print(
    f"nitrog.to_csv(...) -> {len(nitrog)} rows, {len(out)} bytes; columns {list(nitrog.columns)}"
)

sspi.close()
