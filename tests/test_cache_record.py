"""Tests for cache_module.core.cache_record: CacheRecord and look_up_class."""

import math
import time

import pytest

from pypercache.core.cache_record import CacheRecord, look_up_class, PRIMITIVE_TYPES_MAP
from pypercache.utils.patterns import ClassRepository
from pypercache.utils.sentinel import UNSET


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_record(data=None, expiry="math.inf", cast=None, offset=0):
    """Build a raw record dict, optionally back-dating the timestamp."""
    return {
        "timestamp": time.time() - offset,
        "expiry": expiry,
        "data": data or {"x": 1},
        "cast": cast,
    }


# ---------------------------------------------------------------------------
# look_up_class
# ---------------------------------------------------------------------------

class TestLookUpClass:

    @pytest.mark.parametrize("name,expected", [
        ("str", str), ("int", int), ("dict", dict),
        ("list", list), ("bool", bool), ("float", float),
    ])
    def test_primitive_types(self, name, expected):
        assert look_up_class(name) is expected

    def test_registered_class(self):
        class _LookupTarget:
            pass

        ClassRepository().add_class(_LookupTarget)
        assert look_up_class("_LookupTarget") is _LookupTarget

    def test_unregistered_class_raises_name_error(self):
        with pytest.raises(NameError):
            look_up_class("__TotallyMadeUp__")


# ---------------------------------------------------------------------------
# CacheRecord construction
# ---------------------------------------------------------------------------

class TestCacheRecordConstruction:

    def test_basic_fields(self):
        raw = make_record(data={"value": 7}, expiry=60)
        rec = CacheRecord(raw)
        assert rec.data == {"value": 7}
        assert rec.expiry == 60
        assert rec.cast_str is None

    def test_math_inf_expiry_deserialised(self):
        raw = make_record(expiry="math.inf")
        rec = CacheRecord(raw)
        assert rec.expiry == math.inf

    def test_numeric_expiry(self):
        raw = make_record(expiry=300)
        rec = CacheRecord(raw)
        assert rec.expiry == 300

    def test_cast_str_stored(self):
        raw = make_record(cast="dict")
        rec = CacheRecord(raw)
        assert rec.cast_str == "dict"

    def test_from_data_factory(self):
        rec = CacheRecord.from_data({"k": "v"}, expiry=120, cast=dict)
        assert rec.data == {"k": "v"}
        assert rec.expiry == 120
        assert rec.cast_str == "dict"

    def test_from_data_no_cast(self):
        rec = CacheRecord.from_data({"k": "v"})
        assert rec.cast_str is None
        assert rec.expiry == math.inf


# ---------------------------------------------------------------------------
# Freshness / staleness
# ---------------------------------------------------------------------------

class TestFreshness:

    def test_fresh_record(self):
        rec = CacheRecord(make_record(expiry=3600))
        assert not rec.is_data_stale

    def test_stale_record(self):
        rec = CacheRecord(make_record(expiry=1, offset=10))
        assert rec.is_data_stale

    def test_infinite_expiry_never_stale(self):
        rec = CacheRecord(make_record(expiry="math.inf", offset=10_000))
        assert not rec.is_data_stale

    def test_zero_expiry_is_immediately_stale(self):
        rec = CacheRecord(make_record(expiry=0, offset=1))
        assert rec.is_data_stale


# ---------------------------------------------------------------------------
# Type casting
# ---------------------------------------------------------------------------

class TestTypeCasting:

    def test_cast_resolves_primitive(self):
        raw = make_record(cast="dict")
        rec = CacheRecord(raw)
        assert rec.cast is dict
        assert rec.should_convert_type is True

    def test_cast_is_lazy(self):
        calls = []
        def resolver(name):
            calls.append(name)
            return str

        raw = make_record(cast="MyType")
        rec = CacheRecord(raw, class_resolver=resolver)
        assert calls == []          # not resolved yet
        _ = rec.cast
        assert calls == ["MyType"]  # resolved on first access
        _ = rec.cast
        assert calls == ["MyType"]  # cached — resolver not called again

    def test_no_cast_returns_none(self):
        rec = CacheRecord(make_record(cast=None))
        assert rec.cast is None
        assert rec.should_convert_type is False

    def test_class_resolver_injection(self):
        """Custom resolver bypasses ClassRepository entirely."""
        sentinel = object()
        resolver = lambda name: type("Fake", (), {})
        raw = make_record(cast="Anything")
        rec = CacheRecord(raw, class_resolver=resolver)
        assert isinstance(rec.cast, type)


# ---------------------------------------------------------------------------
# Update and serialisation
# ---------------------------------------------------------------------------

class TestUpdateAndSerialisation:

    def test_update_replaces_data(self):
        rec = CacheRecord(make_record(data={"old": 1}))
        before = rec.timestamp
        time.sleep(0.01)
        rec.update({"new": 2})
        assert rec.data == {"new": 2}
        assert rec.timestamp > before

    def test_as_dict_encodes_inf(self):
        rec = CacheRecord.from_data({}, expiry=math.inf)
        d = rec.as_dict()
        assert d["expiry"] == "math.inf"

    def test_as_dict_encodes_finite_expiry(self):
        rec = CacheRecord.from_data({}, expiry=60)
        assert rec.as_dict()["expiry"] == 60

    def test_repr_fresh(self):
        rec = CacheRecord(make_record(cast="MyType", expiry=3600))
        assert "data_fresh" in repr(rec)
        assert "MyType" in repr(rec)

    def test_repr_stale(self):
        rec = CacheRecord(make_record(cast="MyType", expiry=0, offset=5))
        assert "data_stale" in repr(rec)
