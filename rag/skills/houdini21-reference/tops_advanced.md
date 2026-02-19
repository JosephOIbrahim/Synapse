# TOPS/PDG Advanced Patterns

## Overview

Beyond basic wedging, TOPS/PDG provides a full dependency-graph computation framework. This reference covers advanced patterns for production pipelines. For wedging basics, see `tops_wedging.md`.

## Dynamic Work Items

Work items can be static (count known at generate time) or dynamic (count depends on upstream results).

### Static Generation
- Count is fixed before cook starts
- Nodes: `wedge`, `filepattern`, `genericgenerator`
- Fast to schedule because the full graph is known upfront

### Dynamic Generation
- Count depends on upstream results -- created during cook, not generate
- `pythonprocessor` with `generateWhen` set to "Each Upstream Item" or "All Upstream Items"
- Dynamic partitioning: partitions created at cook time based on actual data

### Dynamic Generation Example
```python
# In pythonprocessor (dynamic mode)
# Reads upstream result, creates variable number of outputs
import json
upstream_file = work_item.inputResultData[0].path
with open(upstream_file) as f:
    data = json.load(f)
for i, item in enumerate(data["items"]):
    new_item = item_holder.addWorkItem(index=i)
    new_item.setStringAttrib("asset_path", item["path"])
```

### When to Use Dynamic
- Shot list from database query (count unknown until query runs)
- Processing variable-length data (JSON arrays, directory listings)
- Feedback loops where iteration count depends on convergence

## Feedback Loops

`feedbackbegin` / `feedbackend` nodes create iterative loops within a TOPS network.

### Structure
```
feedbackbegin -> process -> evaluate -> feedbackend
```

### How It Works
1. Upstream cooks and feeds into `feedbackbegin`
2. Items flow through the loop body (process -> evaluate)
3. `feedbackend` checks the stop condition
4. If stop condition is False, items re-enter `feedbackbegin` for next iteration
5. If stop condition is True, items pass through to downstream nodes

### Key Parameters
- `feedbackend` stop condition: Python expression returning True to stop
- Max iterations: prevents infinite loops (always set this)
- Access iteration count in expressions: `@pdg_iteration`
- Previous iteration results: `work_item.inputResultData`

### Use Cases
- Iterative render refinement (render -> evaluate quality -> adjust settings -> re-render)
- Convergence testing (simulate -> measure -> stop when threshold met)
- Progressive resolution (render low-res -> check -> double resolution -> repeat)

### Example: Iterative Render Refinement
```
feedbackbegin
  -> set_samples (double samples each iteration)
    -> ropfetch (render)
      -> pythonprocessor (evaluate noise level)
        -> feedbackend (stop when noise < threshold)
```

Stop condition on feedbackend:
```python
# Stop when noise is below threshold or max iterations reached
work_item.attrib("noise_level").value < 0.01 or pdg_iteration >= 5
```

## Partitioners

Partitioners group work items into batches. Downstream nodes see one work item per partition, containing references to all member items.

| Node | Description | Use Case |
|------|-------------|----------|
| `partitionbyattribute` | Group by attribute value | Group renders by shot |
| `partitionbyframe` | Group by frame range | Batch frame ranges for encoding |
| `partitionbynode` | Group by upstream node | Collect per-stage results |
| `partitionbycombination` | Combinatorial grouping | Cross-product analysis |
| `waitforall` | Single partition of all items | Collect everything before final step |

### Partition Behavior
- Downstream nodes wait for all items in a partition to complete
- Partitions create batch work items containing references to members
- Access members in Python: `work_item.partitionItems`
- Member output files: iterate `partition_item.resultData` for each member

### Custom Partitioning with pythonpartitioner
```python
# Group work items by shot name prefix
shot = work_item.attrib("shot_name").value
partition_key = shot.split("_")[0]  # e.g., "sq010" from "sq010_sh020"
return partition_key
```

## Schedulers (Advanced)

### Local Scheduler Tuning

| Parameter | Default | Production Recommendation |
|-----------|---------|--------------------------|
| `maxproccount` | CPU cores | 1 for GPU renders, core count for CPU |
| `tempdirlocal` | $TEMP | Fast SSD path for work item data |
| `taskgraph` | off | Enable for complex dependency visualization |
| `verbose` | off | Enable for debugging scheduler decisions |

### HQueue Scheduler
- Farm submission to SideFX HQueue render manager
- `hqserver`: farm coordinator address (e.g., `http://hq-server:5000`)
- `hqclient_path`: path to hqclient binary on render nodes
- Priority and job grouping via work item attributes
- Per-work-item environment variables for farm configuration

### Deadline Scheduler
- Thinkbox Deadline integration for mixed-vendor farms
- `deadlinerepo`: path to Deadline repository
- Groups, pools, priority mappable from work item attributes
- Plugin info and job info customizable per work item type
- Supports Deadline's built-in job dependencies

### Scheduler Selection Tips
- Local scheduler for development and small jobs
- HQueue for SideFX-native studios
- Deadline for mixed-DCC studios (Maya + Houdini + Nuke)
- Set scheduler at topnet level, override per-node if needed

## Error Handling and Recovery

### Work Item States
- **Waiting**: Dependencies not yet satisfied
- **Cooking**: Currently executing
- **Cooked**: Completed successfully
- **Failed**: Execution failed
- **Cancelled**: Manually or automatically cancelled

### Error Handling Parameters

| Parameter | Values | Description |
|-----------|--------|-------------|
| `errorcondition` | Continue, Warn, Error | What happens when an item fails |
| `maxretries` | 0+ | Auto-retry count (0 = no retry) |

- **Continue**: Mark item failed, continue cooking other items
- **Warn**: Mark failed, continue, show warning
- **Error**: Stop the entire cook on first failure

### Error Attributes
- `@pdg_error`: error message string on failed items
- `@pdg_errorcount`: number of times this item has errored

### Retry Strategy
- `maxretries=2` is a good default for render jobs (transient failures)
- For farm submission, retry handles node hiccups
- For local processing, retry rarely helps (same error will recur)

### Checkpoint and Resume
- Cooked items cached to disk (work item files + `.json` state)
- Resume skips already-cooked items automatically
- Dirty specific nodes to force re-cook of a subset
- `pdg_checkpointfile` attribute stores checkpoint location
- Essential for long render sequences -- crash at frame 500 of 1000 does not restart from frame 1

## Production Pipeline Patterns

### Render Sequence
End-to-end render pipeline:
```
filepattern (scene files)
  -> ropfetch (render per frame)
    -> waitforall
      -> imagemagick (contact sheet)
      -> ffmpegencodevideo (movie)
```

### Multi-Shot Render
```
pythonprocessor (generate shot list)
  -> set_shot_context (per-shot env vars)
    -> ropfetch (render)
      -> partitionbyattribute (group by shot)
        -> ffmpegencodevideo (per-shot movie)
          -> waitforall
            -> notify (email/slack)
```

### Lookdev Pipeline
```
filepattern (textures)
  -> wedge (material variants)
    -> ropfetch (render turntable)
      -> partitionbyattribute (group by material)
        -> imagemagick (comparison sheet per material)
```

### Simulation Cache + Render
```
ropfetch (sim cache)
  -> waitforall
    -> wedge (lighting/camera variations)
      -> ropfetch (render)
        -> ffmpegencodevideo
```
Cache simulation once, then wedge render parameters without re-simulating.

## Monitoring and Diagnostics

### PDG Graph Table
- Visual work item state tracking in the TOPS task graph pane
- Color-coded: green = cooked, red = failed, blue = cooking, grey = waiting
- Click any work item to inspect attributes, output files, cook time

### Cook Stats
- Per-node timing, item counts, failure rates
- Available in UI via TOPS task graph info panel
- Programmatic access:
```python
work_item = pdg.workItem()
stats = work_item.cookStats()
```

### Dependency Graph Export
```python
# Export dependency graph for external analysis
graph_json = pdg.graph.serializationJSON()
```

## Work Item Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `@pdg_index` | int | Work item index within its node |
| `@pdg_name` | string | Unique work item name |
| `@pdg_frame` | float | Associated frame number |
| `@pdg_iteration` | int | Feedback loop iteration count |
| `@pdg_output` | string | Primary output file path |
| `@pdg_input` | string | Primary input file path |
| `@pdg_error` | string | Error message if failed |
| `@pdg_errorcount` | int | Number of errors encountered |
| `@pdg_priority` | int | Scheduling priority (higher = sooner) |

### Custom Attributes
```python
# Set custom attributes in pythonprocessor
work_item.setStringAttrib("shot_name", "sq010_sh020")
work_item.setIntAttrib("frame_start", 1001)
work_item.setFloatAttrib("quality", 0.95)

# Read attributes downstream
shot = work_item.attrib("shot_name").value
```

## Performance Optimization

- **Generate before cook**: pre-compute static items so the scheduler can plan ahead
- **Batch by frame range**: use `partitionbyframe` to reduce scheduler overhead for animation
- **File caching**: use `filecache` TOP to cache intermediate results, avoid re-computation
- **Limit concurrent GPU items**: set `maxproccount=1` for GPU renders (GPU contention destroys throughput)
- **Temporal batching**: `partitionbyframe` groups frames for efficient encoding and review
- **Pre-flight validation**: add a lightweight check node (pythonprocessor) before expensive renders to catch missing files, bad paths, or invalid parameters early
- **Minimize dynamic generation**: prefer static when possible -- dynamic items can't be scheduled ahead of time
- **Work item data locality**: keep temp files on fast local storage, not network drives

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| All items fail simultaneously | Scheduler not configured | Verify scheduler node exists and is started |
| Items stuck in Waiting | Unresolved dependencies | Check dependency graph for cycles or missing connections |
| Cook hangs indefinitely | Deadlock in feedback loop | Add max iterations, verify stop condition logic |
| Output files missing | Wrong output attribute | Verify `@pdg_output` or call `addExpectedResultData` |
| Farm jobs fail | Missing environment on render nodes | Set env vars via scheduler attributes, check paths |
| Memory explosion | Too many concurrent items | Reduce `maxproccount`, add partitioning stages |
| Slow generation phase | Excessive dynamic generation | Convert to static where possible, reduce upstream fanout |
| Items cook out of order | Priority not set | Use `@pdg_priority` or explicit dependencies |
| Checkpoint resume re-cooks everything | Dirty state not cleared | Check that checkpoint files exist and match current graph |
