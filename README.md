# PyperCache

A Python library providing durable file-backed caching for JSON-like data with pluggable storage backends (pickle, JSON, chunked manifest, SQLite), optional TTL and staleness semantics, read-only query navigation, and append-only request logging.

## Installation

```bash
pip install pypercache
```

Or install from source:

```bash
git clone https://github.com/BrandonBahret/PyperCache.git
cd PyperCache
pip install .
```

## Quick Start

See the full documentation, examples, and API reference on GitHub:

https://github.com/BrandonBahret/PyperCache/tree/master/docs

## Features

- **Pluggable Backends**: Choose storage by file extension (.pkl, .json, .manifest, .db)
- **TTL & Staleness**: Optional expiry and acceptable staleness windows
- **Typed Objects**: Decorate classes for automatic serialization/deserialization
- **Query Navigation**: Safe, read-only JSON path queries with filters
- **Request Logging**: Thread-safe JSONL audit trails

## Testing

```bash
pytest
```

## License

MIT License (see LICENSE file)