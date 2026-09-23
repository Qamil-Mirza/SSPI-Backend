from sspi.metadata import CountryCatalog

catalog = CountryCatalog.load()

print(f"SSPI67 Members: {catalog.group('SSPI67').members}")
print(f"Country: {catalog.country('AUT')}")
print(f"Group(s) For MYS: {catalog.groups_for('MYS')}")
