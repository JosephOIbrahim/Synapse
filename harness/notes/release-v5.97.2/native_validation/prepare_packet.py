"""Create an owned native reproduction packet. CPU-only; never imports HOM.

Requires an existing candidate/source checkout with the exact pinned input bytes
and the already installed H22.0.400 runtime. No downloads/installations/overwrites.
"""
import argparse
import hashlib
import json
from pathlib import Path

PUBLIC = Path(__file__).resolve().parent
HFS = Path(r"C:\Program Files\Side Effects Software\Houdini 22.0.400")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    assert not path.exists(), "Preserve existing packet artifact"
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--packet-root", required=True, type=Path)
    args = parser.parse_args()
    repo, packet = args.repo.resolve(), args.packet_root.resolve()
    assert not packet.exists(), "Use a new owned packet directory; never overwrite"
    inputs = json.loads((PUBLIC / "input-pins.json").read_text(encoding="utf-8"))
    evidence = json.loads((PUBLIC / "native-evidence.json").read_text(encoding="utf-8"))
    # Validate before any writes. Metadata-only release changes outside this
    # namespace-loaded closure do not stand in for production startup testing.
    for row in inputs["source_files"]:
        path = (repo / row["path"]).resolve()
        assert path.is_relative_to(repo) and sha(path) == row["sha256"], row["path"]
    runtime = []
    for row in inputs["runtime_files"]:
        path = (HFS / row["relative_to_hfs"]).resolve()
        assert path.is_relative_to(HFS.resolve()) and sha(path) == row["sha256"], str(path)
        runtime.append({"path": str(path), "sha256": row["sha256"]})
    for name, expected in evidence["producer_sha256"].items():
        assert sha(PUBLIC / name) == expected, "Published producer changed: " + name
    reproduction = evidence["reproduction_controller"]
    assert sha(PUBLIC / reproduction["path"]) == reproduction["sha256"], "Reproduction controller changed"
    packet.mkdir(parents=True)
    for row in inputs["source_files"]:
        path = packet / "source" / row["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((repo / row["path"]).read_bytes())
    names = ("native_probe.py", "run_when_coordinated.ps1", "run_when_coordinated.ps1.txt", "subject_loader.py", "input-pins.json", "native-evidence.json", "slot-template.json")
    for name in names:
        (packet / name).write_bytes((PUBLIC / name).read_bytes())
    write(packet / "source-manifest.json", {"source_root": str(packet / "source"),
          "commit": inputs["tested_commit"], "baseline": inputs["baseline"], "files": inputs["source_files"]})
    files = [{"path": name, "sha256": sha(packet / name)} for name in names + ("source-manifest.json",)]
    write(packet / "prepared-pins.json", {"schema": "scoped-solaris-native-reproduction/1",
          "commit": inputs["tested_commit"], "files": files, "runtime_files": runtime,
          "execution_mode": "full-qualification", "native": "UNRUN",
          "limits": {"processes": 2, "threads": 2, "child_seconds": 120, "aggregate_seconds": 300,
                     "memory_bytes": 4294967296, "artifact_bytes": 67108864}})
    print(json.dumps({"status": "PREPARED_NATIVE_UNRUN", "packet_root": str(packet),
          "prepared_pins_sha256": sha(packet / "prepared-pins.json"),
          "tested_source_commit": inputs["tested_commit"], "native_processes": 0}))


if __name__ == "__main__":
    main()
