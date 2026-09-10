# Windows installer design

SYNAPSE 5.67.4, based on d7c90a15. Scope: installation, upgrade, diagnosis and
uninstall. No release, artist-seat changes, or memory architecture changes.

## Decision

Use Inno Setup 7.1.0 with a bundled, isolated CPython 3.13.15 maintenance runtime
and a standard-library Python engine. Inno supplies the conventional wizard,
per-user application registration, shortcuts and uninstaller. A shared Python
module authors Houdini packages for both source-install scripts and Setup.
WiX/MSI adds significant tooling for this per-user package; a custom wizard would
require maintaining Windows installation conventions ourselves.

## Layout and lifecycle

Default application directory: `%LOCALAPPDATA%/Programs/SYNAPSE`.
Runtime files live in `versions/<version>-<payload digest>`; upgrades stage and
hash-check a new runtime before switching registrations. No dependency on a
source checkout survives packaging. A receipt records every installed file.
Only package JSON is needed in the Houdini preferences directory: Houdini's
package hpath supplies panel, shelves, callbacks, design helpers and icons.

An exclusive maintenance lock serializes writers. External registration changes
use a write-ahead recovery journal with before/after contents; interrupted
transactions are rolled back on the next maintenance action. Uninstall removes
only recorded, unchanged runtime files, preserving changed and unknown files. A maintenance-file hash manifest blocks Inno cleanup or replacement when a helper was edited. Previous
legacy registrations/UI files are backed up only with explicit migration consent
and restored when uninstalling. External/studio duplicate packages block setup
with their paths rather than changing studio configuration.

## Discovery and safety

Enumerate SideFX registry entries and Program Files installations, ask each
installation's hconfig for the preference path, and offer Windows Known Folder,
OneDrive and explicit custom paths. Display the detected build, preference path,
and its discovery source. Launcher-only environment overrides cannot be inferred;
the user can browse to the actual folder. Exact 22.0.400/Python 3.13 is the
validation target; other builds require an explicit compatibility acknowledgement.
Running Houdini processes block ordinary installation and uninstall. Never close
or terminate them. Tests use a separately identified installer with all paths
constrained to an isolated test root.

## Dependencies and build

Build a deterministic runtime ZIP from an explicit allowlist of tracked runtime
files. Exclude credentials, local configuration, caches, test outputs and developer
artifacts. Include vendored SDK license metadata and native Windows ABI files.
The builder takes an explicit, hash-verified Moneta dependency archive containing
src/moneta and the three codeless USD schema resources. It never discovers a
sibling checkout. A local dependency export records provenance and proprietary
status; public redistribution authorization is not implied. Core-only builds
explicitly use JSONL and identify Moneta as unavailable. OpenUSD/Qt are supplied
by Houdini. Missing required files/dependencies fail the build or setup.

## Verification

Before success: ZIP/path safety, manifest hashes, runtime dependency presence,
package structure/target paths, panel/shelf XML and icons, and registration readback.
Model credentials are not an installation requirement. Live package loading,
panel construction and USD schema registration are separate Houdini checks.
Test fresh/repeat/upgrade/uninstall, duplicate migration, changed-file and user-data
preservation, running-process refusal, missing dependency, unwritable target,
tampered payload and interrupted transaction recovery. Capture a native wizard
walkthrough in an isolated test environment where possible. Independent advisory
review is required by AGENTS.md; findings must be resolved or reported.

## Work plan

1. Shared registration/assets and runtime exporter.
2. Detection, transaction engine and meaningful failure/lifecycle tests.
3. Inno wizard, pinned tools and reproducible build.
4. Isolated executable lifecycle and Houdini runtime probes.
5. Independent review, documentation, receipt and local source commit.
