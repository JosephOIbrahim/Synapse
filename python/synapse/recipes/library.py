"""Local saved-network assets; no host, model, Qt, or memory-store ownership.

The host supplies the native clip writer and USD metadata codec. A version is
visible only after its complete directory is published. Curated RecipeSpec
qualification is deliberately not inferred from a successful file capture.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata
import uuid

SCHEMA = "synapse-saved-network-v1"
_ID = re.compile(r"[0-9a-f]{32}\Z")
_VERSION = re.compile(r"v([0-9]{6})\Z")


class LibraryError(ValueError):
    """An asset could not be saved, verified or read."""


def normalize_metadata(name, tags, notes=""):
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
        raise LibraryError("Give the recipe a name of 1–120 characters.")
    if not isinstance(notes, str) or len(notes) > 4000:
        raise LibraryError("Notes must be text of at most 4,000 characters.")
    if not isinstance(tags, (tuple, list)) or len(tags) > 20:
        raise LibraryError("Use at most 20 tags, separated by commas.")
    result = []
    for tag in tags:
        if not isinstance(tag, str):
            raise LibraryError("Each tag must be text.")
        tag = unicodedata.normalize("NFKC", tag).strip().casefold()
        if len(tag) > 40:
            raise LibraryError("Keep each tag within 40 characters.")
        if tag and tag not in result:
            result.append(tag)
    return {"name": name.strip(), "tags": result, "notes": notes.strip()}


def default_library_path():
    override = os.environ.get("SYNAPSE_RECIPE_DIR", "").strip()
    return Path(override) if override else Path.home() / ".synapse" / "recipes"


class SavedNetworkLibrary:
    max_clip_bytes = 32 * 1024 * 1024
    max_manifest_bytes = 4 * 1024 * 1024

    def __init__(self, root, codec):
        self.root = Path(root).resolve()
        self.codec = codec

    def _recipe_path(self, recipe_id):
        if not isinstance(recipe_id, str) or not _ID.fullmatch(recipe_id):
            raise LibraryError("Invalid recipe identity.")
        path = self.root / recipe_id
        if path.resolve().parent != self.root:
            raise LibraryError("Recipe identity leaves this library.")
        return path

    def version_path(self, recipe_id, version):
        if type(version) is not int or not 1 <= version <= 999999:
            raise LibraryError("Invalid recipe version.")
        parent = self._recipe_path(recipe_id)
        path = parent / f"v{version:06d}"
        if path.resolve().parent != parent:
            raise LibraryError("Version identity leaves this recipe.")
        return path

    def _versions(self, parent):
        if not parent.exists():
            return []
        return sorted(int(match.group(1)) for path in parent.iterdir()
                      if path.is_dir() and (match := _VERSION.fullmatch(path.name)))

    def _clip_hash(self, path):
        if path.is_symlink() or not path.is_file():
            raise LibraryError("The saved network clip is missing or redirected.")
        size = path.stat().st_size
        if not 0 < size <= self.max_clip_bytes:
            raise LibraryError("The network clip exceeds the supported size, or is empty.")
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def save(self, name, tags, notes, capture, *, recipe_id=None):
        metadata = normalize_metadata(name, tags, notes)
        if recipe_id is not None:
            parent = self._recipe_path(recipe_id)
            versions = self._versions(parent)
            if not versions:
                raise LibraryError("Choose an existing recipe before saving a new version.")
            self.load(recipe_id, versions[-1])  # do not version a corrupt authority
        else:
            recipe_id = uuid.uuid4().hex
            parent = self._recipe_path(recipe_id)
        temporary = None
        try:
            parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix=".pending-", dir=parent))
            snapshot = capture(temporary / "network.cpio")
            if not isinstance(snapshot, dict) or not snapshot.get("nodes"):
                raise LibraryError("Capture did not return an observed network.")
            clip_hash = self._clip_hash(temporary / "network.cpio")
            for _ in range(20):
                version = max(self._versions(parent), default=0) + 1
                target = self.version_path(recipe_id, version)
                record = dict(metadata, schema=SCHEMA, recipe_id=recipe_id,
                              version=version, created_utc=datetime.now(timezone.utc).isoformat(),
                              clip_sha256=clip_hash, snapshot=snapshot)
                self.codec.write(temporary / "recipe.usda", record)
                if not 0 < (temporary / "recipe.usda").stat().st_size <= self.max_manifest_bytes:
                    raise LibraryError("USD metadata exceeds the supported size, or is empty.")
                if self.codec.read(temporary / "recipe.usda") != record:
                    raise LibraryError("Saved USD metadata did not read back correctly.")
                try:
                    # A competing writer may have published this number first.
                    # Complete version directories are nonempty and never replaced.
                    temporary.rename(target)
                except FileExistsError:
                    continue
                temporary = None
                return self.load(recipe_id, version)
            raise LibraryError("This recipe is being saved elsewhere. Try again.")
        except LibraryError:
            raise
        except Exception as exc:
            raise LibraryError(f"Recipe was not saved: {exc}") from exc
        finally:
            if temporary is not None and temporary.exists():
                # Remove only this invocation's unpublished temporary directory.
                if temporary.resolve().parent == parent.resolve() and self.root in temporary.resolve().parents:
                    shutil.rmtree(temporary)

    def load(self, recipe_id, version):
        directory = self.version_path(recipe_id, version)
        manifest = directory / "recipe.usda"
        try:
            if manifest.is_symlink() or not 0 < manifest.stat().st_size <= self.max_manifest_bytes:
                raise LibraryError("USD metadata is redirected, empty, or too large.")
            record = self.codec.read(manifest)
            if not isinstance(record, dict) or record.get("schema") != SCHEMA:
                raise LibraryError("Unsupported saved-network metadata.")
            if record.get("recipe_id") != recipe_id or type(record.get("version")) is not int or record["version"] != version:
                raise LibraryError("Saved recipe identity differs from its package.")
            normalize_metadata(record.get("name"), record.get("tags"), record.get("notes"))
            created = record.get("created_utc")
            if not isinstance(created, str) or datetime.fromisoformat(created).tzinfo is None:
                raise LibraryError("Saved recipe timestamp is missing or invalid.")
            if not isinstance(record.get("snapshot"), dict) or not record["snapshot"].get("nodes"):
                raise LibraryError("The saved network inventory is missing.")
            if self._clip_hash(directory / "network.cpio") != record.get("clip_sha256"):
                raise LibraryError("The network clip changed after capture; it cannot be restored.")
            return record
        except LibraryError:
            raise
        except Exception as exc:
            raise LibraryError(f"Could not read saved recipe: {exc}") from exc

    def search(self, query="", *, all_versions=False):
        if not self.root.exists():
            return [], []
        words = str(query).casefold().split()
        entries, problems = [], []
        try:
            parents = sorted(self.root.iterdir())
        except OSError as exc:
            raise LibraryError(f"The local library could not be read: {exc}") from exc
        for parent in parents:
            if not _ID.fullmatch(parent.name):
                continue
            try:
                parent = self._recipe_path(parent.name)
                versions = self._versions(parent)
                if not all_versions:
                    versions = versions[-1:]
                for version in versions:
                    try:
                        item = self.load(parent.name, version)
                        haystack = " ".join([item["name"], item["notes"], *item["tags"]]).casefold()
                        if all(word in haystack for word in words):
                            entries.append(item)
                    except LibraryError as exc:
                        problems.append(f"{parent.name} v{version}: {exc}")
            except (LibraryError, OSError) as exc:
                problems.append(f"{parent.name}: {exc}")
        entries.sort(key=lambda item: item["created_utc"], reverse=True)
        return entries, problems
