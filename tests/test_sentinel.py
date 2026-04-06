"""Tests for PyperCache.utils.sentinel."""

import pytest
from PyperCache.utils.sentinel import UNSET, _UnsetType


class TestUnsetSentinel:

    def test_is_singleton(self):
        """Constructing _UnsetType multiple times returns the same object."""
        a = _UnsetType()
        b = _UnsetType()
        assert a is b

    def test_module_instance_is_singleton(self):
        """The module-level UNSET is identical to a freshly constructed instance."""
        assert UNSET is _UnsetType()

    def test_identity_across_import_paths(self):
        """UNSET imported via different paths resolves to the same object."""
        from PyperCache.utils.sentinel import UNSET as U1
        from PyperCache.utils import UNSET as U2
        from PyperCache.core.cache import UNSET as U3
        assert U1 is U2 is U3

    def test_bool_is_false(self):
        """UNSET is falsy, allowing `if not value` guards."""
        assert not UNSET
        assert bool(UNSET) is False

    def test_repr(self):
        assert repr(UNSET) == "UNSET"

    def test_is_check_distinguishes_from_none(self):
        """UNSET must not be confused with None."""
        assert UNSET is not None
        assert None is not UNSET

    def test_is_check_distinguishes_from_false(self):
        assert UNSET is not False
