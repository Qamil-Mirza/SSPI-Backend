from sspi import SSPI

sspi = SSPI()

# --------------------
# ANALYZE
# --------------------

scores = sspi.query(
    indicators=["WATMAN"],
    countries=["SGP", "CHE"],
    years=(2000, 2023),
)

print(scores)
