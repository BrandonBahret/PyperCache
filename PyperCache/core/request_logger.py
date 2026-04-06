"""RequestLogger: thread-safe API request log with JSONL append-mode writes."""

from datetime import datetime
import threading
from typing import List
from pathlib import Path
import time
import json

from PyperCache.utils.fs import ensure_dirs_exist


LOG_FILENAME = "api_logfile.log"


class LogRecord:
    """Represents a single API request log entry."""

    def __init__(self, record: dict) -> None:
        self._record_dict = record
        self.timestamp: float = record["timestamp"]
        self.data: dict = {"uri": record["uri"], "status": int(record["status"])}

    def as_dict(self) -> dict:
        return self._record_dict

    def __repr__(self) -> str:
        ts_str = datetime.fromtimestamp(self.timestamp).strftime(
            "%d-%m-%Y %I:%M:%S,%f %p"
        )
        return f"{ts_str} - {self.data!r}"


class RequestLogger:
    """Persists API request logs to a JSON Lines file and provides
    thread-safe read/write access.

    File format: one JSON object per line (JSONL). Each call to ``log()``
    appends a single line — an O(1) operation regardless of how many records
    the file already contains. Legacy files written as a JSON array are
    detected on load and migrated transparently.
    """

    def __init__(self, filepath: str | None = None) -> None:
        self.lock = threading.Lock()
        self.filepath: str = filepath or LOG_FILENAME
        ensure_dirs_exist(self.filepath)
        path = Path(self.filepath)
        path.touch(exist_ok=True)
        self.records: List[LogRecord] = self._load(path)

    def log(self, uri: str, status: int) -> None:
        """Append a new request record to the log file (O(1) per write)."""
        new_record = {"uri": uri, "status": status, "timestamp": time.time()}
        log_record = LogRecord(new_record)
        with self.lock:
            self.records.append(log_record)
            self._append(log_record)

    def get_logs_from_last_seconds(self, seconds: int = 60) -> List[LogRecord]:
        """Return records from the last *seconds* seconds, sorted oldest-first."""
        cutoff = time.time() - seconds
        recent = [log for log in self.records if log.timestamp >= cutoff]
        return sorted(recent, key=lambda log: log.timestamp)

    def as_list(self) -> list[dict]:
        return [r.as_dict() for r in self.records]

    def _append(self, record: LogRecord) -> None:
        """Write a single record as one JSON line (must be called under self.lock)."""
        with open(self.filepath, "a") as fp:
            fp.write(json.dumps(record.as_dict()))
            fp.write("\n")

    @staticmethod
    def _load(path: Path) -> List[LogRecord]:
        """Parse records from *path*, handling both JSONL and legacy JSON-array format."""
        content = path.read_text().strip()
        if not content:
            return []

        try:
            records: list[dict] = []
            for line in content.splitlines():
                line = line.strip()
                if line:
                    parsed = json.loads(line)
                    if not isinstance(parsed, dict):
                        raise ValueError("Expected a JSON object per line.")
                    records.append(parsed)
            return [LogRecord(r) for r in records]
        except (json.JSONDecodeError, ValueError):
            pass

        try:
            records = json.loads(content)
            if isinstance(records, list):
                log_records = [LogRecord(r) for r in records if isinstance(r, dict)]
                with open(path, "w") as fp:
                    for lr in log_records:
                        fp.write(json.dumps(lr.as_dict()))
                        fp.write("\n")
                return log_records
        except json.JSONDecodeError:
            pass

        return []
