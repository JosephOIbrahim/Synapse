# Pipeline Preferences & Production Presets

Studio-confirmed defaults captured so they survive across sessions. Reachable
via `synapse_knowledge_lookup` and (since the recall→RAG seam) `synapse_recall`
/ `synapse_search`.

## Material Binding — prefer materiallinker over assignmaterial

In Solaris, bind materials with the **`materiallinker`** LOP, not
**`assignmaterial`**. `materiallinker` drives collection-based binding and is
the preferred path for production scenes. `assignmaterial` (multiparm tuples
`primpattern1` / `matspecpath1`, documented in `solaris_nodes.md`) remains
available but is not the default choice.

- Preferred: `materiallinker` — collection-aware, scales to many prims.
- Fallback: `assignmaterial` — fine for one-off or explicit single-prim binds.

## Karma CPU Production Preset — diffuse-dominant hero

Starting point for matte / diffuse-dominant surfaces rendered on Karma **CPU**.
Full per-setting rationale lives in `docs/karma_cpu_settings_summary.md`
(derived from the rubber_toy scene).

| Setting | Value |
|---|---|
| Image Mode | Bucket (CPU production) |
| Bucket Size | 64 |
| Pixel Samples | 256 |
| Path Traced Samples | 512 |
| Light Sampling | Light Tree, quality 1.5 |
| Indirect Guiding | ON — 128 training samples, diffuse + sss |
| Variance AA Threshold | 0.005 |
| Pixel Filter | blackman-harris 1.5 |
| Diffuse / Reflect / Refract Limit | 3 / 2 / 0 |
| Min / Max Secondary Samples | 4 / 16 |

Tune down samples for previews; raise diffuse limit for deeper GI. For glass /
transmission surfaces this preset is wrong — it zeroes refraction.

## AMD Material Library — loaded through materiallinker

The AMD library is **not a filesystem path you sublayer** — it is reached through
the `materiallinker` LOP, which is a multiparm node (confirmed by headless probe,
`scripts/probe_materiallinker_amd.py`):

- **Files section** (`num_files` multiparm): each instance has `filepath_N` —
  the USD / material library file to load, plus `createprims_N`
  (Edit Existing / Create New) and `primpath_N`.
- **Links section** (`num_links` multiparm): each instance binds via
  `link_prim_N` / `link_id_N` (the **dropdown** where library materials appear),
  with `link_type_N` = Direct Binding vs Collection Binding.

So the AMD materials show up as options in the **`link_prim` dropdown once the
AMD library is loaded via `filepath_N`** — an empty stage shows an empty menu,
which is why the entry is easy to miss.

> **Still pending (follow-up PR):** the exact AMD library file path and the
> precise `link_prim` menu token. Capturing those needs a live session with the
> AMD library loaded — re-run `scripts/probe_materiallinker_amd.py` there (with
> `filepath_1` pointed at the AMD library) and record the path + token here.
