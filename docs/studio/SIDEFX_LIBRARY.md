# SideFX help library

SYNAPSE Scout can search an externally built SideFX help library alongside its
existing node, VEX and reference sources. Configure the library once; queries
read a bounded shortlist from SQLite FTS5. They do not download documentation,
parse every page, construct an index, or call a model.

## Build and connect

From the SYNAPSE checkout, using Python with SQLite FTS5:

```powershell
python scripts/update_sidefx_library.py --root 'G:/HOUDINI22/_CORPUS' --hfs 'C:/Program Files/Side Effects Software/Houdini 22.0.400' --workers 8 --connect
```

This inventories every installed ZIP and loose `.txt` help page, preserves the
original bytes, downloads the public Markdown graph reachable from the official
`https://www.sidefx.com/docs/houdini/llms.txt`, builds a disk search index, and
writes the checkout's ignored `.synapse/sidefx_library.json` configuration.
`SYNAPSE_SIDEFX_CORPUS_ROOT` can override that configured location.

Re-run the same command to resume with SHA256-checked cached pages. Add
`--refresh` to conditionally revalidate the online graph with HTTP validators.
Unchanged installed snapshots and search generations are reused. Updates run
on demand; this does not install a scheduled job.

Web fetch errors stop the default update with exit 2 and preserve the active search
generation. Inspect `web_manifest.json`. `--allow-incomplete-web` deliberately
publishes available pages with visible gap counts; it never labels a partial
download complete. `--installed-only` explicitly builds the installed source
without network access. Run ingestion in a separate Python process, never on
Houdini's GUI thread.

## Stored material and coverage

- `llms.txt`: the exact official navigation index.
- `cache/installed/`: content-addressed original installed help text.
- `installed_manifest.json`: logical paths, hashes, origin, installed build and
  any loose-page overrides.
- `cache/web/` and `web_manifest.json`: original HTTP Markdown, hashes, checked
  URLs, validators, discovered pages, pending work, failures and traversal status.
- `indexes/<generation>.sqlite3`: immutable chunks, metadata and FTS5 index.
- `current.json`: atomic active-generation pointer.
- `coverage.json`: counts of cached, indexed, empty and federated pages.

"Complete installed snapshot" means every help `.txt` in the chosen installation
was accounted for, including root pages and licenses. "Web closure" means all
links discovered from the index were traversed, not that undiscoverable/unlinked
website pages were proven absent. `fetch_complete` additionally requires no
failed discovered pages. These are distinct, recorded measurements.

All documentation bytes stay local. They are not added to Git or release assets.
Old generations remain available for rollback; automatic cleanup does not race
active readers. To roll back, republish a validated prior pointer while keeping
its database and source cache intact.

## Evidence and retrieval boundaries

Installed build identity comes from the installation's `SYS_Version.h`.
Installed wiki is converted for search, with raw files and unexpanded directives
preserved. It is labeled `sidefx_wiki_unexpanded`; it is not a fully rendered
SideFX wiki. Online Markdown supplies rendered content and its own build stamp.
An index-inferred web build is labeled as inferred, not per-page verified.
Each hit carries source hashes, origin/format, citation and build provenance.

Documentation remains `document_only`. Runtime API membership is still decided
by Scout's independently introspected symbol table. Newer help never establishes
that an API exists in the current Houdini build. The normal `docs`/`vex`/`both`
queries exclude APEX callback pages: their raw files are archived, but callback
queries continue through the explicit `domain='apex'` provider.

`source_status.sidefx_library` reports the configured source and its published
coverage. Missing/corrupt configuration, generation disagreement, unavailable G:
or a failed query produce an explicit unavailable status and retain the existing
Scout sources. The reader opens its own read-only connection for each query and
sees an updated generation on the next request.

## JEV's role

Use TypeSafe JEV for narrow advisory judgments such as architecture tradeoffs or
the relevance of a retrieved shortlist. Download traversal, hashes, build stamps,
coverage, publication and runtime authority remain deterministic. JEV's approval
is not proof of completeness and is not required for normal library searches.
