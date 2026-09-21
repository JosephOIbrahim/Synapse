"""fxhoudinimcp benchmark arm -- the outside-in opponent.

Runs the fxhoudinimcp MCP server over stdio (JSON-RPC 2.0: ``initialize`` ->
``tools/list`` -> ``tools/call``), which in turn drives its own hwebserver plugin inside
its own Houdini on port 8100. HARD ISOLATION (HARVEST_SPEC + mission note):

  * installed via ``pip install fxhoudinimcp`` into a SEPARATE venv -- never SYNAPSE's env,
    never vendored into hython;
  * its Houdini package file points at a SCRATCH packages dir, so it loads in a fresh
    Houdini that is not SYNAPSE's;
  * pinned to port 8100 (SYNAPSE holds 9999); its own scene copy.

Nothing here touches SYNAPSE's ledger, undo stack, or session store. If the arm venv has
no fxhoudinimcp, ``available()`` says so and the runner records the cell UNKNOWN -- never a
fabricated result.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _agent  # noqa: E402

PORT = 8100  # pinned; fxhoudinimcp's hwebserver default-scans 8100-8115, we pin the low end


class FxArm:
    name = "fxhoudinimcp"

    def __init__(self, scene: str, *, venv_dir: str, packages_dir: str, port: int = PORT):
        self.scene = scene
        self.venv_dir = Path(venv_dir)
        self.packages_dir = Path(packages_dir)
        self.port = port
        self._proc: subprocess.Popen | None = None
        self._rpc_id = 0

    # --- environment (network + install; run.py calls this only on explicit opt-in) --- #
    def _venv_python(self) -> Path:
        if os.name == "nt":
            return self.venv_dir / "Scripts" / "python.exe"
        return self.venv_dir / "bin" / "python"

    def setup_env(self) -> tuple[bool, str]:
        """Create the isolated venv and pip-install fxhoudinimcp. Needs network. Writes a
        Houdini package json into a scratch packages dir. NEVER touches SYNAPSE's env."""
        try:
            if not self._venv_python().exists():
                subprocess.run([sys.executable, "-m", "venv", str(self.venv_dir)], check=True,
                               capture_output=True, timeout=180)
            subprocess.run([str(self._venv_python()), "-m", "pip", "install", "--quiet", "fxhoudinimcp"],
                           check=True, capture_output=True, timeout=600)
            self.packages_dir.mkdir(parents=True, exist_ok=True)
            pkg = self.packages_dir / "fxhoudinimcp.json"
            pkg.write_text(json.dumps({
                "env": [{"FXHOUDINIMCP_PORT": str(self.port)}],
                "load_package_once": True,
            }, indent=2), encoding="utf-8")
            return True, f"installed into {self.venv_dir}"
        except subprocess.CalledProcessError as e:  # noqa: PERF203
            return False, f"setup failed: {e.stderr.decode('utf-8', 'replace')[:300] if e.stderr else e}"
        except Exception as e:  # noqa: BLE001
            return False, f"setup failed: {type(e).__name__}: {e}"

    def available(self) -> tuple[bool, str]:
        py = self._venv_python()
        if not py.exists():
            return False, f"no arm venv at {self.venv_dir} (call setup_env(): pip install fxhoudinimcp)"
        try:
            out = subprocess.run([str(py), "-c", "import fxhoudinimcp,sys;print(fxhoudinimcp.__name__)"],
                                 capture_output=True, timeout=30)
            if out.returncode != 0:
                return False, f"fxhoudinimcp not importable in arm venv: {out.stderr.decode('utf-8', 'replace')[:200]}"
            return True, "arm venv ready"
        except Exception as e:  # noqa: BLE001
            return False, f"probe failed: {type(e).__name__}: {e}"

    # --- MCP stdio JSON-RPC transport --- #
    def _launch(self) -> tuple[bool, str]:
        env = dict(os.environ)
        env["HOUDINI_PACKAGE_DIR"] = str(self.packages_dir)  # isolate: fresh Houdini, not SYNAPSE's
        env["FXHOUDINIMCP_PORT"] = str(self.port)
        try:
            self._proc = subprocess.Popen(
                [str(self._venv_python()), "-m", "fxhoudinimcp"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=env, bufsize=1)
        except Exception as e:  # noqa: BLE001
            return False, f"launch failed: {type(e).__name__}: {e}"
        init = self._rpc("initialize", {"protocolVersion": "2024-11-05",
                                        "capabilities": {}, "clientInfo": {"name": "outside-in-bench", "version": "1"}})
        if init.get("error"):
            return False, f"initialize error: {init['error']}"
        self._notify("notifications/initialized", {})
        return True, "mcp server up"

    def _rpc(self, method: str, params: dict) -> dict:
        self._rpc_id += 1
        req = {"jsonrpc": "2.0", "id": self._rpc_id, "method": method, "params": params}
        self._proc.stdin.write(json.dumps(req) + "\n")
        self._proc.stdin.flush()
        deadline = time.time() + 120
        while time.time() < deadline:
            line = self._proc.stdout.readline()
            if not line:
                return {"error": "server closed stdout"}
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("id") == self._rpc_id:
                return msg
        return {"error": "rpc timeout"}

    def _notify(self, method: str, params: dict):
        self._proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n")
        self._proc.stdin.flush()

    def tools(self) -> list:
        listed = self._rpc("tools/list", {})
        out = []
        for t in (listed.get("result", {}) or {}).get("tools", []):
            out.append({"name": t["name"], "description": t.get("description", ""),
                        "input_schema": t.get("inputSchema", {"type": "object", "properties": {}})})
        return out

    def tool_runner(self, name: str, tool_input: dict):
        resp = self._rpc("tools/call", {"name": name, "arguments": tool_input or {}})
        if resp.get("error"):
            raise RuntimeError(resp["error"])
        content = (resp.get("result", {}) or {}).get("content", [])
        return "\n".join(c.get("text", "") for c in content if c.get("type") == "text") or content

    def run(self, *, client, prompt: str, model: str, max_turns: int = 12) -> dict:
        if self._proc is None:
            ok, reason = self._launch()
            if not ok:
                r = _agent.new_result()
                r["error"] = f"arm unavailable: {reason}"
                return r
        system = ("You are a Houdini technical artist working headless. Use the tools to build the "
                  "requested setup, then briefly say what you built.")
        return _agent.run_agent(client=client, prompt=prompt, tools=self.tools(),
                                tool_runner=self.tool_runner, model=model, system=system,
                                max_turns=max_turns)

    def save_scene(self) -> tuple[bool, str]:
        try:
            self.tool_runner("execute_python", {"code": f"import hou; hou.hipFile.save({self.scene!r})"})
            return True, self.scene
        except Exception as e:  # noqa: BLE001
            return False, f"save via arm not available: {type(e).__name__}: {e}"

    def close(self):
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:  # noqa: BLE001
                pass
            self._proc = None
