# CAPSULE — VIDEO DROP (single-purpose handoff)

**Mission for a fresh Claude session with Desktop Commander:** Joe recorded a SYNAPSE demo
and posted it to Vimeo. He will paste this file's path plus the Vimeo link. Embed the video
on the repo front page as a clickable thumbnail, verify the claims surfaces, and push on
his word. Nothing else.

**Machine facts:** repo `C:\Users\User\Synapse` (branch master, remote JosephOIbrahim/Synapse).
The workstation must be ON for Desktop Commander. `harness/notes/scratch/` is gitignored.

## Hard rules (ratified, do not bend)
1. README line starting `> v` (the version banner) is a sync surface — NEVER edit it.
2. Never `git add -A`. Add named files only.
3. Push requires Joe's explicit word IN THAT CHAT, then exactly:
   `$env:SYNAPSE_GATE_C=1; git push origin master; Remove-Item Env:SYNAPSE_GATE_C`
4. Unrelated in-flight work (W1/INS branches, closer receipts) has its own protocol in
   `CAPSULE_2026-08-09_cache-wave.md` — do not touch it from this session.

## Steps
1. Validate the link matches `https://vimeo.com/<digits>`.
2. Fetch metadata (title + thumbnail):
   `$m = Invoke-RestMethod "https://vimeo.com/api/oembed.json?url=<LINK>"`
3. Download the thumbnail:
   `Invoke-WebRequest $m.thumbnail_url -OutFile C:\Users\User\Synapse\assets\demo_video_thumb.jpg`
4. Edit `README.md`: insert the block below AFTER the `---` that closes the
   "## For artists — the one-minute version" section and BEFORE `## Runs your model`:

   ```
   ## Watch it work

   [![SYNAPSE demo — natural language to real Houdini nodes](assets/demo_video_thumb.jpg)](<LINK>)

   *Two minutes of SYNAPSE in practice: plain English in, undoable nodes out.*

   ---
   ```

   Fallback if the oEmbed fetch fails: same section, bold link line instead of the image.
5. Verify BEFORE any commit: `python scripts\sync_version.py --check` → PASS, and
   `python -m pytest tests/test_phase0c_doc1_version_conformance.py -q` → 11 passed.
6. Commit: `git add README.md assets/demo_video_thumb.jpg` then
   `git commit -m "docs(readme): demo video on the front page (Vimeo thumbnail link)"`
7. Ask Joe for the push word. On it, rule 3's exact form. Then confirm CI:
   `gh run list -L 1` → success (~3 min).
8. Tell Joe this may satisfy Gate A task L3-2 (demo video) — his call to mark it.

## Done looks like
Repo front page shows the thumbnail under the artist section; clicking plays the Vimeo;
CI green; banner byte-identical.
