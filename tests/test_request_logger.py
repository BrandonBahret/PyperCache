"""Tests for PyperCache.core.request_logger: LogRecord and RequestLogger."""

import json
import time
import threading
from pathlib import Path

import pytest

from pypercache.core.request_logger import LogRecord, RequestLogger


# ---------------------------------------------------------------------------
# LogRecord
# ---------------------------------------------------------------------------

class TestLogRecord:

    def test_fields(self):
        ts = time.time()
        rec = LogRecord({"uri": "/api/v1", "status": 200, "timestamp": ts})
        assert rec.timestamp == ts
        assert rec.data["uri"] == "/api/v1"
        assert rec.data["status"] == 200

    def test_status_coerced_to_int(self):
        rec = LogRecord({"uri": "/", "status": "404", "timestamp": time.time()})
        assert isinstance(rec.data["status"], int)
        assert rec.data["status"] == 404

    def test_as_dict_returns_original(self):
        raw = {"uri": "/", "status": 200, "timestamp": 1_700_000_000.0}
        rec = LogRecord(raw)
        assert rec.as_dict() == raw

    def test_repr_contains_uri_and_status(self):
        rec = LogRecord({"uri": "/ping", "status": 200, "timestamp": time.time()})
        r = repr(rec)
        assert "/ping" in r
        assert "200" in r


# ---------------------------------------------------------------------------
# RequestLogger: basic writes
# ---------------------------------------------------------------------------

class TestRequestLoggerWrites:

    def test_log_creates_jsonl_lines(self, tmp_log):
        logger = RequestLogger(filepath=tmp_log)
        logger.log("/api/users", 200)
        logger.log("/api/orders", 404)

        lines = [l for l in Path(tmp_log).read_text().splitlines() if l.strip()]
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert "uri" in obj and "status" in obj and "timestamp" in obj

    def test_in_memory_records_updated(self, tmp_log):
        logger = RequestLogger(filepath=tmp_log)
        assert len(logger.records) == 0
        logger.log("/a", 200)
        logger.log("/b", 500)
        assert len(logger.records) == 2

    def test_each_write_is_one_line(self, tmp_log):
        """Every log() call appends exactly one line — O(1) write."""
        logger = RequestLogger(filepath=tmp_log)
        for i in range(10):
            logger.log(f"/endpoint/{i}", 200)
        lines = [l for l in Path(tmp_log).read_text().splitlines() if l.strip()]
        assert len(lines) == 10

    def test_records_persist_across_instances(self, tmp_log):
        RequestLogger(filepath=tmp_log).log("/a", 200)
        RequestLogger(filepath=tmp_log).log("/b", 201)
        logger = RequestLogger(filepath=tmp_log)
        assert len(logger.records) == 2
        uris = {r.data["uri"] for r in logger.records}
        assert uris == {"/a", "/b"}


# ---------------------------------------------------------------------------
# RequestLogger: loading
# ---------------------------------------------------------------------------

class TestRequestLoggerLoading:

    def test_empty_file_loads_empty_list(self, tmp_log):
        Path(tmp_log).touch()
        logger = RequestLogger(filepath=tmp_log)
        assert logger.records == []

    def test_legacy_json_array_migrated(self, legacy_log_file):
        """Files written as a JSON array are migrated to JSONL on first load."""
        logger = RequestLogger(filepath=legacy_log_file)
        assert len(logger.records) == 2

        # File must now be JSONL format
        lines = [l for l in Path(legacy_log_file).read_text().splitlines() if l.strip()]
        assert len(lines) == 2
        json.loads(lines[0])   # must be a valid JSON object

    def test_legacy_migration_preserves_data(self, legacy_log_file):
        logger = RequestLogger(filepath=legacy_log_file)
        uris = {r.data["uri"] for r in logger.records}
        assert "/old/1" in uris
        assert "/old/2" in uris

    def test_subsequent_writes_after_migration_are_jsonl(self, legacy_log_file):
        logger = RequestLogger(filepath=legacy_log_file)
        logger.log("/new/endpoint", 201)
        lines = [l for l in Path(legacy_log_file).read_text().splitlines() if l.strip()]
        assert len(lines) == 3   # 2 migrated + 1 new


# ---------------------------------------------------------------------------
# RequestLogger: time-window filtering
# ---------------------------------------------------------------------------

class TestGetLogsFromLastSeconds:

    def test_returns_only_recent_records(self, tmp_log):
        logger = RequestLogger(filepath=tmp_log)
        # Inject one old record directly (bypass log() to control timestamp)
        old = LogRecord({"uri": "/old", "status": 200, "timestamp": time.time() - 120})
        logger.records.append(old)
        logger.log("/new", 200)

        recent = logger.get_logs_from_last_seconds(60)
        uris = {r.data["uri"] for r in recent}
        assert "/new" in uris
        assert "/old" not in uris

    def test_returns_sorted_oldest_first(self, tmp_log):
        logger = RequestLogger(filepath=tmp_log)
        logger.log("/first", 200)
        time.sleep(0.02)
        logger.log("/second", 200)

        recent = logger.get_logs_from_last_seconds(10)
        assert len(recent) == 2
        assert recent[0].timestamp <= recent[1].timestamp

    def test_empty_when_all_records_old(self, tmp_log):
        logger = RequestLogger(filepath=tmp_log)
        old = LogRecord({"uri": "/old", "status": 200, "timestamp": time.time() - 200})
        logger.records.append(old)
        assert logger.get_logs_from_last_seconds(60) == []

    def test_default_window_is_60_seconds(self, tmp_log):
        logger = RequestLogger(filepath=tmp_log)
        logger.log("/recent", 200)
        assert len(logger.get_logs_from_last_seconds()) == 1


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_writes_all_recorded(self, tmp_log):
        logger = RequestLogger(filepath=tmp_log)
        threads = [
            threading.Thread(target=logger.log, args=(f"/t/{i}", 200))
            for i in range(50)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(logger.records) == 50
        lines = [l for l in Path(tmp_log).read_text().splitlines() if l.strip()]
        assert len(lines) == 50
        # Every line must be valid JSON
        for line in lines:
            json.loads(line)
