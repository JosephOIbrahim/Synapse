# Your first SYNAPSE session

[Install first](installation.md) · [Back to README](../../README.md)

Use a scratch scene for the first run. You are checking the connection and the
resulting nodes before moving to a shot.

## 1. Open the panel

In Houdini, choose **New Pane Tab → Synapse**.

Look for the conversation, prompt field, **Connect models**, and separate
**Connect** / **Doctor** controls. The lightning icon opens tools and settings.

If the pane is missing, restart Houdini and follow
[installation verification](installation.md#verify-the-installation).

## 2. Choose the model

Click **Connect models** below the prompt.

| You want | Choose |
|---|---|
| A local model | Ollama, with an installed model and the local service running. |
| A cloud model | Claude, Gemini or NVIDIA Nemotron, with the relevant key. |
| Your own endpoint | Custom, with its service address, model and credentials. |

Select **Build and edit networks** under **Task needs**, then click
**Check connection → Use this model**. The check reads metadata; it does not test
generation. Explicit model selection can proceed when capability metadata is
unknown; automatic selection is stricter. A listed model is not automatically
able to build or read images.

The dialog shows the data destination. Local Ollama needs no API key, but a
customized remote Ollama address sends data to that address. Ollama cloud/relay
models may also send work remotely even through a localhost service. Check the
model and destination, not just the address. Model-data permission
belongs to the current task; choosing a model does not grant every scene operation.

## 3. Make something small

Send:

```text
make a box
```

Inspect the created nodes and the panel's result. Try Undo, then Redo.

A supported build operation groups its scene changes. One Undo does not promise
to reverse a whole conversation, files written to disk, or every failed build.
A partial network may need inspection and deliberate cleanup.

## 4. Try the Solaris starter

Begin with:

```text
create a solaris network
```

Then make the intended setup explicit:

> Use a SOP Create with geometry inside, a dome light using an HDRI I provide,
> an area light, a Material Library with a standard MaterialX surface, a camera,
> and Karma XPU render settings.

This is a task description. Model choice, available tools and the running Houdini
build affect the result. Inspect the geometry, HDRI path, material binding, camera
and render settings. Check node errors before attempting a render.

[Lookdev workflow and limits](../copernicus-lookdev.md) ·
[Solaris reference notes](../knowledge/rob_pieke_h22_solaris.json)

## 5. Ask for a saved suggestion, if configured

Open **lightning tools menu → Saved lookdev suggestion…**, or send
`/lookdev-suggestion`.

A compatible imported Stage 0 experience produces a card. Read its settings and
limits. **Use in prompt** appends editable text; it does not submit that text.
**Dismiss** ends the lookup. Missing memory or a changed version produces an
explanation rather than an invented suggestion.

[Optional setup](../development/rsi_stage0.md)

## If something stops working

- **Model problem:** reopen **Connect models** and check the selected service.
- **Houdini bridge problem:** click **Connect**, then **Doctor**.
- **Need more readable text:** use the lightning tools menu's text-size controls.
- **Need to stop:** use Stop. A running cook/render may still need to finish or be cancelled separately.

The **Connect** button starts the local bridge; it is not the model chooser.
It stays labeled Connect. The panel can use an off-main local fallback when a
tool request was definitely not sent. A lost reply after possible dispatch is
reported as uncertain and must not trigger an automatic duplicate action.

External MCP clients need their own setup and have different permissions:
[MCP connection guide](../mcp/SETUP.md) and
[execution diagrams](../architecture/overview.md#execution-paths).
