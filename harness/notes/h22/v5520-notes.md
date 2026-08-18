## The day the weak domains became lookups

Two full waves authored, executed, adversarially reviewed, and merged - plus a
production-hardening program opened and its first audit landed. Suite on the
tagged head: **6,740 passed / 0 failed**.

### APEXFORGE - APEX stops being a memorization problem

- **Truth surface re-stamped for H22.0.400**: the callback registry enumerated live (2,286 callbacks), per-callback port signatures, `::version` parsing - replacing a symbol set last seeded against 21.0.671.
- **Wire-typing matrix**: 441-cell ordered type-pair matrix recording connect / coerce / reject, all 420 rejects carrying their exception text; plus a 68-row `@` vs `$` token-resolution table. The "exact wire-typing rules" weak area is now a lookup that regenerates per build.
- **Help-cache referee**: parsed node help cross-referenced against the live runtime - 55 rows, zero unclassified, two quarantine candidates raised with both doc and runtime anchors.
- **Phantom-name migration**: panel recipes moved off fictional node names, guarded by a catalog-membership test that fails loud rather than skipping when the catalog is absent.

### Substrate - the parm gate gets its authority

- **Per-build parameter-name catalog**, replacing doc-derived names with ground truth.
- **Parm gate proven in composition**: a phantom parameter name is rejected *before mutation* and answered with the real one (`code` -> suggests `kernelcode`).
- **Cook-verify measures**: a tier ladder that cannot promote without measurement - every unmeasured kind resolves to UNKNOWN rather than a default.

### BASTION - production hardening opens

Seven-blueprint program (lifecycle, truth, engine, memory, surface, shield, ship)
ratified, and its wave-0 audit executed by seven read-only scouts, a librarian
synthesizer, and a harness-v2 smith: **112 findings indexed - 3 P0, 58 P1, 51 P2**,
each with a file:line anchor and first-hand evidence or an explicit UNKNOWN.

### What the crucibles caught

Both waves passed through adversarial review that re-derived every claim from
committed evidence rather than trusting leg self-reports. The substrate crucible
found a defect no single leg could see - two environment variables read by the
catalog loader but absent from the deployment docs, failing conformance only in
the combined tree. Fixed before the merge, not after.

The librarian returned `blocked` rather than claim a commit it had been denied
permission to make. Honest-by-design is not only in the product.
