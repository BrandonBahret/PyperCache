# Post-Build Review

After the first implementation pass, review the wrapper methodically before presenting it as done.

## Pass 1: API Coverage

Confirm that the implemented methods cover the useful documented surface:

- primary read endpoints
- important write endpoints, if relevant
- authentication setup
- pagination mechanics
- common filters
- error-relevant parameters

## Pass 2: Model Quality

Check for:

- nested response branches that should be typed
- fields that need `Alias`
- fields that should be `datetime` via `Timestamp`
- fields that should be enums
- places where `strict=True` would be too aggressive
- places where `validate=True` was forgotten
- column-oriented payloads that should use `Columns`
- heavy branches that should use `Lazy`

## Pass 3: Convenience Methods

Ask what a developer would repeatedly do with this API that the raw docs make awkward.

Good convenience methods usually:

- combine a search step with a detail step
- normalize multiple accepted input styles
- hide repeated pagination or filtering boilerplate
- map user-friendly inputs to documented API values
- expose a common workflow as one call

Example pattern:

- raw docs: `list_locations(query)` then manually pick one result, then call `forecast(lat, lon)`
- better wrapper: `weather(place_name, country_code=None, days=3)`

Another pattern:

- raw docs: `list_projects(page=...)` and client code must loop until the target slug is found
- better wrapper: `get_project_by_slug(slug)`

Do not invent unsupported server behavior. Compose documented calls locally.

## Pass 4: Developer Experience

Check for:

- sensible defaults
- useful docstrings
- readable constant names
- clear cache TTLs
- request log support
- a clean `__all__`
- a clear class name ending in `Client` unless another suffix is more natural

## Pass 5: Final User Prompt

Once the wrapper is complete, ask:

`Do you want me to generate markdown documentation for this wrapper as well?`

If the user says yes, produce docs that cover:

- overview
- installation or import path
- authentication
- constructor options
- endpoint methods
- convenience methods
- models and enums
- caching and logging behavior
- examples
