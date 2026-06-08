# Bundled fonts (v9 type pass)

Loaded into QFontDatabase at panel init by `../fontload.py`.

| File | Family | Weights | Source |
|---|---|---|---|
| `SpaceGrotesk-Variable.ttf` | Space Grotesk | variable 300–700 (uses 400/500/700) | github.com/floriankarsten/space-grotesk → google/fonts `ofl/spacegrotesk` |
| `SpaceMono-Regular.ttf` | Space Mono | 400 | google/fonts `ofl/spacemono` |
| `SpaceMono-Bold.ttf` | Space Mono | 700 | google/fonts `ofl/spacemono` |

Both families are licensed under the **SIL Open Font License 1.1** — see
`OFL-SpaceGrotesk.txt` and `OFL-SpaceMono.txt`. The OFL permits bundling and
redistribution with the license text included (done here).

If a family fails to register, `fontload.load_application_fonts()` raises the
build-mismatch flag and the panel falls back to the documented families in
`tokens.FONT_*_FALLBACKS`.
