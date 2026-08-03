# LLM support — shipped

> This file was a pre-H22 strategy paper (2026-06-22, v5.14.0). The multi-provider work it argued for has since shipped, and the paper's specifics no longer describe the tree. The code is the record now; this pointer exists so a stale design can't keep teaching.

Provider support lives at **`python/synapse/panel/providers/`** — a streaming provider abstraction the panel's engines plug into. The panel exposes five engines; your pick persists via `.synapse/panel_settings.json`.

**Ollama runs local.** No API key, nothing leaves the machine — SYNAPSE talks to your own server at its default address, `http://localhost:11434`.

For current engine names, capabilities, and configuration, read the package. The README's "Runs your model" section carries the user-facing summary.
