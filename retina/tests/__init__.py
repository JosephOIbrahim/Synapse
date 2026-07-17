"""RETINA worker test-support package.

NOTE: the *pytest* test files that gate the suite live under the repo-root
``tests/`` tree (``tests/test_retina_*.py``) because ``pyproject.toml`` pins
``testpaths = ["tests"]`` — only that tree is collected by ``pytest tests/``.
This package holds shared **fixtures** (``retina.tests.fixtures``) those test
files import. It is a package (not a collected test dir) on purpose.
"""
