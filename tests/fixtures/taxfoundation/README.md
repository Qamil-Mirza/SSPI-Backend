# Tax Foundation source fixtures

## Source, attribution and licence

Source: Tax Foundation, "Corporate Tax Rates Around the World, 2024", by
Cristina Enache, published 17 December 2024,
<https://taxfoundation.org/data/all/global/corporate-tax-rates-by-country-2024/>.
The data file is the one that page links as its historical data:

| | |
|---|---|
| File | `rates_final.csv` (worldwide statutory corporate income tax rates, 1980-2024) |
| URL | <https://taxfoundation.org/wp-content/uploads/2025/01/rates_final.csv> |
| Edition | 2025/01 (the January 2025 upload; the edition the legacy SSPI collector read) |
| Size | 45,749 bytes, 251 rows, CRLF line endings |
| SHA-256 | `7dd8f506e2942c816e28f01c7c478402fb39d3c263cf6c38b32f04df3fab9f52` |
| Internet Archive digest (SHA-1, base 32) | `JLDGQRPGPDEK5HNORPE6WZFNLNU74XJK`, captures of 2025-01-17 and 2025-05-28 |
| Downloaded | 2026-10-09 |

Licence: Creative Commons Attribution-NonCommercial 4.0 International
(CC BY-NC 4.0), <https://creativecommons.org/licenses/by-nc/4.0/>. The
licence applies unless the publisher specifies otherwise.

Basis, as checked on 2026-10-09:

- The Tax Foundation's copyright notice,
  <https://taxfoundation.org/copyright-notice/>, states that work by the Tax
  Foundation, unless otherwise noted, is licensed under CC BY-NC 4.0, and
  that materials may be reproduced and distributed for non-commercial
  purposes with clear attribution to the Tax Foundation and, where
  applicable, a URL to the relevant Tax Foundation page.
- Neither the CSV file, nor the publication page that links it, nor the
  publisher's GitHub repository for this data set
  (<https://github.com/TaxFoundation/worldwide-corporate-tax-rates>, no
  licence file) carries a different licensing notice. The site-wide notice
  is therefore the one that applies.

Commercial use or commercial redistribution of these files, or of data
derived from them, may require permission from the Tax Foundation. Its
copyright notice directs those seeking permission for commercial purposes to
contact it through that page. The files are kept here unmodified (the
excerpt below only omits rows), for non-commercial research and testing.

## Files

`rates_final_2025-01.csv` is the complete file above, byte for byte. It
exists so the edition pin is tested against bytes:
`tests/unit/test_taxfoundation_pin.py` checks its size and SHA-256 against
values recorded in that test and its SHA-1 against the Internet Archive's
own digest, before comparing the adapter's pin, the canonical metadata note
and this README with it. It also checks that the parity excerpt below is a
verbatim excerpt of it.

`rates_final_2025-01_sample.csv` is a verbatim excerpt of the same file: the
header and 21 rows, byte for byte, in file order, with the file's CRLF line
endings. The rows are MYS, AUT, USA, DEU, CAN, CHE, JPN, ARE, BHR, JEY, NIU,
COM, XKX, ZAF, KWT, ANT, NAM, IRN, SAU, SGP and PRK; why each is there is
listed in `docs/indicator-migration.md` (Tax fixtures). It is the parity
fixture for `TF_CRPTAX` and `CRPTAX`. See `tests/golden/generate_tax_cases.py`
(section `crptax`).

`.gitattributes` marks both CSV files `-text`, so git never rewrites their
line endings.
