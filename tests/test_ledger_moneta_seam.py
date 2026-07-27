"""The Ledger -> Moneta deposit seam, and the Moneta revision provenance.

Two defects, verified 2026-07-26, pinned here:

  1. ``ledger._deposit_to_moneta`` was a hardcoded ``return None`` stub carrying
     ``# pragma: no cover``. Ledger records never reached Moneta, and the pragma
     guaranteed no test could ever notice. The comment claimed "default-off" but
     there was no flag to turn it on.
  2. ``$MONETA_SRC`` points at a live git worktree, so the memory substrate was
     "whatever branch is checked out". ``moneta_provenance()`` reported a path
     and a useless version string (``importlib.metadata`` reports ``1.2.0rc1``
     for rc1/rc2/rc2+N alike, and reports NOTHING at all for a path-injected
     copy), but never the commit.

Every pin here is written to the R34 mutation standard: it must FAIL against a
deliberately broken implementation. The mutations each pin catches are named in
its docstring, so a future reader can re-run the battery instead of trusting it.

Run: python -m pytest tests/test_ledger_moneta_seam.py -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.memory import ledger
from synapse.memory import moneta_runtime as mr

FAKE_SHA = "0123456789abcdef0123456789abcdef01234567"
OTHER_SHA = "fedcba9876543210fedcba9876543210fedcba98"

moneta_required = pytest.mark.skipif(
    not mr.moneta_available(),
    reason="Moneta is not importable in this environment (adapter guard, not a stub)",
)


# ═════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════


@pytest.fixture
def seam_tmp(monkeypatch):
    """A throwaway ledger root with the process-wide Moneta store reset around it.

    The store holds a Moneta single-owner URI lock and an open snapshot file, so
    it MUST be closed before the directory is removed or Windows refuses.
    """
    d = tempfile.mkdtemp(prefix="synapse_seam_test_")
    monkeypatch.setenv("SYNAPSE_LEDGER_DIR", d)
    ledger.reset_moneta_store()
    yield d
    ledger.reset_moneta_store()
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def moneta_on(monkeypatch):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")


@pytest.fixture
def moneta_off(monkeypatch):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")


@pytest.fixture
def clean_revision_cache():
    mr.reset_revision_cache()
    yield
    mr.reset_revision_cache()


def _record(**overrides):
    kwargs = dict(
        kind="Confirmation",
        verified_by="V1_cook",
        against_build="22.0.368",
        title="the seam deposits",
        timestamp="2026-07-26T12:00:00Z",
        notes="a verified finding",
        probe=["moneta_available"],
    )
    kwargs.update(overrides)
    return ledger.LedgerRecord(**kwargs)


def _make_git_worktree(root, *, head="ref: refs/heads/main", loose=None,
                       packed=None, gitdir_file=False, commondir=None):
    """Build a synthetic package root with git metadata. Returns the module file."""
    pkg = os.path.join(root, "moneta")
    os.makedirs(pkg, exist_ok=True)
    with open(os.path.join(pkg, "__init__.py"), "w", encoding="utf-8") as fh:
        fh.write("# synthetic\n")

    if gitdir_file:
        real_git = os.path.join(root, "_realgit")
        os.makedirs(real_git, exist_ok=True)
        with open(os.path.join(root, ".git"), "w", encoding="utf-8") as fh:
            fh.write(f"gitdir: {real_git}\n")
        git_dir = real_git
    else:
        git_dir = os.path.join(root, ".git")
        os.makedirs(git_dir, exist_ok=True)

    with open(os.path.join(git_dir, "HEAD"), "w", encoding="utf-8") as fh:
        fh.write(head + "\n")

    ref_home = git_dir
    if commondir is not None:
        os.makedirs(commondir, exist_ok=True)
        with open(os.path.join(git_dir, "commondir"), "w", encoding="utf-8") as fh:
            fh.write(commondir + "\n")
        ref_home = commondir

    if loose:
        ref_path = os.path.join(ref_home, "refs", "heads")
        os.makedirs(ref_path, exist_ok=True)
        with open(os.path.join(ref_path, "main"), "w", encoding="utf-8") as fh:
            fh.write(loose + "\n")
    if packed:
        with open(os.path.join(ref_home, "packed-refs"), "w", encoding="utf-8") as fh:
            fh.write("# pack-refs with: peeled fully-peeled sorted\n")
            fh.write(f"{packed} refs/heads/main\n")
            fh.write("^aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")

    return os.path.join(pkg, "__init__.py")


# ═════════════════════════════════════════════════════════════════
# Defect 1 — the seam is live
# ═════════════════════════════════════════════════════════════════


class TestSeamIsLive:

    @moneta_required
    def test_record_lands_in_moneta_when_backend_on(self, seam_tmp, moneta_on):
        """MUTATION CAUGHT: ``_deposit_to_moneta`` returning None early (the
        shipped stub) leaves count()==0 and no reachable memory."""
        rec = _record()
        res = ledger.deposit(rec)

        assert res["moneta"]["deposited"] is True, res["moneta"]["reason"]

        store = ledger.ledger_moneta_store()
        assert store is not None
        assert store.count() == 1

        memories = store.all()
        assert len(memories) == 1
        memory = memories[0]
        # The memory points back at the source-of-truth file (D-1).
        assert f"{res['stem']}.json" in memory.content
        assert "the seam deposits" in memory.content
        assert memory.source == "ledger"
        assert "ledger" in memory.tags
        assert res["moneta"]["memory_id"] == memory.id

    @moneta_required
    def test_deposited_finding_is_recallable_by_keyword(self, seam_tmp, moneta_on):
        """A finding that lands but cannot be found again is archived, not
        remembered. MUTATION CAUGHT: dropping content/keywords from the
        projected Memory (search returns nothing)."""
        from synapse.memory.models import MemoryQuery

        ledger.deposit(_record(title="karma xpu denoiser probe"))
        store = ledger.ledger_moneta_store()

        hits = store.search(MemoryQuery(text="denoiser", limit=10))
        assert len(hits) == 1
        assert "denoiser" in hits[0].memory.content.lower()

    @moneta_required
    def test_findings_resist_the_sleep_pass(self, seam_tmp, moneta_on):
        """Verified findings are an append-only audit trail: a sleep pass must
        not decay them away. MUTATION CAUGHT: projecting at a lower tier, which
        drops the protected floor to 0.0 and makes the record prunable."""
        from synapse.memory.moneta_store import MonetaBackedStore

        ledger.deposit(_record())
        store = ledger.ledger_moneta_store()
        memory = store.all()[0]
        assert MonetaBackedStore._is_protected(store, memory) is True

    def test_file_write_survives_moneta_unavailable(self, seam_tmp, moneta_on, monkeypatch):
        """FILE FIRST is unconditional. MUTATION CAUGHT: making the file write
        conditional on Moneta, or letting an unavailable substrate raise."""
        monkeypatch.setattr(mr, "moneta_available", lambda: False)
        monkeypatch.setattr(mr, "import_error", lambda: "ModuleNotFoundError: moneta")

        rec = _record()
        res = ledger.deposit(rec)  # must not raise

        assert res["ok"] is True
        assert res["moneta"]["deposited"] is False
        assert res["moneta"]["reason"].startswith("unavailable")

        path = os.path.join(seam_tmp, res["filename"])
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as fh:
            assert json.load(fh)["title"] == "the seam deposits"
        # No substrate was touched.
        assert not os.path.isdir(os.path.join(seam_tmp, ".moneta"))

    def test_backend_off_is_a_declared_noop(self, seam_tmp, moneta_off):
        """Choosing jsonl must actually turn the Moneta writer off, and must SAY
        so. MUTATION CAUGHT: gating on availability alone (reason becomes
        'deposited' and a .moneta store appears under a jsonl backend)."""
        res = ledger.deposit(_record())

        assert res["ok"] is True
        assert res["moneta"]["deposited"] is False
        assert res["moneta"]["reason"] == "backend-off"
        assert ledger.ledger_moneta_store() is None
        assert not os.path.isdir(os.path.join(seam_tmp, ".moneta"))

    def test_moneta_failure_never_escapes_deposit(self, seam_tmp, moneta_on, monkeypatch):
        """MUTATION CAUGHT: letting a substrate error propagate out of deposit()
        (which would take the source-of-truth file write down with it)."""
        def boom():
            raise RuntimeError("URI lock held by another owner")

        monkeypatch.setattr(mr, "moneta_available", lambda: True)
        monkeypatch.setattr(ledger, "ledger_moneta_store", boom)

        res = ledger.deposit(_record())

        assert res["ok"] is True
        assert res["moneta"]["deposited"] is False
        assert res["moneta"]["reason"].startswith("error: RuntimeError")
        assert os.path.exists(os.path.join(seam_tmp, res["filename"]))

    def test_add_failure_is_reported_not_swallowed(self, seam_tmp, moneta_on, monkeypatch):
        """A failed substrate write must never read as a success. MUTATION
        CAUGHT: `except Exception: pass` around the deposit (Law 3)."""
        class Exploding:
            def add(self, memory):
                raise IOError("disk full")

        monkeypatch.setattr(mr, "moneta_available", lambda: True)
        monkeypatch.setattr(ledger, "ledger_moneta_store", lambda: Exploding())

        res = ledger.deposit(_record())

        assert res["ok"] is True
        assert res["moneta"]["deposited"] is False
        assert "OSError" in res["moneta"]["reason"] or "IOError" in res["moneta"]["reason"]

    def test_every_deposit_reports_a_moneta_status(self, seam_tmp, monkeypatch):
        """The caller is never required to read prose to learn what happened.
        MUTATION CAUGHT: returning None / omitting the key in any mode."""
        for backend in ("jsonl", "moneta", "not-a-backend"):
            monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", backend)
            ledger.reset_moneta_store()
            res = ledger.deposit(_record(title=f"mode {backend}"))
            status = res["moneta"]
            assert isinstance(status, dict)
            assert set(status) >= {"deposited", "reason", "memory_id", "provenance"}
            assert isinstance(status["deposited"], bool)
            assert status["reason"]
        ledger.reset_moneta_store()

    def test_the_shadow_backend_also_enables_the_seam(self, seam_tmp, monkeypatch):
        """`shadow` is in MONETA_BACKENDS but no pin exercised it — a live
        branch with no coverage. MUTATION CAUGHT: narrowing MONETA_BACKENDS to
        ("moneta",)."""
        for value, expected in (("moneta", True), ("shadow", True), ("SHADOW", True),
                                (" shadow ", True), ("jsonl", False), ("", False),
                                ("sqlite", False)):
            monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", value)
            assert ledger.moneta_backend_enabled() is expected, value

    def test_deposited_never_claims_durability(self, seam_tmp, monkeypatch):
        """MonetaBackedStore.add() writes in-memory; the snapshot happens at
        close/atexit, so a hard exit loses the row. `deposited` reports
        acceptance and `durable` reports durability — two fields, not one field
        and a footnote. MUTATION CAUGHT: setting durable True on accept."""
        monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
        res = ledger.deposit(_record())
        status = res["moneta"]
        assert status["durable"] is False
        assert "hard exit" in status["durability"]
        # The durable copy exists and is the file.
        assert os.path.exists(os.path.join(seam_tmp, res["filename"]))

    @moneta_required
    def test_redeposit_appends_and_is_not_claimed_as_unique(self, seam_tmp, moneta_on):
        """Moneta is append-only with no dedup key. Depositing the same finding
        twice yields ONE file and TWO rows sharing a Memory.id. Pinned as known
        behaviour rather than discovered in production. MUTATION CAUGHT: a
        claim of substrate-side idempotence."""
        first = ledger.deposit(_record())
        second = ledger.deposit(_record())

        assert first["stem"] == second["stem"]
        records = [f for f in os.listdir(seam_tmp) if f.endswith(".json")]
        assert records == [f"{first['stem']}.json"]

        store = ledger.ledger_moneta_store()
        assert store.count() == 2, "append-only: expected a duplicate row"
        assert first["moneta"]["memory_id"] == second["moneta"]["memory_id"]

    def test_seam_carries_no_coverage_pragma(self):
        """A seam that cannot be covered cannot be verified. MUTATION CAUGHT:
        re-adding `# pragma: no cover` to the hook (the exact mechanism that
        hid this defect)."""
        source = open(ledger.__file__, encoding="utf-8").read()
        seam_start = source.index("def _deposit_to_moneta")
        seam_end = source.index("def deposit(", seam_start)
        assert "pragma: no cover" not in source[seam_start:seam_end]
        assert "return None" not in source[seam_start:seam_end]


# ═════════════════════════════════════════════════════════════════
# Defect 2 — the substrate revision is recorded
# ═════════════════════════════════════════════════════════════════


class TestRevisionProvenance:

    def test_resolves_sha_from_a_loose_ref(self, tmp_path, clean_revision_cache):
        """MUTATION CAUGHT: revision left as None (the shipped behaviour)."""
        pkg_file = _make_git_worktree(str(tmp_path / "src"), loose=FAKE_SHA)
        got = mr._resolve_revision(pkg_file)
        assert got["revision"] == FAKE_SHA
        assert got["revision_ref"] == "refs/heads/main"
        assert got["revision_source"] == "git-loose-ref"
        assert got["root"] == os.path.abspath(str(tmp_path / "src"))

    def test_resolves_sha_from_packed_refs(self, tmp_path, clean_revision_cache):
        """A freshly-cloned or gc'd repo has no loose ref file. MUTATION CAUGHT:
        reading only refs/heads/<branch>."""
        pkg_file = _make_git_worktree(str(tmp_path / "src"), packed=FAKE_SHA)
        got = mr._resolve_revision(pkg_file)
        assert got["revision"] == FAKE_SHA
        assert got["revision_source"] == "git-packed-refs"

    def test_resolves_a_detached_head(self, tmp_path, clean_revision_cache):
        """MUTATION CAUGHT: assuming HEAD is always a symbolic ref."""
        pkg_file = _make_git_worktree(str(tmp_path / "src"), head=FAKE_SHA)
        got = mr._resolve_revision(pkg_file)
        assert got["revision"] == FAKE_SHA
        assert got["revision_source"] == "git-head-detached"

    def test_resolves_a_linked_worktree(self, tmp_path, clean_revision_cache):
        """A linked worktree stores `.git` as a FILE and delegates refs via
        commondir — the shape SYNAPSE itself uses. MUTATION CAUGHT: handling
        only a `.git` directory, or ignoring commondir."""
        root = str(tmp_path / "src")
        common = str(tmp_path / "common")
        pkg_file = _make_git_worktree(root, gitdir_file=True, loose=FAKE_SHA,
                                      commondir=common)
        got = mr._resolve_revision(pkg_file)
        assert got["revision"] == FAKE_SHA
        assert got["revision_source"] == "git-loose-ref"

    def test_non_git_install_reports_honestly(self, tmp_path, clean_revision_cache):
        """A pip-installed copy has no revision, and must say None + why —
        never a fabricated or inherited SHA. MUTATION CAUGHT: falling back to
        some other repo's HEAD by walking too far up."""
        pkg = tmp_path / "site-packages" / "moneta"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("# pip copy\n", encoding="utf-8")
        got = mr._resolve_revision(str(pkg / "__init__.py"))
        assert got["revision"] is None
        assert got["revision_source"] == "not-a-git-worktree"

    def test_installed_copy_never_inherits_an_enclosing_repo_sha(
        self, tmp_path, clean_revision_cache
    ):
        """Moneta pip-installed into a venv INSIDE some other git repo must not
        report that repo's HEAD as the Moneta revision. A wrong SHA is worse
        than no SHA, because it is trusted. MUTATION CAUGHT: dropping the
        site-packages guard (found by the mutation battery, not by review)."""
        repo = tmp_path / "some-other-repo"
        git_dir = repo / ".git"
        (git_dir / "refs" / "heads").mkdir(parents=True)
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (git_dir / "refs" / "heads" / "main").write_text(OTHER_SHA + "\n", encoding="utf-8")

        # site-packages sitting ONE level under the repo root — i.e. inside the
        # walk bound, so the marker guard is the only thing standing between an
        # installed copy and a fabricated SHA. A deeper .venv/Lib/site-packages
        # layout is out of range of the bound anyway, which would make this pin
        # pass whether or not the guard existed (the mutation battery caught
        # exactly that vacuity, 2026-07-26).
        pkg = repo / "site-packages" / "moneta"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("# installed copy\n", encoding="utf-8")

        got = mr._resolve_revision(str(pkg / "__init__.py"))
        assert got["revision"] is None, "inherited an unrelated repo's SHA"
        assert got["revision_source"] == "not-a-git-worktree"
        assert got["revision_repo"] is None

    def test_walk_upward_is_bounded(self, tmp_path, clean_revision_cache):
        """A nested copy must not reach an unrelated repo above it. MUTATION
        CAUGHT: removing MAX_REVISION_WALK."""
        repo = tmp_path / "outer"
        git_dir = repo / ".git"
        (git_dir / "refs" / "heads").mkdir(parents=True)
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (git_dir / "refs" / "heads" / "main").write_text(OTHER_SHA + "\n", encoding="utf-8")

        deep = repo.joinpath(*[f"d{i}" for i in range(mr.MAX_REVISION_WALK + 2)], "moneta")
        deep.mkdir(parents=True)
        (deep / "__init__.py").write_text("# vendored deep\n", encoding="utf-8")

        got = mr._resolve_revision(str(deep / "__init__.py"))
        assert got["revision"] is None
        assert got["revision_source"] == "not-a-git-worktree"

    def test_vendored_copy_does_not_inherit_the_host_repo_sha(
        self, tmp_path, clean_revision_cache
    ):
        """The site-packages guard alone made this class READ closed while it
        was open: a plain vendored copy is not under site-packages, and at the
        old bound of 3 it inherited the host repo's HEAD. MUTATION CAUGHT:
        widening MAX_REVISION_WALK back past 1. (CRUCIBLE blocker, 2026-07-26.)"""
        repo = tmp_path / "host-repo"
        git_dir = repo / ".git"
        (git_dir / "refs" / "heads").mkdir(parents=True)
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (git_dir / "refs" / "heads" / "main").write_text(OTHER_SHA + "\n", encoding="utf-8")

        pkg = repo / "vendor" / "moneta-src" / "moneta"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("# vendored\n", encoding="utf-8")

        got = mr._resolve_revision(str(pkg / "__init__.py"))
        assert got["revision"] is None, "inherited the host repo's SHA"
        assert got["revision_repo"] is None

    def test_the_deployed_layout_still_resolves(self, tmp_path, clean_revision_cache):
        """Tightening the bound must not break the layout that matters:
        $MONETA_SRC=<repo>/src. Positive control for the bound — without it,
        the previous pin passes trivially at MAX_REVISION_WALK=0."""
        repo = tmp_path / "Moneta"
        git_dir = repo / ".git"
        (git_dir / "refs" / "heads").mkdir(parents=True)
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (git_dir / "refs" / "heads" / "main").write_text(FAKE_SHA + "\n", encoding="utf-8")

        pkg = repo / "src" / "moneta"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("# deployed layout\n", encoding="utf-8")

        got = mr._resolve_revision(str(pkg / "__init__.py"))
        assert got["revision"] == FAKE_SHA
        assert got["revision_repo"] == str(repo)

    def test_resolution_stamps_when_it_read_the_disk(self, tmp_path, clean_revision_cache):
        """The cache is permanent, so staleness must be visible rather than
        inferred. MUTATION CAUGHT: dropping revision_resolved_at."""
        pkg_file = _make_git_worktree(str(tmp_path / "src"), loose=FAKE_SHA)
        got = mr._resolve_revision(pkg_file)
        assert got["revision_resolved_at"]
        assert got["revision_resolved_at"].endswith("Z")
        # The stamp is cached with the resolution — it dates the READ, not the call.
        assert mr._resolve_revision(pkg_file)["revision_resolved_at"] == \
            got["revision_resolved_at"]

    def test_version_lookup_is_cached(self, monkeypatch, clean_revision_cache):
        """moneta_provenance() is on the per-deposit path;
        importlib.metadata.version() scans distribution metadata per call.
        MUTATION CAUGHT: calling _md.version() inline on every provenance."""
        import importlib.metadata as md

        calls = []
        real = md.version

        def counted(name):
            calls.append(name)
            return real(name)

        monkeypatch.setattr(md, "version", counted)
        mr._dist_version()
        mr._dist_version()
        mr._dist_version()
        assert len(calls) <= 1, f"version() called {len(calls)}x; expected at most 1"

    def test_unresolvable_ref_is_named_not_guessed(self, tmp_path, clean_revision_cache):
        """HEAD points at a branch with no ref file anywhere. MUTATION CAUGHT:
        reporting success with revision None."""
        pkg_file = _make_git_worktree(str(tmp_path / "src"))  # HEAD, no refs
        got = mr._resolve_revision(pkg_file)
        assert got["revision"] is None
        assert got["revision_source"] == "unresolved-ref"

    def test_revision_is_cached_not_reread(self, tmp_path, clean_revision_cache):
        """'do not shell out on every call, cache it'. MUTATION CAUGHT: removing
        the cache — the second call would pick up the rewritten ref."""
        root = str(tmp_path / "src")
        pkg_file = _make_git_worktree(root, loose=FAKE_SHA)
        first = mr._resolve_revision(pkg_file)
        assert first["revision"] == FAKE_SHA

        # Move the branch on disk. A cached resolution must not notice.
        with open(os.path.join(root, ".git", "refs", "heads", "main"), "w",
                  encoding="utf-8") as fh:
            fh.write(OTHER_SHA + "\n")

        assert mr._resolve_revision(pkg_file)["revision"] == FAKE_SHA
        mr.reset_revision_cache()
        assert mr._resolve_revision(pkg_file)["revision"] == OTHER_SHA

    def test_resolution_never_shells_out(self, tmp_path, clean_revision_cache, monkeypatch):
        """`git` is not always on PATH, and a subprocess per deposit is a real
        cost. MUTATION CAUGHT: implementing this with subprocess."""
        def forbidden(*args, **kwargs):
            raise AssertionError("revision resolution must not spawn a subprocess")

        for name in ("run", "Popen", "check_output", "call", "check_call"):
            monkeypatch.setattr(subprocess, name, forbidden)
        monkeypatch.setattr(os, "system", forbidden)

        pkg_file = _make_git_worktree(str(tmp_path / "src"), loose=FAKE_SHA)
        assert mr._resolve_revision(pkg_file)["revision"] == FAKE_SHA

    def test_provenance_declares_what_the_sha_does_not_cover(self):
        """$MONETA_SRC is a working directory: a SHA pins committed state only.
        MUTATION CAUGHT: dropping the caveat and letting a reader infer the
        revision fully pins the substrate."""
        assert "uncommitted" in mr.REVISION_SCOPE
        prov = mr.moneta_provenance()
        assert prov["revision_scope"] == mr.REVISION_SCOPE
        # Shape is stable whether or not Moneta is importable.
        assert set(prov) >= {"available", "version", "file", "root", "revision",
                             "revision_ref", "revision_source", "revision_scope",
                             "moneta_src", "import_error"}

    def test_provenance_survives_a_missing_package_file(self, clean_revision_cache):
        """MUTATION CAUGHT: raising on a namespace package with no __file__."""
        got = mr._resolve_revision(None)
        assert got["revision"] is None
        assert got["revision_source"] == "no-package-file"


# ═════════════════════════════════════════════════════════════════
# The join — provenance reaches the deposit
# ═════════════════════════════════════════════════════════════════


class TestProvenanceReachesTheDeposit:

    @moneta_required
    def test_deposit_metadata_carries_the_revision(self, seam_tmp, moneta_on, monkeypatch):
        """Any memory written must be traceable to the Moneta revision that
        wrote it. MUTATION CAUGHT: dropping provenance from the deposit result."""
        real = mr.moneta_provenance

        def stamped():
            prov = real()
            prov["revision"] = FAKE_SHA
            prov["revision_ref"] = "refs/heads/main"
            prov["revision_source"] = "git-loose-ref"
            return prov

        monkeypatch.setattr(mr, "moneta_provenance", stamped)
        res = ledger.deposit(_record())

        prov = res["moneta"]["provenance"]
        assert prov["revision"] == FAKE_SHA
        assert prov["revision_ref"] == "refs/heads/main"
        assert prov["revision_scope"] == mr.REVISION_SCOPE
        assert prov["file"]

    @moneta_required
    def test_the_memory_itself_carries_the_revision(self, seam_tmp, moneta_on, monkeypatch):
        """The deposit result is ephemeral; the trace has to survive the process
        that produced it. MUTATION CAUGHT: recording the revision only in the
        return value."""
        real = mr.moneta_provenance

        def stamped():
            prov = real()
            prov["revision"] = FAKE_SHA
            return prov

        monkeypatch.setattr(mr, "moneta_provenance", stamped)
        ledger.deposit(_record())

        memory = ledger.ledger_moneta_store().all()[0]
        assert f"moneta_rev:{FAKE_SHA[:12]}" in memory.tags

    def test_provenance_is_reported_even_when_the_deposit_fails(
        self, seam_tmp, moneta_on, monkeypatch
    ):
        """A failed write is exactly when you want to know which substrate you
        were talking to. MUTATION CAUGHT: populating provenance only on success."""
        monkeypatch.setattr(mr, "moneta_available", lambda: True)
        monkeypatch.setattr(ledger, "ledger_moneta_store",
                            lambda: (_ for _ in ()).throw(RuntimeError("nope")))

        res = ledger.deposit(_record())
        assert res["moneta"]["deposited"] is False
        assert res["moneta"]["provenance"] is not None
        assert "revision_scope" in res["moneta"]["provenance"]

    @moneta_required
    def test_backfill_reports_substrate_outcomes(self, seam_tmp, moneta_on, tmp_path):
        """A status nobody reads is the same defect as a stub nobody calls.
        backfill() discarded deposit()'s result entirely, so a substrate leg
        failing on EVERY record still reported a clean 'N files written'.
        MUTATION CAUGHT: dropping the moneta counters from backfill's return."""
        md = tmp_path / "ledger.md"
        md.write_text(
            "## Session 2026-07-26 — seam\n\n"
            "### Confirmation — first finding\n"
            "- **verified_by:** V1_cook\n"
            "- **against_build:** 22.0.368\n"
            "- **ts:** 2026-07-26T10:00:00Z\n\n"
            "### Confirmation — second finding\n"
            "- **verified_by:** V1_cook\n"
            "- **against_build:** 22.0.368\n"
            "- **ts:** 2026-07-26T11:00:00Z\n",
            encoding="utf-8",
        )
        summary = ledger.backfill(str(md))

        assert summary["files_written"] == 2
        assert summary["moneta_deposited"] == 2
        assert summary["moneta_failures"] == []

    def test_backfill_surfaces_a_broken_substrate(self, seam_tmp, moneta_on, tmp_path,
                                                  monkeypatch):
        """The counter has to be able to report BAD news, or it is decoration.
        MUTATION CAUGHT: hardcoding moneta_deposited to the record count."""
        monkeypatch.setattr(mr, "moneta_available", lambda: True)
        monkeypatch.setattr(ledger, "ledger_moneta_store",
                            lambda: (_ for _ in ()).throw(RuntimeError("substrate down")))
        md = tmp_path / "ledger.md"
        md.write_text(
            "## Session 2026-07-26 — seam\n\n"
            "### Confirmation — a finding\n"
            "- **verified_by:** V1_cook\n"
            "- **against_build:** 22.0.368\n"
            "- **ts:** 2026-07-26T10:00:00Z\n",
            encoding="utf-8",
        )
        summary = ledger.backfill(str(md))

        assert summary["files_written"] == 1      # the contract still held
        assert summary["moneta_deposited"] == 0
        assert len(summary["moneta_failures"]) == 1
        assert "substrate down" in summary["moneta_failures"][0]

    @moneta_required
    def test_the_science_sink_reports_substrate_outcomes(self, seam_tmp, moneta_on):
        """science/deposit.py is the ONLY live producer of ledger records and it
        discarded deposit()'s return value. MUTATION CAUGHT: dropping the
        moneta counters from LedgerDeposit."""
        from synapse.science.deposit import LedgerDeposit

        sink = LedgerDeposit()
        sink({"surface": "hou.Node.cook", "status": "champion",
              "detail": "exists", "timestamp": 1785000000})

        assert sink.deposited == 1
        assert sink.moneta_deposited == 1
        assert sink.moneta_failures == []

    def test_the_science_sink_surfaces_a_broken_substrate(self, seam_tmp, moneta_on,
                                                          monkeypatch):
        """MUTATION CAUGHT: counting moneta successes unconditionally."""
        from synapse.science.deposit import LedgerDeposit

        monkeypatch.setattr(mr, "moneta_available", lambda: True)
        monkeypatch.setattr(ledger, "ledger_moneta_store",
                            lambda: (_ for _ in ()).throw(RuntimeError("substrate down")))
        sink = LedgerDeposit()
        sink({"surface": "hou.Node.cook", "status": "champion",
              "detail": "exists", "timestamp": 1785000000})

        assert sink.deposited == 1                 # the file still landed
        assert sink.moneta_deposited == 0
        assert len(sink.moneta_failures) == 1

    @moneta_required
    def test_record_identity_is_independent_of_the_substrate(self, seam_tmp, moneta_on,
                                                             monkeypatch):
        """The per-record filename is a content hash. If substrate provenance
        leaked INTO the record, the same finding would land under different
        filenames on different machines and idempotent dedup (RFC §11.3) would
        break. MUTATION CAUGHT: stamping the revision into rec.extra."""
        real = mr.moneta_provenance

        def rev_a():
            prov = real(); prov["revision"] = FAKE_SHA; return prov

        def rev_b():
            prov = real(); prov["revision"] = OTHER_SHA; return prov

        monkeypatch.setattr(mr, "moneta_provenance", rev_a)
        first = ledger.deposit(_record())
        monkeypatch.setattr(mr, "moneta_provenance", rev_b)
        second = ledger.deposit(_record())

        assert first["stem"] == second["stem"]
        # Exactly ONE record file, not one per substrate revision. (write_report
        # keeps a .bak.N of the overwritten copy — that is the backup policy,
        # not a second record.)
        records = [f for f in os.listdir(seam_tmp) if f.endswith(".json")]
        assert records == [f"{first['stem']}.json"]
