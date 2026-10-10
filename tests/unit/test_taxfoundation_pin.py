"""The Tax Foundation edition pin, checked against bytes rather than against
itself.

``tests/fixtures/taxfoundation/rates_final_2025-01.csv`` is the complete
approved file, January 2025 edition, byte for byte. Its identity is asserted
against records that do not come from the adapter's configuration:

* the size and SHA-256 written below, recorded when the file was
  established (2026-10-09);
* the Internet Archive's own content digest (base-32 SHA-1) for its captures
  of the legacy URL on 2025-01-17 and 2025-05-28, computed by a third party.

Only then is the adapter's pin (``FILES``), the canonical metadata note and
the fixture README compared with it; and the 21-row parity fixture is
checked to be a verbatim excerpt of this file. Changing the expected digest
and a fixture together therefore cannot pass unnoticed: the bytes, the size,
the archive digest and the excerpt check would all have to move with it.
No network.
"""

import base64
import hashlib
from pathlib import Path

import httpx
import pytest

from sspi.errors import SourceResponseError
from sspi.ingestion import TaxFoundationClient, normalize_taxfoundation_dataset
from sspi.ingestion.taxfoundation import FILES
from sspi.metadata import MetadataCatalog

DIRECTORY = Path(__file__).parents[1] / "fixtures" / "taxfoundation"
FULL = DIRECTORY / "rates_final_2025-01.csv"
EXCERPT = DIRECTORY / "rates_final_2025-01_sample.csv"
KEY = "rates_final_2025-01"
URL = "https://taxfoundation.org/wp-content/uploads/2025/01/rates_final.csv"  # the legacy collector's literal

# Recorded when the edition was established, independently of FILES.
EXPECTED_SIZE = 45_749
EXPECTED_SHA256 = "7dd8f506e2942c816e28f01c7c478402fb39d3c263cf6c38b32f04df3fab9f52"
# Internet Archive CDX digest of https://taxfoundation.org/wp-content/uploads/2025/01/rates_final.csv,
# captures 20250117164233 and 20250528003704 (base-32 SHA-1 of the archived body).
WAYBACK_SHA1_BASE32 = "JLDGQRPGPDEK5HNORPE6WZFNLNU74XJK"


def full_bytes() -> bytes:
    return FULL.read_bytes()


def test_the_committed_file_is_the_archived_2025_01_edition():
    content = full_bytes()
    assert len(content) == EXPECTED_SIZE
    assert hashlib.sha256(content).hexdigest() == EXPECTED_SHA256
    assert base64.b32encode(hashlib.sha1(content).digest()).decode() == WAYBACK_SHA1_BASE32  # third-party record of the same bytes


def test_the_adapter_pin_metadata_and_readme_all_name_that_file():
    assert FILES[KEY].sha256 == EXPECTED_SHA256 and FILES[KEY].url == URL and FILES[KEY].edition == "2025/01"
    note = MetadataCatalog.load().dataset("TF_CRPTAX").source.note
    assert EXPECTED_SHA256 in note and URL in note
    readme = (DIRECTORY / "README.md").read_text(encoding="utf-8")
    assert EXPECTED_SHA256 in readme and URL in readme and "2025/01" in readme and WAYBACK_SHA1_BASE32 in readme and f"{EXPECTED_SIZE:,} bytes" in readme


def test_the_readme_keeps_attribution_and_licence():
    readme = (DIRECTORY / "README.md").read_text(encoding="utf-8")
    assert "Tax Foundation" in readme and "https://taxfoundation.org/data/all/global/corporate-tax-rates-by-country-2024/" in readme
    assert "CC BY-NC 4.0" in readme and "https://creativecommons.org/licenses/by-nc/4.0/" in readme
    assert "unless the publisher specifies otherwise" in readme and "may require permission" in readme


def test_the_parity_fixture_is_a_verbatim_excerpt_of_the_pinned_file():
    full = full_bytes().split(b"\r\n")
    excerpt = EXCERPT.read_bytes().split(b"\r\n")
    assert full[-1] == excerpt[-1] == b""  # both end with CRLF
    assert excerpt[0] == full[0]  # same header
    positions = [full.index(line) for line in excerpt[1:-1]]  # raises if a line is not in the file
    assert len(positions) == 21 and positions == sorted(set(positions))  # distinct rows, in file order


class Server:
    def __init__(self, content):
        self.content, self.requests = content, []

    def __call__(self, request):
        self.requests.append(str(request.url))
        return httpx.Response(200, content=self.content, headers={"content-type": "text/csv"})


def fetch(content):
    server = Server(content)
    with TaxFoundationClient(http=httpx.Client(transport=httpx.MockTransport(server))) as client:  # default configuration
        return client.fetch_file(KEY), server.requests


def test_the_default_configuration_accepts_exactly_these_bytes():
    file, requests = fetch(full_bytes())
    assert requests == [URL] and file.sha256 == EXPECTED_SHA256 and file.source.edition == "2025/01"


@pytest.mark.parametrize("change", ["one byte", "line endings", "trailing newline"])
def test_the_default_configuration_refuses_any_other_bytes(change):
    content = full_bytes()
    altered = {
        "one byte": content.replace(b"25.83858", b"25.83859", 1),
        "line endings": content.replace(b"\r\n", b"\n"),
        "trailing newline": content.rstrip(b"\r\n"),
    }[change]
    assert altered != content
    with pytest.raises(SourceResponseError, match="no other edition is substituted"):
        fetch(altered)


def test_the_whole_pinned_file_normalizes_as_the_legacy_cleaner_did_and_contains_the_excerpt():
    """Whole-file figures checked against the legacy cleaner on 2026-10-09 (7,205 identical rows); the excerpt's
    observations are exactly the full file's observations for the excerpt's areas."""
    dataset = MetadataCatalog.load().dataset("TF_CRPTAX")
    full, _ = fetch(full_bytes())
    whole = normalize_taxfoundation_dataset(dataset, full)
    assert (len(whole.observations), whole.missing_values, len({o.country_code for o in whole.observations})) == (7205, 4090, 226)
    assert (min(o.year for o in whole.observations), max(o.year for o in whole.observations)) == (1980, 2024)
    assert sum(1 for o in whole.observations if o.value == 0) == 536 and whole.skipped_areas == ()

    excerpt_bytes = EXCERPT.read_bytes()
    excerpt_file = type(full)(KEY, full.source, hashlib.sha256(excerpt_bytes).hexdigest(), excerpt_bytes.decode("utf-8"))
    part = normalize_taxfoundation_dataset(dataset, excerpt_file)
    areas = {o.country_code for o in part.observations}

    def rows(observations):
        return [(o.country_code, o.year, o.value, o.unit, o.provenance["source_value"]) for o in observations]

    assert rows(part.observations) == rows(o for o in whole.observations if o.country_code in areas)
