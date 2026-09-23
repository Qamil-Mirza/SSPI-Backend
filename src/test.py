from sspi import SSPI

with SSPI() as sspi:
    result = sspi.run("BIODIV")

    df = sspi.query(
        indicators=["BIODIV"],
        countries=["MYS", "AUT"],
        years=(2018, 2023),
    )

    print(df.head(2))
