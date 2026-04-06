"""Tests for PyperCache.utils.serialization: PickleStore and DataSerializer."""

import json
import os
import pickle
from pathlib import Path

import pytest

from PyperCache.utils.serialization import DataSerializer, PickleStore


class TestPickleStore:

    def test_save_and_load_roundtrip(self, tmp_path):
        path = str(tmp_path / "data.pkl")
        obj = {"key": [1, 2, 3], "nested": {"a": True}}
        PickleStore.save_object(obj, path)
        loaded = PickleStore.load_object(path)
        assert loaded == obj

    def test_creates_intermediate_dirs(self, tmp_path):
        path = str(tmp_path / "deep" / "nested" / "data.pkl")
        PickleStore.save_object({"x": 1}, path)
        assert Path(path).exists()

    def test_load_missing_file_returns_none(self, tmp_path, capsys):
        result = PickleStore.load_object(str(tmp_path / "ghost.pkl"))
        assert result is None
        assert "No such file" in capsys.readouterr().out

    def test_touch_file_creates_when_absent(self, tmp_path):
        path = str(tmp_path / "new.pkl")
        PickleStore.touch_file({"default": True}, path)
        assert Path(path).exists()
        assert PickleStore.load_object(path) == {"default": True}

    def test_touch_file_does_not_overwrite_existing(self, tmp_path):
        path = str(tmp_path / "existing.pkl")
        PickleStore.save_object({"original": 1}, path)
        PickleStore.touch_file({"default": 99}, path)
        assert PickleStore.load_object(path) == {"original": 1}

    def test_preserves_complex_python_types(self, tmp_path):
        """Pickle round-trips sets, tuples, and custom classes intact."""
        path = str(tmp_path / "complex.pkl")
        obj = {"s": {1, 2, 3}, "t": (4, 5), "b": b"\x00\xff"}
        PickleStore.save_object(obj, path)
        loaded = PickleStore.load_object(path)
        assert loaded == obj


class TestDataSerializer:

    def test_string_value_roundtrip(self):
        original = {"msg": "hello world"}
        assert DataSerializer.deserialize_dict(
            DataSerializer.serialize_dict(original.copy())
        ) == original

    def test_dict_value_roundtrip(self):
        original = {"cfg": {"debug": True, "retries": 3}}
        assert DataSerializer.deserialize_dict(
            DataSerializer.serialize_dict(original.copy())
        ) == original

    def test_mixed_types_roundtrip(self):
        original = {
            "greeting": "hello",
            "config": {"x": 1, "y": [2, 3]},
            "message": "the quick brown fox",
        }
        assert DataSerializer.deserialize_dict(
            DataSerializer.serialize_dict(original.copy())
        ) == original

    def test_compression_actually_applied(self):
        """Serialized output must be a [tag, hex] pair, not the raw value."""
        serialized = DataSerializer.serialize_dict({"key": "value"})
        parsed = json.loads(serialized)
        tag, hex_str = parsed["key"]
        assert tag == "str"
        assert len(hex_str) > 0
        # hex string must decode to something shorter than a long repeated string
        long_val = "a" * 10_000
        s2 = DataSerializer.serialize_dict({"k": long_val})
        hex2 = json.loads(s2)["k"][1]
        assert len(hex2) < len(long_val)

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="not supported"):
            DataSerializer.serialize_dict({"bad": 123})

    def test_compress_decompress_text_roundtrip(self):
        text = "The quick brown fox jumps over the lazy dog. " * 100
        assert DataSerializer.decompress_text(DataSerializer.compress_text(text)) == text

    def test_compress_levels(self):
        """Higher compression levels produce smaller (or equal) output."""
        text = "aaaa" * 1000
        low  = DataSerializer.compress_text(text, level=1)
        high = DataSerializer.compress_text(text, level=9)
        assert len(high) <= len(low)

    def test_empty_dict(self):
        result = DataSerializer.deserialize_dict(DataSerializer.serialize_dict({}))
        assert result == {}
