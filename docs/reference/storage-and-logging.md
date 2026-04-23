# Storage And Logging Reference

## Imports

```python
from pypercache import RequestLogger
from pypercache.storage import (
    ChunkedDictionary,
    ChunkedStorage,
    JSONStorage,
    PickleStorage,
    SQLiteStorage,
    StorageMechanism,
    get_storage_mechanism,
)
```

## Backend selection

```python
get_storage_mechanism("cache.db")
```

Returns the backend class selected by file extension.

Supported mappings:

- `.pkl` -> `PickleStorage`
- `.json` -> `JSONStorage`
- `.manifest` -> `ChunkedStorage`
- `.db` -> `SQLiteStorage`

## `StorageMechanism`

Abstract base class for custom backends.

Public methods:

- `load()`
- `save(data)`
- `get_record(key)`
- `update_record(key, data)`
- `store_record(key, cache_record_dict)`
- `erase_everything()`
- `touch_store()`

Custom backends implement:

- `_impl__touch_store(filepath)`
- `_impl__load(filepath)`
- `_impl__save(cache_records_dict, filepath)`
- `_impl__update_record(key, data)`
- `_impl__erase_everything()`

## SQLite details

`SQLiteStorage` is the most specialized backend.

Constructor:

```python
SQLiteStorage(
    filepath,
    flush_interval=5.0,
    dirty_threshold=50,
)
```

Operational behavior:

- loads all rows into memory on open
- tracks dirty keys in memory
- flushes dirty rows in batches
- uses WAL mode
- supports `flush()` and `close()`
- supports context manager usage

If you use `SQLiteStorage` directly, prefer:

```python
with SQLiteStorage("cache.db") as store:
    ...
```

## `RequestLogger`

Constructor:

```python
RequestLogger(filepath: str | None = None)
```

Default path: `api_logfile.log`

### Methods

#### `log`

```python
logger.log(uri, status)
```

Appends one JSON object line to the log file.

#### `get_logs_from_last_seconds`

```python
logger.get_logs_from_last_seconds(seconds=60) -> list[LogRecord]
```

Returns matching records sorted oldest-first.

#### `as_list`

```python
logger.as_list() -> list[dict]
```

Returns raw record dicts.

## `LogRecord`

Public attributes:

- `timestamp`
- `data`

`data` has the shape:

```python
{"uri": "...", "status": 200}
```
