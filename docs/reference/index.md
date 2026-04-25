# PyperCache Documentation

PyperCache is a Python library for caching API responses, typed data hydration, and query-based payload inspection.

## Concepts

- **Cache** — the core persistence API. Write, read, check freshness, and hydrate typed objects.
- **ApiWrapper** — a high-level HTTP client base class. Handles requests, caching, and typed responses in one place.
- **@apimodel** — a model decorator for API-shaped data. Adds dict-accepting constructors, nested hydration, aliases, timestamps, and validation.
- **JsonInjester** — a read-only query layer over in-memory dicts and lists.
- **RequestLogger** — a lightweight append-only log for HTTP request metadata.

## Guides

| Guide | Description |
|---|---|
| [Serialize and retrieve data](./guides/cache.md) | Core Cache workflow: store, get, freshness, typed round-trips, querying |
| [Build with ApiWrapper](./guides/api-wrapper.md) | High-level HTTP client: subclassing, endpoints, caching rules, error handling |
| [Build from lower-level pieces](./guides/building-blocks.md) | Using Cache, Logger, @apimodel, and JsonInjester without ApiWrapper |
| [Typed models with @apimodel](./guides/typed-models.md) | Decorator options, nested hydration, aliases, timestamps, lazy fields |
| [JsonInjester selector syntax](./guides/json-injester.md) | Full selector reference with examples |
| [Choose a storage backend](./guides/storage-backends.md) | .pkl, .json, .manifest, .db — tradeoffs and when to use each |

## Reference

| Reference | Description |
|---|---|
| [Cache reference](./reference/cache.md) | All Cache and CacheRecord methods and attributes |
| [ApiWrapper reference](./reference/api-wrapper.md) | Constructor, request(), exceptions, SSEEvent |
| [@apimodel reference](./reference/apimodel.md) | Decorator signature and field helpers |
| [Storage and logging reference](./reference/storage-and-logging.md) | Backend classes and RequestLogger |
