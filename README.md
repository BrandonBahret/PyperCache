# PyperCache

A Python library providing durable file-backed caching for JSON-like data with pluggable storage backends (pickle, JSON, chunked manifest, SQLite), optional TTL and staleness semantics, read-only query navigation, and append-only request logging.

## Installation

```bash
pip install lark
```

## Quick Start

See [docs/README.md](docs/README.md) for detailed documentation, examples, and API reference.

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