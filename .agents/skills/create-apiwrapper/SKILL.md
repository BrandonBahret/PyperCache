---
name: create-apiwrapper
description: Build Python API wrappers on top of pypercache from online API documentation. Use when the user asks for `/create-apiwrapper <docs-url>` or otherwise wants Codex to inspect an API's web docs, map its endpoints and payloads, and generate a typed pypercache-based wrapper with models, caching, logging, enums, and follow-up convenience methods.
---

# API Wrapper Skill

Build a production-oriented Python API wrapper on top of `pypercache`.

## Inputs

- Accept a docs URL such as `/create-apiwrapper https://example.com/api/docs.html`.
- Treat the URL as the starting point, not necessarily the only page worth reading.
- Build the wrapper in the current workspace unless the user says otherwise.

## Workflow

1. Start from the provided docs URL and inspect the API surface online.
2. Search the same docs site for the pages needed to understand authentication, endpoints, parameters, pagination, errors, and response shapes.
3. Before coding, create a short implementation plan covering:
   - wrapper class shape
   - models to define
   - enum candidates
   - likely convenience methods
4. Build the wrapper using `pypercache.api_wrapper.ApiWrapper` and `@apimodel` models.
5. Add typed models and pypercache features intentionally rather than mirroring the raw JSON blindly.
6. After the first implementation pass, review the wrapper for:
   - enum opportunities
   - missing aliases
   - timestamp parsing
   - strict or validate settings
        note: `validate=True` hydrates `Lazy[...]` fields so nested structures can be validated, but once enabled that hydration propagates down the payload and the lazy branches are no longer lazy in practice. When models use Lazy[...] and you want
        to add validation use `Lazy[Annotated[T, Shallow()]]` so that that field stays lazy at validation time.
   - lazy-loading opportunities
   - column-oriented payloads that should use `Columns`
   - convenience methods that improve developer ergonomics
7. When the wrapper is complete, ask the user whether to generate markdown documentation for it.
8. If the user wants docs, generate readable markdown documentation with clear structure and polished presentation.

## Required Local References

- Read [references/pypercache-wrapper-patterns.md](./references/pypercache-wrapper-patterns.md) before implementing the wrapper.
- Read [references/pypercache-feature-guide.md](./references/pypercache-feature-guide.md) when choosing model features such as `Alias`, `Timestamp`, `Lazy`, `Columns`, `validate`, and `strict`.
- Read [references/post-build-review.md](./references/post-build-review.md) after the initial implementation pass.

## Implementation Rules

- Prefer a thin endpoint layer: each endpoint method should mainly prepare arguments and delegate to `self.request(...)`.
- When the API requires shared authentication or session-wide headers, implement them in `get_session()` by calling `super().get_session()` and updating the returned session there. Treat `get_session()` as the default place for API keys, bearer tokens, default `Accept` headers, user agents, retries, and adapters unless the API docs require a different flow.
- Configure cache and request logging in the wrapper constructor unless the API is a bad fit for caching.
- Use module-level constants for base URLs, cache defaults, timeouts, and meaningful TTLs.
- Use descriptive typed models for important response shapes.
- Create enums when the docs expose closed sets such as status values, sort values, categories, units, languages, or region codes.
- Add wrapper-specific convenience methods when they remove repetitive multi-step work for developers.
- Do not invent undocumented endpoint behavior, but do compose documented calls into ergonomic helper methods.
- If the API has authentication, make sure the generated wrapper docs and examples show exactly where auth is applied, preferably with a concrete `get_session()` example.

## Documentation Output

If the user asks for wrapper docs after implementation:

- Return markdown.
- Organize it for fast scanning: overview, install/setup, authentication, quick start, models, endpoint methods, convenience methods, caching/logging behavior, and examples.
- Make examples realistic and copyable.
