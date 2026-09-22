from sspi.ingestion import UNSDGClient, normalize_unsdg_dataset
from sspi.metadata import MetadataCatalog

catalog = MetadataCatalog.load()
dataset = catalog.dataset("UNSDG_MARINE")

client = UNSDGClient()
rows = client.fetch_indicator(dataset.source.query_code)

result = normalize_unsdg_dataset(dataset, rows)
print(result.observations[25:31])
