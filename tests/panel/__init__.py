"""Package marker for the panel seat tests.

NOT optional, and not cosmetic. Without it, pytest imports tests/panel/conftest.py
under the bare module name ``conftest`` and it DISPLACES tests/conftest.py in
sys.modules -- at which point the 14 test modules that do ``from conftest import
...`` fail to collect. Measured: 13 collection errors, exit 2, the moment
tests/panel/conftest.py was added without this file.

tests/solaris/ already carries the same marker for the same reason.
"""
