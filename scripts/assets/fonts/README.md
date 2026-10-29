# Vendored fonts (local-only)

`Inter-VF.ttf` — Inter variable font (opsz and wght axes), version 4.001,
© 2016 The Inter Project Authors (https://github.com/rsms/inter), licensed
under the SIL Open Font License 1.1 (https://openfontlicense.org). File is
Google Fonts' `Inter-VariableFont_opsz,wght.ttf`
(https://github.com/google/fonts/tree/main/ofl/inter), renamed.

Used by `scripts/og.py` to set the share-card type. The deploy workflow
excludes `scripts/`, so the font is never served — it exists only so the
committed OG PNGs can be regenerated locally.
