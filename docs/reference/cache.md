# Cache Reference

## Imports

```python
from pypercache import Cache, CacheRecord
```

## `Cache`

### Constructor

```python
Cache(filepath: str | None = None)
```

- default file path: `api-cache.pkl`
- backend is chosen from the file extension

### Methods

#### `Cache.cached`

```python
@Cache.cached
class MyModel:
    ...
```

Registers a class for cache round-trips.

#### `store`

```python
cache.store(key, data, expiry=math.inf, cast=None)
```

- creates or overwrites a record
- stores cast metadata when `cast` is provided
- flushes immediately by default for SQLite-backed caches

#### `get`

```python
cache.get(key) -> CacheRecord
```

- returns the record for `key`
- raises `KeyError` if missing

#### `get_object`

```python
cache.get_object(key, default_value=UNSET) -> object
```

- hydrates the cached payload using the stored cast type
- raises `KeyError` when missing and no default is provided
- raises `AttributeError` when the record has no cast metadata

#### `has`

```python
cache.has(key) -> bool
```

Checks existence only.

#### `is_data_fresh`

```python
cache.is_data_fresh(key) -> bool
```

Returns `True` only when the key exists and its TTL has not expired.

#### `update`

```python
cache.update(key, data)
```

- replaces the payload
- refreshes the timestamp
- preserves expiry and cast metadata
- flushes immediately by default for SQLite-backed caches

#### `flush`

```python
cache.flush()
```

For backends that support explicit flushing, forces pending writes to disk. This matters most for SQLite when manual flush mode is enabled.

#### `enable_manual_flush_mode`

```python
cache.enable_manual_flush_mode()
```

Opts into deferred writes for backends that support it. For SQLite, subsequent writes stay in memory until `flush()` or `close()` is called.

#### `disable_manual_flush_mode`

```python
cache.disable_manual_flush_mode()
```

Returns to immediate-flush writes for backends that support it. For SQLite, disabling manual flush mode also flushes any currently pending writes.

#### `completely_erase_cache`

```python
cache.completely_erase_cache()
```

Deletes all records from the backend.

#### `close`

```python
cache.close()
```

Closes the storage backend when it has lifecycle hooks. This matters most for SQLite.

## `CacheRecord`

Returned by `cache.get(key)`.

### Public attributes and properties

- `data`: stored payload
- `timestamp`: Unix timestamp of the last write
- `expiry`: TTL in seconds
- `cast_str`: stored cast metadata string or `None`
- `cast`: lazily resolved Python type or `None`
- `should_convert_type`: `True` when `cast` resolved to a valid type
- `is_data_stale`: `True` when the record has expired
- `query`: `JsonInjester` over `data`

### Methods

#### `update`

```python
record.update(data)
```

Replaces the payload, refreshes the timestamp, and invalidates the cached query wrapper.

#### `as_dict`

```python
record.as_dict() -> dict
```

Returns a serializable dict form of the record.
