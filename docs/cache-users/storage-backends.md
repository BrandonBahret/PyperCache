# Choose A Storage Backend

The cache backend is selected entirely by file extension.

The cache API stays the same across all backends. What changes is how data is stored and how well the backend fits your write volume, cache size, and operational needs.

```python
Cache(filepath="cache.pkl")
Cache(filepath="cache.json")
Cache(filepath="cache.manifest")
Cache(filepath="cache.db")
```

## Quick picker

| Extension | Backend | Use it when |
|---|---|---|
| `.pkl` | Pickle | You want the default, simplest general-purpose backend. |
| `.json` | JSON | You want a human-readable file and your cache will stay fairly small. |
| `.manifest` | Chunked storage | You expect many keys or large payloads and want per-chunk rewrites instead of full-file rewrites. |
| `.db` | SQLite | You want better write behavior, concurrent access, or a cache that grows over time. |

## Pickle: `.pkl`

Pros:

- simple default choice
- Python-native serialization
- no external service required

Trade-offs:

- not human-readable
- rewrites the full store on each save
- less suitable as a portable long-term archive

## JSON: `.json`

Pros:

- human-readable
- easy to inspect during debugging
- easy to diff in version control for small stores

Trade-offs:

- rewrites the full store on each save
- complex objects may fall back to `jsonpickle`, which is not always human-friendly
- not ideal for large caches

## Chunked storage: `.manifest`

This backend stores records across multiple pickle chunk files and keeps a manifest file alongside them.

Use it when:

- the cache is large
- you do not want full-file rewrites on each write
- you are okay with a directory-based backing store instead of one single file

The implementation is exposed as `ChunkedDictionary` in `pypercache.storage`.

## SQLite: `.db`

This is the most operationally robust backend in the package.

Use it when:

- writes happen regularly
- cache size may grow
- you want WAL mode without repeated full-file rewrites
- you care about avoiding repeated full-file rewrites

Important behavior:

- records are loaded into memory on open
- `Cache.store()` and `Cache.update()` flush immediately by default
- manual flush mode is optional and must be enabled explicitly
- when manual flush mode is enabled, SQLite writes do not reach disk until you call `flush()` or `close()`

If you use SQLite directly or through `Cache`, call `close()` when you are done. In the default mode this mainly closes the connection cleanly; in manual flush mode it also flushes pending writes.

## Same cache semantics across backends

Regardless of backend, these behaviors stay the same:

- `Cache.store()`
- `Cache.get()`
- `Cache.get_object()`
- TTL and staleness checks
- `CacheRecord.query`

## Practical defaults

- Start with `.pkl` if you want the simplest default.
- Use `.json` if human readability matters more than write efficiency.
- Use `.manifest` when full-file rewrites become too expensive.
- Use `.db` when the cache grows, writes happen regularly, or you care about better operational behavior.

## Request logging is separate

`RequestLogger` does not depend on the cache backend. It always writes JSONL records to its own file.

```python
from pypercache import RequestLogger

log = RequestLogger("requests.log")
log.log(uri="/v1/items", status=200)
```

For exact backend and logging details, see [storage and logging reference](../reference/storage-and-logging.md).
