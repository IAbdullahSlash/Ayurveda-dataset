[Your name]
[Designation, Department, Institution]
[Postal address] · [E-mail] · [Phone]
[Date]

To
The NAMASTE Portal Team / Joint Secretary (eHealth),
Ministry of Ayush, Government of India, Ayush Bhawan, B-Block, GPO Complex, INA, New Delhi - 110023

**Subject: Request for licence clarification of NAMASTE morbidity codes and Standardised Ayurveda Terminologies, and report of data issues**

Respected Sir/Madam,

I am building **AyurKB**, a non-commercial, bilingual (English-Hindi) research knowledge base for Ayurveda
decision support. The National AYUSH Morbidity and Standardised Terminologies Electronic portal (NAMASTE) is its
backbone: AyurKB uses the 2,910 Ayurveda morbidity codes (with ICD-11 TM2 links) and 12,080 SAT terms downloaded from
https://namaste.ayush.gov.in, always with attribution to the Ministry of Ayush.

**1. Licence.** The portal does not state terms of reuse. We respectfully request written confirmation that the
morbidity codes and SAT tables may be redistributed in derived form (normalised, transliterated, cross-linked) for
non-commercial research and education, with attribution - ideally under an open licence such as CC BY 4.0 or the
Government Open Data License - India (GODL).

**2. Data issues found (offered as feedback).** While processing the downloads we found:
- in the morbidity file, the official IAST column is empty for 14.1% of rows, and in a number of rows the diacritic and
  Devanagari columns appear shifted relative to the code (we re-derived these from the phonetic column, matching the
  official forms in 97% of aligned rows);
- in the SAT files, 2,251 tokens have diacritics replaced by "?" characters (e.g. encoding loss during export);
  we repaired 90% automatically, but 221 tokens remain unresolved and 146 rows are flagged;
- 16 rows name a parent code that has no row of its own (e.g. the top-level code "E", parent of the srotovikāra
  groups EA-EP), and one row has no NAMC code at all, which breaks the hierarchy for those entries.
We can share the full list of affected codes and our proposed corrections if useful.

**3. Machine-readable source.** If a UTF-8 CSV/JSON export or an API with the corrected columns is available (or
planned), we would be very grateful for access.

Thank you for this valuable national resource. We would be glad to share AyurKB with the Ministry before release.

Yours faithfully,

[Signature]
[Your name]
