# v5.69.0 Preview — The stop controls actually stop

**Channel: Preview.** `v5.68.0` stays Latest because it is the newest tag with a
Windows Setup behind it. This tag has no installer: the reproducible build needs
Inno Setup 7.1.0 and a Moneta bundle, neither available when it was cut.

Nothing about the code is provisional — the suite is green and the fixes are
measured. What is provisional is the *distribution*: an artist on Setup is on
5.68.0 until a 5.69.0 installer is built and published.

## What it carries

- The emergency halt fires when another panel tool is already running. Measured
  on two trees: `calls_started` delta `0 -> 1`, dispatched `False -> True`.
- A refused panel request says so instead of returning in silence.
- A REVIEW consent card no longer files a rejection that never happened.
- The system-prompt fallback announces itself; journal entries carry a date;
  `log_decision` stops discarding out-of-schema keys quietly.

Full detail, scope and limits: [docs/releases/v5.69.0.md](../../docs/releases/v5.69.0.md).

## To promote this to Latest

1. Build `SYNAPSE-5.69.0-Setup.exe` with Inno Setup 7.1.0 and the Moneta bundle
   (`installer/README.md` has the invocation).
2. Publish the GitHub release for `v5.69.0` with the Setup and `SHA256SUMS.txt`.
3. Flip the README banner to `tags: v5.69.0 is Latest`, restore the download
   button and checksum link to 5.69.0, and delete the Preview note under them.

Until step 2 lands, the README's download button deliberately still serves the
5.68.0 Setup, because it exists and works.
