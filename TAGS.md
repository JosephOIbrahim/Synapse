# Versions and release tags

[README](README.md) · [User instructions](INSTRUCTIONS.md) · [Release notes](docs/releases/v5.97.5.md)

📦 **Current published release: [v5.97.5](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.5)**, published 20 October 2026. These are published identities, not an instruction to change your installed version.

| Tag | Exact release commit | Downloads |
|---|---|---|
| [v5.97.5](https://github.com/JosephOIbrahim/Synapse/tree/v5.97.5) | [`6a8d97b2d8052592c18e01bb68beb01e5f166e29`](https://github.com/JosephOIbrahim/Synapse/commit/6a8d97b2d8052592c18e01bb68beb01e5f166e29) | [Release and five assets](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.5) |
| [v5.97.4](https://github.com/JosephOIbrahim/Synapse/tree/v5.97.4) | [`20d742c5d036392f6938ab88b2d55e27462df55b`](https://github.com/JosephOIbrahim/Synapse/commit/20d742c5d036392f6938ab88b2d55e27462df55b) | [Previous release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.4) |

The annotated v5.97.5 tag object is `d08b27d3eccfcb18e39479b144b386c964c4df6e`; its commit is the one above. Existing tag targets and release assets are preserved.

## Verify 5.97.5

- [Exact-commit CI](https://github.com/JosephOIbrahim/Synapse/actions/runs/39439531389): six jobs passed, covering Linux, macOS and Windows with Python 3.11 and 3.14.
- [SHA256SUMS.txt](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.5/SHA256SUMS.txt) binds the source ZIP, Setup and public verification reports.
- [Installer verification](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.5/installer-verification.json) records actual final-EXE extraction and isolated embedded-engine/runtime checks.

The published Setup is **unsigned** and contains **no native Rust wheel**. Interactive wizard, registry/shortcut and clean-machine qualification remain separate. Local Rust-ON qualification does not change the public installer default.

## Documentation and future changes

The default branch can contain documentation corrections after a release. Use the tag or release source ZIP to identify the published code. A proposed installer correction is unreleased and will require a separate reviewed successor; it does not replace the 5.97.5 tag or assets.
