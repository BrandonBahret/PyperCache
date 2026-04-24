"""Tests for cache_module.core.cache: Cache end-to-end with all storage backends."""

import math
import os
import time

import pytest

from pypercache import Cache
from pypercache.storage.backends import JSONStorage, PickleStorage
from pypercache.storage.sqlite_storage import SQLiteStorage
from pypercache.utils.patterns import ClassRepository
from pypercache.utils.sentinel import UNSET


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@Cache.cached
class UserProfile:
    def __init__(self, data: dict):
        self.name = data.get("name")
        self.age  = data.get("age")


# ---------------------------------------------------------------------------
# Basic operations — PickleStorage (default)
# ---------------------------------------------------------------------------

class TestCacheBasicOperations:

    def test_store_and_has(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        assert not cache.has("k")
        cache.store("k", {"v": 1})
        assert cache.has("k")

    def test_get_returns_cache_record(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        cache.store("k", {"v": 42})
        record = cache.get("k")
        assert record.data == {"v": 42}

    def test_get_missing_raises_key_error(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        with pytest.raises(KeyError, match="k"):
            cache.get("k")

    def test_store_overwrites_existing(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        cache.store("k", {"v": 1})
        cache.store("k", {"v": 2})
        assert cache.get("k").data == {"v": 2}

    def test_update_existing_record(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        cache.store("k", {"v": 1})
        cache.update("k", {"v": 99})
        assert cache.get("k").data == {"v": 99}

    def test_update_missing_raises_key_error(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        with pytest.raises(KeyError):
            cache.update("missing", {"v": 1})

    def test_completely_erase_cache(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        cache.store("a", {"v": 1})
        cache.store("b", {"v": 2})
        cache.completely_erase_cache()
        assert not cache.has("a")
        assert not cache.has("b")


# ---------------------------------------------------------------------------
# TTL / freshness
# ---------------------------------------------------------------------------

class TestCacheFreshness:

    def test_is_data_fresh_within_ttl(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        cache.store("k", {"v": 1}, expiry=3600)
        assert cache.is_data_fresh("k")

    def test_is_data_fresh_after_ttl(self, pkl_cache):
        assert not pkl_cache.is_data_fresh("stale_key")

    def test_is_data_fresh_missing_key(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        assert not cache.is_data_fresh("nonexistent")

    def test_infinite_expiry_always_fresh(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        cache.store("k", {"v": 1}, expiry=math.inf)
        assert cache.is_data_fresh("k")


# ---------------------------------------------------------------------------
# get_object with type casting
# ---------------------------------------------------------------------------

class TestGetObject:

    def test_get_object_with_cast(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        cache.store("profile", {"name": "Alice", "age": 30}, cast=UserProfile)
        obj = cache.get_object("profile")
        assert isinstance(obj, UserProfile)
        assert obj.name == "Alice"
        assert obj.age == 30

    def test_get_object_missing_raises_key_error(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        with pytest.raises(KeyError):
            cache.get_object("missing")

    def test_get_object_missing_with_default(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        result = cache.get_object("missing", default_value="fallback")
        assert result == "fallback"

    def test_get_object_no_cast_raises_attribute_error(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        cache.store("k", {"v": 1})   # no cast
        with pytest.raises(AttributeError):
            cache.get_object("k")


# ---------------------------------------------------------------------------
# @Cache.cached decorator
# ---------------------------------------------------------------------------

class TestCachedDecorator:

    def test_registers_class_in_repository(self):
        @Cache.cached
        class _DecoratorTarget:
            pass

        assert "_DecoratorTarget" in ClassRepository().list_classes()

    def test_decorated_class_still_instantiable(self):
        @Cache.cached
        class _StillWorks:
            def __init__(self):
                self.ok = True

        obj = _StillWorks()
        assert obj.ok is True


# ---------------------------------------------------------------------------
# Persistence: data survives across Cache instances
# ---------------------------------------------------------------------------

class TestPersistence:

    def test_pickle_storage_persists(self, tmp_pkl):
        Cache(filepath=tmp_pkl).store("key", {"survived": True})
        reloaded = Cache(filepath=tmp_pkl)
        assert reloaded.has("key")
        assert reloaded.get("key").data == {"survived": True}

    def test_json_storage_persists(self, tmp_json):
        Cache(filepath=tmp_json).store("key", {"survived": True})
        reloaded = Cache(filepath=tmp_json)
        assert reloaded.has("key")
        assert reloaded.get("key").data == {"survived": True}

    def test_sqlite_store_persists_without_close(self, tmp_path):
        db_path = str(tmp_path / "cache.db")
        cache = Cache(filepath=db_path)
        cache.store("key", {"survived": True})
        reloaded = Cache(filepath=db_path)
        assert reloaded.has("key")
        assert reloaded.get("key").data == {"survived": True}
        cache.close()
        reloaded.close()

    def test_sqlite_update_persists_without_close(self, tmp_path):
        db_path = str(tmp_path / "cache.db")
        cache = Cache(filepath=db_path)
        cache.store("key", {"value": 1})
        cache.update("key", {"data": {"value": 2}})
        reloaded = Cache(filepath=db_path)
        assert reloaded.get("key").data == {"value": 2}
        cache.close()
        reloaded.close()

    def test_sqlite_manual_flush_mode_requires_flush(self, tmp_path):
        db_path = str(tmp_path / "cache.db")
        cache = Cache(filepath=db_path)
        cache.enable_manual_flush_mode()
        cache.store("key", {"survived": False})

        reloaded = Cache(filepath=db_path)
        assert not reloaded.has("key")

        cache.flush()
        after_flush = Cache(filepath=db_path)
        assert after_flush.get("key").data == {"survived": False}

        cache.close()
        reloaded.close()
        after_flush.close()


# ---------------------------------------------------------------------------
# Storage backend dispatch
# ---------------------------------------------------------------------------

class TestStorageDispatch:

    def test_pkl_extension_uses_pickle_storage(self, tmp_pkl):
        cache = Cache(filepath=tmp_pkl)
        assert isinstance(cache.storage, PickleStorage)

    def test_json_extension_uses_json_storage(self, tmp_json):
        cache = Cache(filepath=tmp_json)
        assert isinstance(cache.storage, JSONStorage)

    def test_unknown_extension_raises(self, tmp_path):
        with pytest.raises(ValueError, match="No storage mechanism"):
            Cache(filepath=str(tmp_path / "store.csv"))

    def test_db_extension_uses_sqlite_storage(self, tmp_path):
        cache = Cache(filepath=str(tmp_path / "cache.db"))
        assert isinstance(cache.storage, SQLiteStorage)
        cache.close()
