# Open-Meteo Wrapper Example

This example now has a single final implementation in [`openmeteo_wrapper.py`](./openmeteo_wrapper.py). The older `openmeteo_wrapper_v1.py` and `openmeteo_wrapper_v2.py` files remain only as compatibility import shims.

It demonstrates the current pypercache mechanisms working together:

- origin-aware `ApiWrapper` requests for the forecast and geocoding hosts
- `@apimodel(validate=True)` for typed response hydration
- `Alias(...)` for Python-friendly field names
- `Timestamp(...)` for Unix timestamp parsing
- `Columns(...)` for Open-Meteo's dict-of-arrays payloads
- `Lazy[...]` for deferring heavier forecast branches
- `client.at(...).forecast(...)` for a cleaner resolve-then-fetch flow

## Quick start

```bash
python examples/weather_api/app.py
```

## Public surface

```python
from examples.weather_api.openmeteo_wrapper import OpenMeteoClient

client = OpenMeteoClient(cache_path="weather_cache.db")

report = client.at("Phoenix", country_code="US").forecast(days=3)
print(report.location.label)
print(report.now.temperature_c, report.now.summary)
print(report.today.high_c, report.today.low_c)

for hour in report.next_hours(6):
    print(hour.time, hour.temperature_c, hour.summary)
```

You can still use the more direct helpers when they fit better:

```python
location = client.resolve("Phoenix", country_code="US")
forecast = client.forecast(location, days=3)
report = client.weather("Phoenix", country_code="US", days=3)
```

## Why this example is useful

The raw Open-Meteo forecast payload mixes:

- nested objects
- Python-unfriendly field names like `temperature_2m`
- Unix timestamps
- column-oriented hourly and daily arrays

The final wrapper turns that into a friendlier object graph:

- `temperature_2m` becomes `temperature_c`
- `apparent_temperature` becomes `feels_like_c`
- `current`, `hourly`, and `daily` are typed models
- `hourly` and `daily` are exposed directly as `list[...]` row models
- geocoding and forecast calls share one wrapper via named origins

## Upstream docs

- [Forecast API docs](https://open-meteo.com/en/docs)
- [Geocoding API docs](https://open-meteo.com/en/docs/geocoding-api)
