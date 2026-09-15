"""Session-id uniqueness across ``AuditLog`` instances (salvage/scene-model).

``python/synapse/core/audit.py`` seeded the session id from ``id(self)`` and
the constructing thread's ident through ``deterministic_uuid`` -- which has
no entropy of its own (same seed, same UUID, by design). ``id()`` is only
unique among *live* objects: once an ``AuditLog`` is garbage-collected the
allocator may hand the same address to the next same-sized allocation, so
a second ``AuditLog`` built on the same thread minted the SAME session id
and every consumer keyed on it (``AuditEntry.session_id``, the
``export_session`` target filter) silently merged the two sessions.

Whether the address actually recycles is allocator-dependent (0 of 20
back-to-back rebuilds hit the same address on CPython 3.14 / Windows), so
the collision test pins ``id`` inside the audit module instead of relying
on the allocator. It fails on the ``id + thread`` seed and passes once the
seed also carries a time component and a process-wide sequence number.

The session id is read the way consumers read it -- stamped on a logged
entry and returned by ``export_session`` -- not off the private attribute.
"""

from synapse.core import audit as audit_mod
from synapse.core.audit import AuditLog


def _session_of(log: AuditLog) -> str:
    """The session id as consumers see it: stamped on a logged entry."""
    log.log("probe", "session id probe")
    exported = log.export_session()
    assert len(exported) == 1, exported
    return exported[0]["session_id"]


def test_two_live_instances_get_distinct_session_ids(tmp_path):
    """Two instances alive at once never share a session id."""
    a = AuditLog(log_dir=tmp_path / "a")
    b = AuditLog(log_dir=tmp_path / "b")
    assert _session_of(a) != _session_of(b)


def test_session_id_is_stable_within_one_instance(tmp_path):
    """The fix must not turn the SESSION id into a per-entry id."""
    log = AuditLog(log_dir=tmp_path)
    log.log("op1", "msg1")
    log.log("op2", "msg2")
    sessions = {entry["session_id"] for entry in log.export_session()}
    assert len(sessions) == 1, sessions


def test_distinct_session_ids_when_object_identity_recycles(tmp_path, monkeypatch):
    """Deterministic form of the post-GC collision.

    Pin ``id`` inside the audit module so both constructions observe the
    same object identity -- what the allocator does when it recycles the
    first instance's address -- without depending on allocator behaviour.
    Fails on master's ``id + thread`` seed; passes with the fixed seed.
    """
    monkeypatch.setattr(audit_mod, "id", lambda obj: 0xC0FFEE, raising=False)
    a = AuditLog(log_dir=tmp_path / "a")
    b = AuditLog(log_dir=tmp_path / "b")
    assert _session_of(a) != _session_of(b)
