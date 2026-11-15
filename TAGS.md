# Versions and release tags

[README](README.md) · [User instructions](INSTRUCTIONS.md) · [Release notes](docs/releases/v5.102.0.md)

🏷️ **Current release: [v5.102.0](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.102.0)**. Installation into a seat is a separate action.

| Tag | Commit identity | Downloads |
|---|---|---|
| [v5.102.0](https://github.com/JosephOIbrahim/Synapse/tree/v5.102.0) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.102.0/SYNAPSE-5.102.0-Setup.public-build.json); compare the tag target | [Minor release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.102.0) |
| [v5.101.1](https://github.com/JosephOIbrahim/Synapse/tree/v5.101.1) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.101.1/SYNAPSE-5.101.1-Setup.public-build.json); compare the tag target | [Unchanged release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.101.1) |
| [v5.101.0](https://github.com/JosephOIbrahim/Synapse/tree/v5.101.0) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.101.0/SYNAPSE-5.101.0-Setup.public-build.json); compare the tag target | [Unchanged release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.101.0) |
| [v5.100.0](https://github.com/JosephOIbrahim/Synapse/tree/v5.100.0) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.100.0/SYNAPSE-5.100.0-Setup.public-build.json); compare the tag target | [Unchanged release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.100.0) |
| [v5.99.0](https://github.com/JosephOIbrahim/Synapse/tree/v5.99.0) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.99.0/SYNAPSE-5.99.0-Setup.public-build.json); compare the tag target | [Unchanged release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.99.0) |
| [v5.98.0](https://github.com/JosephOIbrahim/Synapse/tree/v5.98.0) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.98.0/SYNAPSE-5.98.0-Setup.public-build.json); compare the tag target | [Unchanged release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.98.0) |
| [v5.97.7](https://github.com/JosephOIbrahim/Synapse/tree/v5.97.7) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.7/SYNAPSE-5.97.7-Setup.public-build.json); compare the tag target | [Unchanged release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.7) |
| [v5.97.6](https://github.com/JosephOIbrahim/Synapse/tree/v5.97.6) | Exact source revision in the [public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.6/SYNAPSE-5.97.6-Setup.public-build.json); compare the tag target | [Unchanged release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.6) |
| [v5.97.5](https://github.com/JosephOIbrahim/Synapse/tree/v5.97.5) | [`6a8d97b2d8052592c18e01bb68beb01e5f166e29`](https://github.com/JosephOIbrahim/Synapse/commit/6a8d97b2d8052592c18e01bb68beb01e5f166e29) | [Unchanged release and five assets](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.5) |
| [v5.97.4](https://github.com/JosephOIbrahim/Synapse/tree/v5.97.4) | [`20d742c5d036392f6938ab88b2d55e27462df55b`](https://github.com/JosephOIbrahim/Synapse/commit/20d742c5d036392f6938ab88b2d55e27462df55b) | [Previous release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.4) |

## Verify 5.102.0

- [SHA256SUMS.txt](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.102.0/SHA256SUMS.txt) binds downloadable assets.
- [Public build record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.102.0/SYNAPSE-5.102.0-Setup.public-build.json) records the exact source commit, toolchain, native input and Setup/payload hashes.
- [Installer verification](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.102.0/installer-verification.json) states final-byte qualification and remaining gaps. Its `ci` block names the CI run on the tagged commit, [Actions run 43774665860](https://github.com/JosephOIbrahim/Synapse/actions/runs/43774665860).
- Its native input is published beside the release as `moneta-native-0.1.0-win64-clean.zip`, so the native artifact can be checked against the pin rather than taken on trust.
- `git rev-parse 'v5.102.0^{commit}'` resolves the annotated tag to its source commit — `a6c3d4f9460a11ac9e1840e59f797e8328f2402d`, tag object `3e2486645d265312347808ce1af5a0c6ad408bf3`. Never substitute a later default-branch HEAD.

Setup remains **unsigned** because the inspected local signing setup has no configured publisher identity. Fresh supported-host native activation requires pinned artifacts plus actual execution; explicit OFF and legacy default-OFF remain OFF. Source-script installation has a separate policy.

## Preserved releases

The annotated v5.97.5 tag object is `d08b27d3eccfcb18e39479b144b386c964c4df6e`, targeting `6a8d97b2d8052592c18e01bb68beb01e5f166e29`. Its [six-job CI](https://github.com/JosephOIbrahim/Synapse/actions/runs/39439531389) and five assets remain unchanged. That Setup has no native wheel. The v5.97.6, v5.97.7, v5.98.0, v5.99.0, v5.100.0, v5.101.0 and v5.101.1 tags and their assets are likewise preserved by v5.102.0. Documentation commits after a tag do not replace the tagged code.
