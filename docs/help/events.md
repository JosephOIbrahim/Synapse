# Know when work needs your attention

Open **Events** below the prompt, or choose `/events` in Commands. SYNAPSE keeps
recent work and connection updates in this Houdini session. Opening Events does
not send a prompt, run a job or share scene data.

SYNAPSE render operations and final batch reports appear automatically. To follow
other work, select a supported render output, File Cache, or TOP node and choose
**Watch selected**. The result tells you exactly which sources are being watched.
Foreground and background cache work can have different coverage. Watching does
not start a cook or render. Closing SYNAPSE stops these selected watches.

**Finished** means the observed source reported that its operation completed.
It does not certify the resulting image or cache. **Needs attention** can mean
that SYNAPSE saw activity end but could not confirm the outcome; it does not
automatically mean the work failed. A viewport fallback is labeled **Preview only**.
An arbitrary SOP simulation may have no usable completion event: select its cache
output or TOP network instead. A cancel request is not proof that cooking stopped.

Select an event to read details, copy them, or inspect the exact watched node.
If its scene or identity changed, SYNAPSE keeps the record and refuses to jump
to a replacement. Model-check events offer **Model setup**. Metadata checks show
the service's location; they do not claim that a generation request was tested.

**Quiet** keeps the history without new alerts. **Completion alerts** can be
disabled while failures still ask for attention. Desktop alerts are off by
default and depend on your operating system. When enabled, they contain a generic
message; scene paths and job details stay in Events. The operating system may
retain those generic alerts after Houdini closes.

The bounded Events history survives reopening the panel in the same Houdini
process. It ends when that process exits. Old desktop alerts are not replayed on
reopen. **Mark all read** clears unread attention, and **Clear finished** removes
finished records without stopping running jobs. Retention loss is shown explicitly.
