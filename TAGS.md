# Versions and release tags

[README](README.md) · [User instructions](INSTRUCTIONS.md) · [Release notes](docs/releases/v5.97.6.md)

🏷️ **Current release: [v5.97.6](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.6)**. Installation into a seat is a separate action.

| Tag | Commit identity | Downloads |
|---|---|---|
| [v5.97.6](https://github.com/JosephOIbrahim/Synapse/tree/v5.97.6) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.6/SYNAPSE-5.97.6-Setup.public-build.json); compare the tag target | [Patch release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.6) |
| [v5.97.5](https://github.com/JosephOIbrahim/Synapse/tree/v5.97.5) | [`6a8d97b2d8052592c18e01bb68beb01e5f166e29`](https://github.com/JosephOIbrahim/Synapse/commit/6a8d97b2d8052592c18e01bb68beb01e5f166e29) | [Unchanged release and five assets](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.5) |
| [v5.97.4](https://github.com/JosephOIbrahim/Synapse/tree/v5.97.4) | [`20d742c5d036392f6938ab88b2d55e27462df55b`](https://github.com/JosephOIbrahim/Synapse/commit/20d742c5d036392f6938ab88b2d55e27462df55b) | [Previous release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.4) |

## Verify 5.97.6

- [SHA256SUMS.txt](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.6/SHA256SUMS.txt) binds downloadable assets.
- [Public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.6/SYNAPSE-5.97.6-Setup.public-build.json) records the exact source commit, toolchain, native input and Setup/payload hashes.
- [Installer verification](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.6/installer-verification.json) states final-byte qualification and remaining gaps. The release page links its exact-commit CI run.
- `git rev-parse 'v5.97.6^{commit}'` resolves the annotated tag to its source commit. Never substitute a later default-branch HEAD.

Setup remains **unsigned** because the inspected local signing setup has no configured publisher identity. Fresh supported-host native activation requires pinned artifacts plus actual execution; explicit OFF and legacy default-OFF remain OFF. Source-script installation has a separate policy.

## Preserved releases

The annotated v5.97.5 tag object is `d08b27d3eccfcb18e39479b144b386c964c4df6e`, targeting `6a8d97b2d8052592c18e01bb68beb01e5f166e29`. Its [six-job CI](https://github.com/JosephOIbrahim/Synapse/actions/runs/39439531389) and five assets remain unchanged. That Setup has no native wheel. Documentation commits after a tag do not replace the tagged code.
