---

tag: Reference

comment: "REF: CACHE"

title: Cache

title_em: "API"

lead: |

  Exact signatures and behavior for `Cache{ref=ref-cache#cache}` and `CacheRecord{ref=ref-cache#cache-record}`.

breadcrumb: "pypercache / cache api"

---



```python
from pypercache import Cache, CacheRecord
```

## Cache {id=cache}

### Constructor {id=constructor}

:::method
Cache(filepath: str | None = None)
:::

Default path: `api-cache.pkl{ref=ref-cache#constructor}`. Backend selected from the file extension.

### Methods

#### store {id=store}

:::method
cache.store(key, data, expiry=math.inf, cast=None)
:::

Creates or overwrites a record. Pass `cast=MyModel` to store hydration metadata alongside the payload.

#### get {id=get}

:::method
cache.get(key) → CacheRecord
:::

Returns the record. Raises `KeyError` if missing.

#### get_object {id=get-object}

:::method
cache.get_object(key, default_value=UNSET) → object
:::

Hydrates the payload using the stored cast type. Raises `KeyError` if missing (and no default given), or `AttributeError` if no cast metadata was stored.

#### has {id=has}

:::method
cache.has(key) → bool
:::

Checks existence only. Doesn't care whether the record is stale.

#### is_data_fresh {id=is-data-fresh}

:::method
cache.is_data_fresh(key) → bool
:::

Returns `True` only when the key exists and the TTL has not elapsed. Never raises.

#### update {id=update}

:::method
cache.update(key, data)
:::

Replaces the payload, refreshes the timestamp, preserves expiry and cast metadata. Raises `KeyError` if the key doesn't exist.

#### completely_erase_cache {id=completely-erase-cache}

:::method
cache.completely_erase_cache()
:::

Deletes all records from the backend.

#### close {id=close}

:::method
cache.close()
:::

Closes the storage backend. This matters most for SQLite: it always closes the connection cleanly and flushes pending writes when manual flush mode is enabled. It is a no-op for other backends.

#### Cache.cached {id=cache-cached}

:::method
@Cache.cached
:::

Class decorator for lightweight registration. The decorated class can then be passed as `cast=`.

---

## CacheRecord {id=cache-record}

Returned by `cache.get(key){ref=ref-cache#get}`.

### Attributes {id=attributes}

:::table
| Attribute | Type | Description |
| --- | --- | --- |
| data | any | The stored payload. |
| timestamp | float | Unix timestamp of the last write. |
| expiry | float | TTL in seconds (`math.inf` if none set). |
| cast_str | str \| None | Stored cast metadata string. |
| cast | type \| None | Lazily resolved Python type. |
| is_data_stale | bool | `True` when the record has expired. |
| query | JsonInjester | A `JsonInjester{ref=json-injester#standalone-usage}` instance over `data`. |
:::

### Methods {id=methods}

#### update {id=record-update}

:::method
record.update(data)
:::

Replaces the payload, refreshes the timestamp, and invalidates the cached query wrapper.

#### as_dict {id=as-dict}

:::method
record.as_dict() → dict
:::

Returns a serializable dict representation of the record.
