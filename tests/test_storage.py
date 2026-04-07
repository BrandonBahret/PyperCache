"""Tests for PyperCache.storage: backends, factory, and ChunkedDictionary."""

import json
import math
import time
from pathlib import Path

import pytest

from pypercache.storage.backends import ChunkedStorage, JSONStorage, PickleStorage
from pypercache.storage.factory import get_storage_mechanism
from pypercache.storage.chunked_dictionary import ChunkedDictionary


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestGetStorageMechanism:

    @pytest.mark.parametrize("ext,cls", [
        (".pkl",      PickleStorage),
        (".json",     JSONStorage),
        (".manifest", ChunkedStorage),
    ])
    def test_correct_class_returned(self, ext, cls):
        assert get_storage_mechanism(f"store{ext}") is cls

    def test_unknown_extension_raises(self):
        with pytest.raises(ValueError, match="No storage mechanism"):
            get_storage_mechanism("store.csv")

    def test_extension_case_insensitive(self):
        assert get_storage_mechanism("store.PKL") is PickleStorage
        assert get_storage_mechanism("store.JSON") is JSONStorage


# ---------------------------------------------------------------------------
# Shared backend contract
# ---------------------------------------------------------------------------

def _sample_record():
    return {
        "cast": None,
        "expiry": "math.inf",
        "timestamp": time.time(),
        "data": {"value": 42},
    }


@pytest.mark.parametrize("backend_cls,path_fixture", [
    (PickleStorage, "tmp_pkl"),
    (JSONStorage,   "tmp_json"),
])
class TestStorageBackendContract:

    def test_store_and_retrieve(self, backend_cls, path_fixture, request):
        path = request.getfixturevalue(path_fixture)
        storage = backend_cls(path)
        storage.store_record("key1", _sample_record())
        assert "key1" in storage.records
        record = storage.get_record("key1")
        assert record.data == {"value": 42}

    def test_update_record(self, backend_cls, path_fixture, request):
        path = request.getfixturevalue(path_fixture)
        storage = backend_cls(path)
        storage.store_record("k", _sample_record())
        storage.update_record("k", {"value": 99})
        assert storage.get_record("k").data == {"value": 99}

    def test_erase_everything(self, backend_cls, path_fixture, request):
        path = request.getfixturevalue(path_fixture)
        storage = backend_cls(path)
        storage.store_record("a", _sample_record())
        storage.store_record("b", _sample_record())
        storage.erase_everything()
        assert "a" not in storage.records
        assert "b" not in storage.records

    def test_persists_across_instances(self, backend_cls, path_fixture, request):
        path = request.getfixturevalue(path_fixture)
        backend_cls(path).store_record("persisted", _sample_record())
        reloaded = backend_cls(path)
        assert "persisted" in reloaded.records

    def test_keys_stored_as_strings(self, backend_cls, path_fixture, request):
        path = request.getfixturevalue(path_fixture)
        storage = backend_cls(path)
        storage.store_record(123, _sample_record())   # int key
        assert "123" in storage.records


# ---------------------------------------------------------------------------
# JSONStorage specifics
# ---------------------------------------------------------------------------

class TestJSONStorageSpecifics:

    def test_file_is_valid_json(self, tmp_json):
        storage = JSONStorage(tmp_json)
        storage.store_record("k", _sample_record())
        with open(tmp_json) as f:
            parsed = json.load(f)
        assert "k" in parsed

    def test_set_cast_coerced_to_tuple_on_save(self, tmp_json):
        """JSON backend uses jsonpickle for complex types like sets; file remains valid JSON."""
        storage = JSONStorage(tmp_json)
        rec = _sample_record()
        rec["cast"] = "set"
        rec["data"] = {1, 2, 3}
        storage.store_record("s", rec)
        # File must be valid JSON (sets serialised via jsonpickle)
        with open(tmp_json) as f:
            json.load(f)


# ---------------------------------------------------------------------------
# ChunkedDictionary
# ---------------------------------------------------------------------------

class TestChunkedDictionary:

    def test_from_dict_and_retrieve(self, tmp_manifest_dir):
        data = {"a": {"v": 1}, "b": {"v": 2}, "c": {"v": 3}}
        cd = ChunkedDictionary.from_dict(data, tmp_manifest_dir, 1024 * 1024)
        for key, val in data.items():
            assert cd[key] == val

    def test_setitem_and_getitem(self, tmp_manifest_dir):
        cd = ChunkedDictionary.from_dict({}, tmp_manifest_dir, 1024 * 1024)
        cd["x"] = {"hello": "world"}
        assert cd["x"] == {"hello": "world"}

    def test_contains(self, tmp_manifest_dir):
        cd = ChunkedDictionary.from_dict({"k": {}}, tmp_manifest_dir, 1024 * 1024)
        assert "k" in cd
        assert "missing" not in cd

    def test_len(self, tmp_manifest_dir):
        data = {str(i): {"i": i} for i in range(5)}
        cd = ChunkedDictionary.from_dict(data, tmp_manifest_dir, 1024 * 1024)
        assert len(cd) == 5

    def test_keys(self, tmp_manifest_dir):
        data = {"alpha": {}, "beta": {}, "gamma": {}}
        cd = ChunkedDictionary.from_dict(data, tmp_manifest_dir, 1024 * 1024)
        assert set(cd.keys()) == {"alpha", "beta", "gamma"}

    def test_get_with_default(self, tmp_manifest_dir):
        cd = ChunkedDictionary.from_dict({}, tmp_manifest_dir, 1024 * 1024)
        assert cd.get("missing", "fallback") == "fallback"

    def test_get_missing_without_default_raises(self, tmp_manifest_dir):
        cd = ChunkedDictionary.from_dict({}, tmp_manifest_dir, 1024 * 1024)
        with pytest.raises(KeyError):
            cd["nonexistent"]

    def test_erase_everything(self, tmp_manifest_dir):
        cd = ChunkedDictionary.from_dict({"x": {}}, tmp_manifest_dir, 1024 * 1024)
        cd.erase_everything()
        assert len(cd) == 0

    def test_from_disk_roundtrip(self, tmp_manifest_dir):
        data = {"p": {"persisted": True}}
        ChunkedDictionary.from_dict(data, tmp_manifest_dir, 1024 * 1024)
        manifest = tmp_manifest_dir / "chunks.manifest"
        reloaded = ChunkedDictionary.from_disk(manifest)
        assert reloaded["p"] == {"persisted": True}

    def test_directory_contains_chunked_dictionary(self, tmp_manifest_dir):
        assert not ChunkedDictionary.directory_contains_chunked_dictionary(tmp_manifest_dir)
        ChunkedDictionary.from_dict({}, tmp_manifest_dir, 1024 * 1024)
        assert ChunkedDictionary.directory_contains_chunked_dictionary(tmp_manifest_dir)

    def test_chunking_splits_large_data(self, tmp_manifest_dir):
        """Tiny chunk size forces multiple chunk files to be created."""
        data = {str(i): {"payload": "x" * 100} for i in range(20)}
        cd = ChunkedDictionary.from_dict(data, tmp_manifest_dir, chunk_size_in_bytes=200)
        chunk_files = list(tmp_manifest_dir.glob("*-chunk.pkl"))
        assert len(chunk_files) > 1
        # All keys still accessible
        for key in data:
            assert cd[key] == data[key]

    def test_update_existing_key(self, tmp_manifest_dir):
        cd = ChunkedDictionary.from_dict({"k": {"v": 1}}, tmp_manifest_dir, 1024 * 1024)
        cd["k"] = {"v": 99}
        assert cd["k"] == {"v": 99}
