"""Artist asset persistence: immutable versions, corruption and interrupted saves."""
import json
from pathlib import Path
import pytest

from synapse.recipes.library import SavedNetworkLibrary, LibraryError, normalize_metadata


class JsonTestCodec:
    """Pure persistence test double; real USD is qualified in the host probe."""
    def write(self, path, data):
        path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")

    def read(self, path):
        return json.loads(path.read_text(encoding="utf-8"))


def capture(path):
    path.write_bytes(b"native clip fixture")
    return {"houdini": "22.0.400", "category": "Lop", "source_scene": "shot.hip",
            "nodes": [{"name": "light", "type": "domelight::3.0"}], "dependencies": []}


@pytest.fixture
def library(tmp_path):
    return SavedNetworkLibrary(tmp_path / "recipes", JsonTestCodec())


def test_names_are_metadata_and_tags_search_unicode(library):
    saved = library.save("../Éclairage: key", [" Lookdev ", "lookdev", "HÉRO"], "Blue rim", capture)
    assert saved["tags"] == ["lookdev", "héro"]
    assert saved["name"] == "../Éclairage: key"
    entries, problems = library.search("HÉRO")
    assert len(entries) == 1 and not problems
    assert library.search("blue rim")[0][0]["recipe_id"] == saved["recipe_id"]
    assert (library.root / saved["recipe_id"]).parent == library.root


def test_explicit_versions_preserve_old_data_and_duplicate_names(library):
    first = library.save("Key", [], "first", capture)
    second = library.save("Key changed", ["night"], "second", capture, recipe_id=first["recipe_id"])
    other = library.save("Key", [], "different recipe", capture)
    assert [first["version"], second["version"], other["version"]] == [1, 2, 1]
    assert library.load(first["recipe_id"], 1)["notes"] == "first"
    assert library.load(first["recipe_id"], 2)["notes"] == "second"
    assert len(library.search()[0]) == 2
    assert len(library.search(all_versions=True)[0]) == 3


@pytest.mark.parametrize("name,tags,notes", [("", [], ""), ("x", [1], ""), ("x", "tag", ""), ("x", [], None), ("x" * 121, [], ""), ("x", ["a" * 41], "")])
def test_invalid_metadata_has_no_write(library, name, tags, notes):
    with pytest.raises(LibraryError):
        library.save(name, tags, notes, capture)
    assert not library.root.exists()


def test_failed_capture_never_publishes_and_preserves_prior_version(library):
    first = library.save("A", [], "", capture)
    def broken(path):
        path.write_bytes(b"half-written")
        raise OSError("disk unavailable")
    with pytest.raises(LibraryError, match="disk unavailable"):
        library.save("A", [], "", broken, recipe_id=first["recipe_id"])
    entries, problems = library.search(all_versions=True)
    assert len(entries) == 1 and not problems
    assert list((library.root / first["recipe_id"]).iterdir()) == [library.version_path(first["recipe_id"], 1)]


def test_corrupt_clip_is_reported_and_cannot_restore(library):
    saved = library.save("A", [], "", capture)
    (library.version_path(saved["recipe_id"], 1) / "network.cpio").write_bytes(b"changed")
    with pytest.raises(LibraryError, match="changed"):
        library.load(saved["recipe_id"], 1)
    entries, problems = library.search()
    assert not entries and len(problems) == 1 and "changed" in problems[0]


def test_corrupt_latest_is_not_silently_presented_as_latest(library):
    saved = library.save("A", [], "", capture)
    library.save("A", [], "new", capture, recipe_id=saved["recipe_id"])
    (library.version_path(saved["recipe_id"], 2) / "recipe.usda").write_text("broken")
    entries, problems = library.search()
    assert not entries and len(problems) == 1
    assert library.load(saved["recipe_id"], 1)["version"] == 1


@pytest.mark.parametrize("identifier,version", [("../elsewhere", 1), ("A" * 32, 1), ("0" * 32, True), ("0" * 32, 0)])
def test_untrusted_identity_cannot_escape_library(library, identifier, version):
    with pytest.raises(LibraryError):
        library.load(identifier, version)


def test_versioning_missing_recipe_is_an_error(library):
    with pytest.raises(LibraryError, match="existing"):
        library.save("A", [], "", capture, recipe_id="0" * 32)
    assert not library.root.exists()


def test_manifest_identity_cannot_substitute_a_different_package(library):
    saved = library.save("A", [], "", capture)
    path = library.version_path(saved["recipe_id"], 1) / "recipe.usda"
    manifest = json.loads(path.read_text())
    manifest["recipe_id"] = "0" * 32
    path.write_text(json.dumps(manifest))
    with pytest.raises(LibraryError, match="identity"):
        library.load(saved["recipe_id"], 1)


def test_oversized_clip_is_not_published(library):
    library.max_clip_bytes = 8
    with pytest.raises(LibraryError, match="size"):
        library.save("A", [], "", capture)
    assert library.search() == ([], [])


def test_oversized_metadata_is_not_published_or_allowed_to_poison_next_version(library):
    first = library.save("A", [], "first", capture)
    library.max_manifest_bytes = (library.version_path(first["recipe_id"], 1) / "recipe.usda").stat().st_size + 40
    with pytest.raises(LibraryError, match="metadata"):
        library.save("A", [], "second" * 100, capture, recipe_id=first["recipe_id"])
    library.max_manifest_bytes = 4 * 1024 * 1024
    assert library._versions(library.root / first["recipe_id"]) == [1]
    second = library.save("A", [], "retry", capture, recipe_id=first["recipe_id"])
    assert second["version"] == 2


def test_missing_timestamp_is_an_entry_problem_not_a_search_crash(library):
    broken = library.save("Broken", [], "", capture)
    healthy = library.save("Healthy", [], "", capture)
    path = library.version_path(broken["recipe_id"], 1) / "recipe.usda"
    data = json.loads(path.read_text())
    del data["created_utc"]
    path.write_text(json.dumps(data))
    entries, problems = library.search()
    assert [item["recipe_id"] for item in entries] == [healthy["recipe_id"]]
    assert len(problems) == 1
