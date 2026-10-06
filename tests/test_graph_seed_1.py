"""handlers_memory must define a module-level logger (its sleep-pass fallback logs)."""
import logging

from synapse.server import handlers_memory


def test_handlers_memory_has_logger():
    assert isinstance(getattr(handlers_memory, "logger", None), logging.Logger)
