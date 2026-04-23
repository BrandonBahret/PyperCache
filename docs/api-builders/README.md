# API Builders

This section is for people building API clients on top of PyperCache.

There are two valid ways to do that:

## Option A: subclass `ApiWrapper`

Use this when you want one class to own:

- HTTP transport
- cache lookup and writeback for `GET` requests
- typed response hydration with `cast=...`
- optional request logging
- shared session configuration
- URL joining and response decoding

Start here:

- [Build with `ApiWrapper`](./using-api-wrapper.md)

## Option B: compose the pieces yourself

Use this when you want full control over network calls and only want selected PyperCache pieces:

- `Cache`
- `RequestLogger`
- `@apimodel`
- `JsonInjester`

This path works best when you already have your own transport layer, want custom cache keys or refresh rules, or need to cache non-request work alongside API responses.

Start here:

- [Build from the lower-level pieces](./using-building-blocks.md)

## Recommended reading order

1. [Build with `ApiWrapper`](./using-api-wrapper.md) or [build from the lower-level pieces](./using-building-blocks.md)
2. [Typed models with `@apimodel`](./typed-models.md)
3. [Storage backends](../cache-users/storage-backends.md)
4. [Reference pages](../reference/README.md)

## Which approach should you choose?

Use `ApiWrapper` if:

- your project is request/response oriented
- most reads are `GET` requests
- you want thin endpoint methods
- you want caching without repeating the same fetch-or-cache code
- you want a single class to manage session lifecycle, caching, and typed hydration

Use the lower-level pieces if:

- you already have your own transport layer
- you want custom cache keys or custom refresh rules
- your workflow is not centered around HTTP requests
- you only want typed hydration or query navigation
