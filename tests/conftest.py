"""Shared pytest fixtures for the PyperCache test suite."""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

# Ensure the package root is on sys.path regardless of how pytest is invoked.
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Temporary file helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_pkl(tmp_path):
    """Path to a non-existent .pkl file inside a fresh temp directory."""
    return str(tmp_path / "cache.pkl")


@pytest.fixture
def tmp_json(tmp_path):
    """Path to a non-existent .json file inside a fresh temp directory."""
    return str(tmp_path / "cache.json")


@pytest.fixture
def tmp_log(tmp_path):
    """Path to a non-existent .log file inside a fresh temp directory."""
    return str(tmp_path / "requests.log")


@pytest.fixture
def tmp_manifest_dir(tmp_path):
    """A fresh empty directory ready to hold a ChunkedDictionary store."""
    d = tmp_path / "chunks"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Pre-populated cache fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def pkl_cache(tmp_pkl):
    """A Cache backed by a fresh PickleStorage with two records pre-stored."""
    from PyperCache import Cache
    cache = Cache(filepath=tmp_pkl)
    cache.store("fresh_key", {"value": 42}, expiry=3600)
    cache.store("stale_key", {"value": 99}, expiry=0)
    # Force stale_key to be expired by back-dating its timestamp
    record = cache.storage.records["stale_key"]
    record["timestamp"] = time.time() - 10
    cache.storage.save(cache.storage.records)
    return cache


@pytest.fixture
def legacy_log_file(tmp_log):
    """A .log file written in the old JSON-array format."""
    records = [
        {"uri": "/old/1", "status": 200, "timestamp": time.time() - 20},
        {"uri": "/old/2", "status": 500, "timestamp": time.time() - 10},
    ]
    with open(tmp_log, "w") as f:
        json.dump(records, f)
    return tmp_log
