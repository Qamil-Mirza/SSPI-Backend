import matplotlib.pyplot as plt

from sspi import SSPI

sspi = SSPI()

df = sspi.query(datasets=["UNSDG_MARINE"], countries=["MYS"])

plt.plot(df["year"], df["value"])
plt.ylabel("Percent Protected Marine Area")
plt.xlabel("Year")
plt.title("Annual Percent Protected Marine Area in Malaysia")
plt.tight_layout()
plt.show()
