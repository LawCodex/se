# LawCodex — Sweden (Sverige)

Swedish statutes from the *Svensk författningssamling* (SFS) as Markdown: the consolidated
(in-force, amended) texts of the fundamental laws, the codes (*balkar*), the acts (*lagar*),
the government ordinances (*förordningar*) and the other SFS instruments still in force.
Original language: Swedish.

Part of [LawCodex](https://github.com/LawCodex) — the legislation of every country as plain
Markdown in git.

## Contents

Retrieved **2026-10-11**. 5,338 documents.

| Directory | What | Files |
|---|---|---:|
| `grundlagar/` | The four fundamental laws — regeringsformen (1974:152), successionsordningen (1810:0926), tryckfrihetsförordningen (1949:105), yttrandefrihetsgrundlagen (1991:1469) — plus riksdagsordningen (2014:801) | 5 |
| `balkar/` | The codes: rättegångsbalken, föräldrabalken, ärvdabalken, brottsbalken, jordabalken, utsökningsbalken, äktenskapsbalken, miljöbalken, socialförsäkringsbalken, and the surviving parts of the 1734 code (byggningabalken, handelsbalken) | 11 |
| `lagar/<year>/` | Acts: titles "Lag (…) om …" or "…lag (…)" (e.g. skollag, kommunallag, inkomstskattelag) | 1,750 |
| `forordningar/<year>/` | Ordinances: titles "Förordning (…)" or "…förordning (…)", incl. older "Kungl. Maj:ts förordning" | 3,043 |
| `ovriga/<year>/` | Other SFS instruments not flagged as repealed: kungörelser, tillkännagivanden, cirkulär, brev, stadgar, agency regulations published in SFS (Riksbankens föreskrifter, Försäkringskassans föreskrifter, SCB kungörelser…) | 529 |

Notes on the structure:

- Classification is by title, as the official SFS title says what kind of instrument it is.
  Riksdagsordningen is not formally a fundamental law but has a special status between
  grundlag and ordinary law; it is kept with the grundlagar. The regeringsform is officially
  titled "Kungörelse (1974:152) om beslutad ny regeringsform", which is kept as its title.
- File names: `<SFS number>-<slug of title>.md`, e.g. `lagar/2010/2010-800-skollag.md`,
  `balkar/1962-700-brottsbalk.md`. The year directory is the SFS year.
- Inside each file: avdelningar, kapitel and section headings (*rubriker*) become Markdown
  headings, each paragraph (§) is a heading at the deepest level (`1 §`, `2 a §`…), then its
  text. Transitional provisions (*Övergångsbestämmelser*) keep the SFS number of each amending
  act in bold. Amendment references (*Lag (2018:411).*) and the database markers for
  provisions that enter into force or expire later (*/Träder i kraft I:2027-01-01/*,
  */Upphör att gälla U:…/*) are kept in italics exactly as in the source — where a
  paragraph has a current and a future wording, both are present.
- Tabular text that the source renders as preformatted lines is kept in code blocks.
- Front matter: `title`, `identifier` (SFS number), `type` (constitution, code, act,
  regulation, notice, other), `date` (utfärdad), `amended_through` (last amending SFS
  incorporated, "t.o.m. SFS …"), `reprinted` (omtryck), `department`, `entry_into_force`
  (only for texts not yet in force), `expires` (if a whole-text expiry date is announced),
  `status`, `source` (Riksdagen document), `consolidated_text` (Regeringskansliet SFST link),
  `retrieved`. Notes from the source ("Rättelseblad … har iakttagits") are shown as a
  blockquote under the title.

## Not covered / gaps

- **Repealed statutes** — 5,906 SFS entries flagged "Författningen är upphävd" in the source
  are excluded. Historic versions of amended texts are not included (only the current
  consolidation).
- **Spent entries without text** — 184 entries that Riksdagen lists as not repealed but that
  carry no text at all (mostly amending/repealing ordinances of the "N" series, e.g.
  "Förordning (N2017:10) om upphävande av …", and a few amending acts) are skipped. Three
  entries without text but with an explanatory note (e.g. "Texten finns bara i den tryckta
  versionen") are kept with that note.
- **Non-SFS series** — 133 historic 19th-century Riksbank/Riksgäldskontor regulations
  (`regl-riksb`, `regl-riksg`, OCR text, not in force) and one `bevför` entry in the same
  database are excluded.
- **6 old documents** (1878–1901 "bih." items, e.g. "Skrivelsen (1878:bih. 56 s.1)") could
  not be downloaded: the Riksdagen API returns 404 for their identifiers.
- **Agency regulations** (myndighetsföreskrifter published in each agency's own
  författningssamling, e.g. FFFS, SKVFS) and EU law are not part of SFS and not included,
  except the few historically printed in SFS.
- **Case law, preparatory works** (propositioner, SOU) are out of scope.
- Signature blocks and the "Ändringsregister" (SFSR amendment register) are not reproduced.

## Sources

- **Riksdagen open data** (Sveriges riksdag), document type `sfs`:
  list API `https://data.riksdagen.se/dokumentlista/?doktyp=sfs&utformat=json` and documents
  `https://data.riksdagen.se/dokument/<dok_id>.json` (metadata, plain text and HTML).
  Riksdagen's SFS texts are the consolidated texts produced by Regeringskansliet
  (SFST, [rkrattsbaser.gov.se](https://rkrattsbaser.gov.se/)), which every file links to.
- The consolidated texts are **not the authentic version**: the legally binding text is the
  printed / electronically published SFS (svenskforfattningssamling.se). Expect the usual
  database caveats (typos, transitional quirks).

## Copyright / licence

Under 9 § of the Swedish Copyright Act (*upphovsrättslagen*, 1960:729), laws and other
regulations (författningar) are not protected by copyright. Riksdagen's open data is
provided free of charge for re-use. This repository's Markdown conversion is likewise
offered without restriction.

## Regenerate

```sh
python -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python scripts/fetch.py list     # page through the SFS listing (date ranges, ≤10,000 hits each)
.venv/bin/python scripts/fetch.py docs     # download every non-repealed document (4 workers, cached)
.venv/bin/python scripts/convert.py        # rebuild grundlagar/ balkar/ lagar/ forordningar/ ovriga/
```

Raw downloads are cached in `../_raw/se/` (≈ 270 MB, not committed; delete after use).
`fetch.py docs --refresh` re-downloads documents whose `systemdatum` has changed;
`--all` also downloads repealed entries. `convert.py` rewrites all Markdown files from the
cache, so removed statutes disappear on regeneration.
