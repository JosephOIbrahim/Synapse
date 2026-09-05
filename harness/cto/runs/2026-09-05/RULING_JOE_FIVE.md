# Joe's five, after the first live look at v5.65.0 (2026-09-05 ~18:05) - CTO rulings

Joe's words: "1.) the model has no color so if you are running an llm there is no highlight color
its grey which is confusing in context to the user. 2.) TOKEN the whole point of TOKEN is it
supposed to count token use. If that isnt possible this shouldnt exist. Currently it does nothing.
3.) The chat used to have a color for USER and a color for SYNAPSE now its grey for both. That is
confusing for the user. 4.) The Curious, Expert, ML profiles are so minimal in change that perhaps
we should just take that out for now. 5.) The top of SYNAPSE just needs a spacer so the text doesnt
feel choked by the panels top edge."

Joe is the design director; where these override an earlier referee call, they win, and the pins
that encoded the referee call move with the ruling (never silently weakened - retargeted with the
reason in the test).

## J1 - the model token is a status light, not grey data
The token says which engine is thinking; that is state, and state has colour in this panel (the
mark, the state sentence). Colour = the engine's liveness, from the existing palette, no new hex:
  - live / reachable / idle  -> CONIFEROUS (tokens: verified / ok)
  - working (turn streaming)  -> WARM (the busy colour the mark already uses)
  - unreachable / no key      -> TEXT_DISABLED
Text stays `<provider>/<model>` in mono. The chat-face hue-bucket pin (3 at rest) becomes 4 with the
token's bucket named. Wire the colour to the same signal the mark and Connect use (`_apply_context`
/ `_render_state`), so it is never a stale green.

## J2 - TOKEN counts tokens, or it goes
First principles: the face exists to answer "what is this costing me, and how much room is left".
It must show, per session and per turn: prompt tokens, completion tokens, total, the model's context
window and the share used, and cost where a public price is known (cloud providers; local = 0 and
says so). Source of truth = the provider's own usage: Anthropic `usage.input_tokens/output_tokens`;
Ollama `prompt_eval_count/eval_count` on the final chunk; Gemini `usageMetadata`; OpenAI-style
(Nemotron) `usage`. Where a provider reports nothing, the face says "not reported by <provider>" -
never an estimate presented as a count. If, after wiring, no provider in the registry can feed it,
the face is removed. The SPEC decides on evidence: trace `_note_usage` and each provider adapter.

## J3 - two speakers, two colours
Speaker identity must read without reading. USER and SYNAPSE each get their own colour on the name
label and the turn's leading rule, from the palette (no new hex): USER = SIGNAL (the accent already
means "the artist"), SYNAPSE = CONIFEROUS or MUSHROOM - the design warden picks the one with the
better contrast and states the WCAG number. Body text stays TEXT_PRIMARY. The one-accent pin
becomes "one accent for actions; two speaker marks" with the reason.

## J4 - the profile switch leaves the UI
Curious / Expert / ML are retired from the panel for now: no Profile submenu, no pills, no density
switch exposed. The composed profile is `expert` (the default). Manifests, compositor and settings
keep the machinery (tests still exercise it) so it can return with a real difference; nothing an
artist can reach shows it. Persisted `profile` in settings is read as `expert` regardless.

## J5 - air above the identity row
The wordmark is choked by the pane's top edge. The rail's shell inset gets a top margin one grid
step larger than its sides' vertical inset (SPACE_MD 16 at standard; scale with density) carried by
the rhythm role, never a literal. Measured: wordmark top y >= 16 at 340x760 in the composed panel.

Gate: build on `design/joe-five`, one commit per item, hython tests/panel + docking, G3 strict,
stock panel set; referee + design warden; merge under the pre-approval; live reload and shots for
Joe's eyes.
