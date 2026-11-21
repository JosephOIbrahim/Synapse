"""The custody ledger's deposit must not inherit the R-033 convergence.

The ledger is append-only by contract: depositing the same finding twice
yields two rows sharing a Memory.id (pinned by
test_ledger_moneta_seam::test_redeposit_appends_and_is_not_claimed_as_unique,
which only runs where Moneta is importable). This test pins the seam's side
of that contract without the backend.
"""
import types


def test_ledger_deposit_asks_the_store_to_allow_a_duplicate_identity(monkeypatch):
    from synapse.memory import ledger
    import synapse.memory.moneta_runtime as mr

    calls = {}

    class FakeStore:
        def add(self, memory, **kwargs):
            calls.update(kwargs)
            calls["memory_id"] = memory.id
            return memory.id

    monkeypatch.setattr(ledger, "moneta_backend_enabled", lambda: True)
    monkeypatch.setattr(ledger, "ledger_moneta_store", lambda: FakeStore())
    monkeypatch.setattr(ledger, "_ledger_memory",
                        lambda rec, stem, revision: types.SimpleNamespace(id="mem-1"))
    monkeypatch.setattr(mr, "moneta_available", lambda: True)
    monkeypatch.setattr(mr, "moneta_provenance", lambda: {})

    status = ledger._deposit_to_moneta(types.SimpleNamespace(), "stem-1")

    assert status["deposited"] is True
    assert status["reason"] == "deposited"
    assert calls.get("allow_duplicate_identity") is True
