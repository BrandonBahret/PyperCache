# Pypercache Feature Guide

Use this reference while mapping raw API docs into Python types.

## Default Bias

- Prefer `@apimodel(validate=True)` for external API payloads.
- Use `strict=True` only when missing fields should fail immediately.
- Favor friendly Python attribute names and map raw names with `Alias`.

## `Alias`

Use `Alias` when:

- the API uses camelCase and the wrapper uses snake_case
- the docs expose awkward names like `temperature_2m`
- the raw key collides with a Python convention or would read poorly

Example:

```python
display_name: Annotated[str, Alias("displayName")]
```

## `Timestamp`

Use `Timestamp` when the docs describe:

- ISO datetime strings
- Unix timestamps
- millisecond timestamps
- formatted date/time strings

Do not leave timestamps as raw strings unless there is a strong reason not to parse them.

## `Lazy`

Use `Lazy[T]` when a field is:

- a large nested branch
- expensive to hydrate
- rarely needed by typical consumers
- a large list or nested object returned together with a much smaller summary payload

Do not use `Lazy` for small, frequently accessed fields. The point is to delay work that is genuinely heavyweight or optional.

Good candidates:

- detailed forecast timelines
- expanded nested metadata
- verbose audit trails
- large related-resource collections bundled into one response

## `Columns`

Use `Columns` when the API returns parallel arrays that really describe rows.

Typical fit:

```json
{
  "hourly": {
    "time": [...],
    "temperature": [...],
    "humidity": [...]
  }
}
```

That should usually become a row model plus:

```python
hourly: Annotated[list[HourlyPoint], Columns(required=("time", "temperature"))]
```

## `validate` And `strict`

Choose deliberately:

- `validate=True` for nearly all external API models
- `strict=True` only for fields that must be present for the model to make sense

Avoid `strict=True` on endpoints whose docs are inconsistent or whose fields are conditionally present.

## Enum Discovery

Scan the docs for closed sets and create enums when they improve discovery and correctness.

Typical enum candidates:

- status values
- sort fields
- sort directions
- languages
- countries
- categories
- units
- formats
- event types
- severity levels

If the docs show a short accepted-values table or repeated fixed literals across endpoints, strongly consider an enum.

Use enums to improve both method signatures and documentation. Preserve the raw API value as the enum value.

## Convenience Modeling

Do not stop at a literal endpoint-for-endpoint port.

Look for opportunities to:

- wrap multi-step flows into one method
- accept richer Python inputs and normalize them
- expose helper result objects
- add common filtering helpers
- preserve typed ergonomics around nested responses

Example pattern:

- weak API surface: `search_locations(query)` then `forecast(lat, lon)`
- better wrapper surface: `weather(place_name, country_code=None)`

The convenience method should still rely on documented API calls under the hood.
