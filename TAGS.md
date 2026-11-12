# Versions and release tags

[README](README.md) · [User instructions](INSTRUCTIONS.md) · [Release notes](docs/releases/v5.100.0.md)

🏷️ **Current release: [v5.100.0](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.100.0)**. Installation into a seat is a separate action.

| Tag | Commit identity | Downloads |
|---|---|---|
| [v5.100.0](https://github.com/JosephOIbrahim/Synapse/tree/v5.100.0) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.100.0/SYNAPSE-5.100.0-Setup.public-build.json); compare the tag target | [Minor release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.100.0) |
| [v5.99.0](https://github.com/JosephOIbrahim/Synapse/tree/v5.99.0) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.99.0/SYNAPSE-5.99.0-Setup.public-build.json); compare the tag target | [Unchanged release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.99.0) |
| [v5.98.0](https://github.com/JosephOIbrahim/Synapse/tree/v5.98.0) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.98.0/SYNAPSE-5.98.0-Setup.public-build.json); compare the tag target | [Unchanged release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.98.0) |
| [v5.97.7](https://github.com/JosephOIbrahim/Synapse/tree/v5.97.7) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.7/SYNAPSE-5.97.7-Setup.public-build.json); compare the tag target | [Unchanged release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.7) |
| [v5.97.6](https://github.com/JosephOIbrahim/Synapse/tree/v5.97.6) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.6/SYNAPSE-5.97.6-Setup.public-build.json); compare the tag target | [Unchanged release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.6) |
| [v5.97.5](https://github.com/JosephOIbrahim/Synapse/tree/v5.97.5) | [`6a8d97b2d8052592c18e01bb68beb01e5f166e29`](https://github.com/JosephOIbrahim/Synapse/commit/6a8d97b2d8052592c18e01bb68beb01e5f166e29) | [Unchanged release and five assets](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.5) |
| [v5.97.4](https://github.com/JosephOIbrahim/Synapse/tree/v5.97.4) | [`20d742c5d036392f6938ab88b2d55e27462df55b`](https://github.com/JosephOIbrahim/Synapse/commit/20d742c5d036392f6938ab88b2d55e27462df55b) | [Previous release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.4) |

## Verify 5.100.0

- [SHA256SUMS.txt](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.100.0/SHA256SUMS.txt) binds downloadable assets.
- [Public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.100.0/SYNAPSE-5.100.0-Setup.public-build.json) records the exact source commit, toolchain, native input and Setup/payload hashes.
- [Installer verification](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.100.0/installer-verification.json) states final-byte qualification and remaining gaps. The release page links its exact-commit CI run.
- Its native input is published beside the release as `moneta-native-0.1.0-win64-clean.zip`, so the native artifact can be checked against the pin rather than taken on trust.
- `git rev-parse 'v5.100.0^{commit}'` resolves the annotated tag to its source commit — `7f8c5ec3cf6a794691d1df47b0b167f9147e7ac5`, tag object `345ab7cceb7637d7a91971f1c8a14bf72188e840`. Never substitute a later default-branch HEAD.

Setup remains **unsigned** because the inspected local signing setup has no configured publisher identity. Fresh supported-host native activation requires pinned artifacts plus actual execution; explicit OFF and legacy default-OFF remain OFF. Source-script installation has a separate policy.

## Preserved releases

The annotated v5.97.5 tag object is `d08b27d3eccfcb18e39479b144b386c964c4df6e`, targeting `6a8d97b2d8052592c18e01bb68beb01e5f166e29`. Its [six-job CI](https://github.com/JosephOIbrahim/Synapse/actions/runs/39439531389) and five assets remain unchanged. That Setup has no native wheel. The v5.97.6, v5.97.7, v5.98.0 and v5.99.0 tags and their assets are likewise preserved by v5.100.0. Documentation commits after a tag do not replace the tagged code.
