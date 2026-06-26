"""Regression test for the daemon's forward-compatible loop selection.

``SynapseDaemon._apply_event_loop_policy`` used to call the global
``asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())``,
which is deprecation-warned on Python 3.12+ and slated for removal in
3.16. This pins the modernized form: it must still yield a
``SelectorEventLoop`` on Windows, emit no ``DeprecationWarning``, and
no-op off-Windows.
"""

from __future__ import annotations

import asyncio
import sys
import warnings

import pytest


def _make_daemon():
    from synapse.host.daemon import SynapseDaemon

    return SynapseDaemon(api_key="test", boot_gate=False)


def test_apply_event_loop_policy_emits_no_deprecation_warning():
    """The selection must not trip the asyncio policy deprecations."""
    daemon = _make_daemon()
    try:
        prior = asyncio.get_event_loop()
    except RuntimeError:
        prior = None
    created = None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            daemon._apply_event_loop_policy()
        if sys.platform == "win32":
            created = asyncio.get_event_loop()
    finally:
        if created is not None and created is not prior:
            created.close()
        asyncio.set_event_loop(prior)


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Selector-loop forcing only applies on Windows",
)
def test_apply_event_loop_policy_installs_selector_loop_on_windows():
    """On Windows the daemon must own a (non-closed) SelectorEventLoop."""
    daemon = _make_daemon()
    try:
        prior = asyncio.get_event_loop()
    except RuntimeError:
        prior = None
    loop = None
    try:
        daemon._apply_event_loop_policy()
        loop = asyncio.get_event_loop()
        assert isinstance(loop, asyncio.SelectorEventLoop)
        assert not loop.is_closed()
    finally:
        if loop is not None and loop is not prior:
            loop.close()
        asyncio.set_event_loop(prior)


def test_apply_event_loop_policy_noop_off_windows(monkeypatch):
    """Off Windows the method must not touch the event loop binding."""
    if sys.platform == "win32":
        pytest.skip("Behaviour under test is the non-Windows branch")
    monkeypatch.setattr(sys, "platform", "linux")
    daemon = _make_daemon()
    try:
        prior = asyncio.get_event_loop()
    except RuntimeError:
        prior = None
    try:
        daemon._apply_event_loop_policy()
        try:
            after = asyncio.get_event_loop()
        except RuntimeError:
            after = None
        assert after is prior
    finally:
        asyncio.set_event_loop(prior)
