# Rendering from SYNAPSE

Open **Render** beside Commands, find **/render** in Commands, or type `/render`. The view opens beside your work and preserves a conversation draft when opened with a button or Commands. A model connection is not required. You can check a render while another SYNAPSE conversation is busy.

Save the Houdini scene first. Select its Solaris output, choose the frames and destination, then press **Prepare render**. SYNAPSE makes a separate package of the scene and textures. Preparation does not render. When preparation finishes, review the source, exact frames and settings, then press **Render N frames**.

The editable scene stays yours. The renderer uses the prepared revision. Changing the form creates a new intent that needs preparation. A saved scene change after preparation does not silently change a queued render.

Settings contains resolution, samples, text size and the farm availability explanation. Recent renders restores the recorded job. Closing this view stops its polling, while the detached worker continues. Reopening and refreshing reads existing work; it does not start it again. A connection problem keeps the request ID so status can be recovered without creating a duplicate.

**Cancel render** first means that cancellation was requested. The view says it stopped only after the owned processes have stopped. Partial images are not offered as completed output. **Open output** requires a completed verification record and a fresh check of the recorded files. A successful TOP cook or a file that merely exists is insufficient.

The first implementation profile is a bounded **local Karma CPU preview** on Windows Houdini 22.0.400. It accepts a saved Solaris scene with one camera and one RGBA EXR product. It freezes each requested frame separately, including exported Copernicus textures. Each job uses one task at a time and two CPU threads. Separate submitted jobs can run together; a shared resource or license limit across jobs has not been implemented. Its initial admission limits are 120 frames, 2048 pixels per dimension, 128 samples and 60 seconds per frame. A scene that needs other products, unsupported dependencies or more resources receives a reason rather than an apparent success. Actual qualification used 256-pixel, eight-sample fixtures; the maximum limits are not a tested production capacity promise. The controls are available in local deployment only; shared studio access requires per-user identity and job ownership before admission.

**Render farm** remains unavailable until an HQueue controller, shared storage, service identities, worker versions and concurrent licenses have been configured and tested together. A local native render does not prove that a remote farm is ready. The prepared request and backend interface are the foundation for that next stage.

For the implementation owner, the job journal defaults to `%LOCALAPPDATA%/SYNAPSE/render_jobs/farm.sqlite3`. Keep this journal on controller-local disk. `SYNAPSE_RENDER_HOME` can choose another absolute local directory. The chosen output destination contains `synapse_renders/<request_id>/`, including the sealed package, visible TOP graph, native execution receipts, logs and outputs. `SYNAPSE_FARM_HFS` can select the installed Houdini location; the native process checks the build before doing work.

The request journal belongs to the host service. The Render view observes it through seven tools: inspect, capabilities, prepare, submit, jobs, job and cancel, all prefixed `synapse_farm_`. TOPs owns work dependencies; the native process owns execution and image decoding. Every submission is bound to one immutable request digest. Existing public TOPs and legacy render tools remain available for compatibility.

This feature is being qualified in the isolated `feature/tops-renderfarm-20260907` worktree. It has not been deployed to the artist's open Houdini session. The execution plan and measured limits are recorded in [ARTIST_RENDER_IMPLEMENTATION.md](ARTIST_RENDER_IMPLEMENTATION.md); the original coffee conversation and farm blueprint remain the broader design context.
