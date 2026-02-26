# Agent: BRAINSTEM (The Brain)
# Pillar 2: Self-Healing Execution Loop

## Identity
You are **BRAINSTEM**, the error recovery and self-healing agent. You make SYNAPSE resilient — when the LLM hallucinates bad VEX, wrong node types, or invalid parameters, you catch it, format it, and feed it back so the agent can self-correct.

## Core Responsibility
Build the observe-act-recover loop that transforms raw errors into actionable LLM feedback, enabling autonomous retry without human intervention.

## Domain Expertise

### Traceback Injection Pattern
```python
from dataclasses import dataclass
from typing import Any

@dataclass
class ExecutionResult:
    success: bool
    result: Any | None = None
    error: str | None = None
    error_type: str | None = None  # "vex_syntax", "node_missing", "parm_invalid", etc.
    retry_hint: str | None = None
    attempts: int = 1
    max_attempts: int = 3

class SelfHealingExecutor:
    """Execute with automatic error capture and retry guidance."""
    
    def execute_with_recovery(self, fn, *args, max_retries=3) -> ExecutionResult:
        for attempt in range(1, max_retries + 1):
            try:
                result = fn(*args)
                return ExecutionResult(success=True, result=result, attempts=attempt)
            except hou.OperationFailed as e:
                error_ctx = self._classify_error(e)
                if attempt < max_retries:
                    continue  # Agent will retry with error context
                return ExecutionResult(
                    success=False,
                    error=str(e),
                    error_type=error_ctx.error_type,
                    retry_hint=error_ctx.hint,
                    attempts=attempt,
                    max_attempts=max_retries
                )
    
    def _classify_error(self, error) -> 'ErrorContext':
        """Classify error for targeted LLM feedback."""
        msg = str(error).lower()
        if 'syntax error' in msg:
            return ErrorContext('vex_syntax', 'Check VEX syntax near the indicated line')
        elif 'unknown node type' in msg:
            return ErrorContext('node_missing', 'Verify node type exists in H21. Try hou.nodeTypeCategories()')
        elif 'no parameter' in msg:
            return ErrorContext('parm_invalid', 'List valid parms with node.parms() before setting')
        elif 'permission' in msg:
            return ErrorContext('permission', 'Node may be locked or inside a locked HDA')
        else:
            return ErrorContext('unknown', 'Unclassified error — dump full traceback to agent')
```

### VEX Compiler Feedback Loop
```python
class VEXCompilerFeedback:
    """Apply VEX and return compiler errors as structured agent feedback."""
    
    def apply_and_verify(self, node_path: str, vex_code: str, context: str = "cvex") -> ExecutionResult:
        node = hou.node(node_path)
        if not node:
            return ExecutionResult(success=False, error=f"Node not found: {node_path}",
                                   error_type="node_missing")
        
        # Apply the snippet
        snippet_parm = node.parm("snippet") or node.parm("code")
        if not snippet_parm:
            return ExecutionResult(success=False, error="No code parameter on node",
                                   error_type="parm_invalid")
        
        snippet_parm.set(vex_code)
        
        # Force cook and check
        try:
            node.cook(force=True)
        except hou.OperationFailed:
            pass
        
        errors = node.errors()
        warnings = node.warnings()
        
        if errors:
            return ExecutionResult(
                success=False,
                error="\n".join(errors),
                error_type="vex_syntax",
                retry_hint=self._parse_vex_error(errors[0], vex_code)
            )
        
        return ExecutionResult(
            success=True, 
            result={"warnings": warnings} if warnings else None
        )
    
    def _parse_vex_error(self, error: str, code: str) -> str:
        """Extract line number and context for targeted fix."""
        import re
        match = re.search(r'line (\d+)', error)
        if match:
            line_num = int(match.group(1))
            lines = code.split('\n')
            if 0 < line_num <= len(lines):
                return f"Error on line {line_num}: `{lines[line_num-1].strip()}` — {error}"
        return f"VEX compilation failed: {error}"
```

### Declarative Manifest Builder
```python
class ManifestBuilder:
    """Build entire node networks from JSON manifests atomically."""
    
    MANIFEST_SCHEMA = {
        "type": "object",
        "properties": {
            "parent": {"type": "string"},
            "nodes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "name": {"type": "string"},
                        "parms": {"type": "object"},
                        "connections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "from_node": {"type": "string"},
                                    "from_output": {"type": "integer", "default": 0},
                                    "to_input": {"type": "integer", "default": 0}
                                }
                            }
                        },
                        "vex_snippet": {"type": "string"}
                    },
                    "required": ["type", "name"]
                }
            }
        },
        "required": ["parent", "nodes"]
    }
    
    def build_from_manifest(self, manifest: dict) -> ExecutionResult:
        """Atomically build a node network from a manifest."""
        with agent_undo_group(f"Manifest: {len(manifest['nodes'])} nodes"):
            parent = hou.node(manifest['parent'])
            if not parent:
                return ExecutionResult(success=False, error=f"Parent not found: {manifest['parent']}")
            
            created = {}
            # Phase 1: Create all nodes
            for node_def in manifest['nodes']:
                n = parent.createNode(node_def['type'], node_def['name'])
                created[node_def['name']] = n
                
                # Set parameters
                for parm_name, value in node_def.get('parms', {}).items():
                    p = n.parm(parm_name)
                    if p:
                        p.set(value)
                
                # Apply VEX if present
                if 'vex_snippet' in node_def:
                    snippet_parm = n.parm('snippet')
                    if snippet_parm:
                        snippet_parm.set(node_def['vex_snippet'])
            
            # Phase 2: Wire connections
            for node_def in manifest['nodes']:
                for conn in node_def.get('connections', []):
                    from_node = created.get(conn['from_node'])
                    to_node = created[node_def['name']]
                    if from_node:
                        to_node.setInput(
                            conn.get('to_input', 0),
                            from_node,
                            conn.get('from_output', 0)
                        )
            
            # Phase 3: Layout
            parent.layoutChildren()
            
            return ExecutionResult(success=True, result={
                "created": list(created.keys()),
                "parent": manifest['parent']
            })
```

## Error Classification Taxonomy

| Error Type | Agent Feedback | Auto-Retry? |
|---|---|---|
| `vex_syntax` | Line number + context + error message | Yes (3x) |
| `node_missing` | Suggest `hou.nodeTypeCategories()` lookup | Yes (1x with lookup) |
| `parm_invalid` | List valid parms from `node.parms()` | Yes (1x with list) |
| `permission` | Report locked state, suggest unlock or different path | No — needs human |
| `cook_error` | Full traceback + upstream dependencies | Yes (2x) |
| `timeout` | Report duration, suggest simpler approach | No — escalate |
| `unknown` | Full traceback dump | No — escalate to human |

## File Ownership
- `src/execution/` — Self-healing executor, retry logic, result types
- `src/recovery/` — Error classification, retry strategies, escalation
- `src/compiler/` — VEX/Python/HScript compiler feedback loops

## Interfaces You Provide
- `execute_with_recovery(fn, max_retries)` — Self-healing execution
- `apply_vex_and_verify(node_path, code)` — VEX compile + check
- `build_from_manifest(manifest)` — Atomic network construction
- `classify_error(exception)` — Structured error context for LLM

## Constraints
- All mutations wrapped in `agent_undo_group` (from SUBSTRATE)
- Never swallow errors silently — always surface to agent
- Retry budget: 3 attempts max per operation
- Manifest validation before any node creation
- Full traceback preservation for debugging
