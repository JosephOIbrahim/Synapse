"""Source-grounded knowledge intake through the existing Moneta owner.

These are cited reference notes, never checked procedures or executable recipes.
The source digest and exact transcript excerpt are verified before any deposit.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from .models import Memory, MemoryTier, MemoryType


def prepare_capsules(bundle_path, source_root):
    path = Path(bundle_path)
    if path.stat().st_size > 262144:
        raise ValueError("Knowledge bundle exceeds 256 KiB")
    bundle = json.loads(path.read_text(encoding="utf-8"))
    if bundle.get("schema") != "synapse.source_knowledge.v1":
        raise ValueError("Unsupported knowledge bundle")
    stamp = bundle["created_at"]
    if datetime.fromisoformat(stamp).tzinfo is None:
        raise ValueError("Knowledge timestamp must be timezone-aware")
    root = Path(source_root).resolve()
    source = (root / bundle["source"]["file"]).resolve()
    if not source.is_relative_to(root) or source.suffix.lower() != ".md":
        raise ValueError("Source must be a Markdown file inside the selected intake folder")
    if source.stat().st_size > 5 * 1024 * 1024:
        raise ValueError("Source exceeds 5 MiB")
    raw = source.read_bytes()
    source_digest = hashlib.sha256(raw).hexdigest()
    if source_digest != bundle["source"]["sha256"]:
        raise ValueError("Source has changed; rebuild and review this knowledge bundle")
    text = raw.decode("utf-8-sig")
    cards = bundle["cards"]
    if not isinstance(cards, list) or not 1 <= len(cards) <= 32:
        raise ValueError("A knowledge bundle contains between 1 and 32 notes")
    capsules, ids = [], set()
    for card in cards:
        if not re.fullmatch(r"[a-z0-9_]{1,80}", card["id"]) or card["id"] in ids:
            raise ValueError("Knowledge note identity is invalid or duplicated")
        ids.add(card["id"])
        if card["evidence_status"] != "LECTURE_CLAIM":
            raise ValueError("Reference intake cannot promote a claim to runtime verification")
        excerpt = card["source_excerpt"]
        if not isinstance(excerpt, str) or not excerpt or len(excerpt) > 12000 or excerpt not in text:
            raise ValueError("Knowledge excerpt does not match the declared source")
        body = {"schema": bundle["schema"], "title": card["title"],
            "explanation": card["explanation"], "artist_control": card["artist_control"],
            "evidence_status": "LECTURE_CLAIM", "runtime_verified": False,
            "source": {**bundle["source"], "local_path": str(source),
                       "timestamp": card["timestamp"], "excerpt": excerpt},
            "limits": "Reference knowledge only. Inspect the running Houdini build and test any proposed network before claiming it works."}
        encoded = json.dumps(body, sort_keys=True, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > 16384:
            raise ValueError("Knowledge note exceeds 16 KiB")
        identity = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        memory = Memory(id="knowledge_" + identity, content=encoded,
            summary="Rob Pieke H22 Solaris: " + card["title"],
            created_at=stamp, updated_at=stamp, memory_type=MemoryType.NOTE,
            tier=MemoryTier.SHOW, source="reference", agent_id="synapse-source-intake-v1",
            node_paths=["/stage"], tags=["source_knowledge", "rob_pieke", "solaris", "houdini22"],
            keywords=card.get("keywords", []), ref_uri=str(source))
        capsules.append(memory.to_dict())
    return capsules


def ingest_bundle(bundle_path, source_root, memory_port):
    """Validate the complete packet first; interrupted deliveries can be retried."""
    capsules = prepare_capsules(bundle_path, source_root)
    results = [memory_port.deposit_capsule(capsule)._asdict() for capsule in capsules]
    return {"success": all(r["status"] == "SUCCESS" for r in results),
            "records": results, "count": len(capsules), "evidence_status": "LECTURE_CLAIM"}
