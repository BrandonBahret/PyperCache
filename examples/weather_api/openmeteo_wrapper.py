from __future__ import annotations

"""Open-Meteo example client built on pypercache.

This module will show how to:

1. subclass ``ApiWrapper`` for a real HTTP API
2. describe JSON responses with ``@apimodel``
3. rename awkward API fields with ``Alias``
4. parse Unix timestamps with ``Timestamp``
5. turn Open-Meteo's column-oriented hourly/daily payloads into row objects
6. keep bigger response branches lazy with ``Lazy``
"""


from pypercache.api_wrapper import ApiWrapper
from pypercache.models.apimodel import Alias, Columns, Lazy, Timestamp, apimodel
from pypercache.utils.sentinel import UNSET

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1"
FORECAST_URL = "https://api.open-meteo.com/v1"
DEFAULT_CACHE_PATH = "openmeteo_cache.db"
DEFAULT_TIMEOUT = 10
GEOCODING_CACHE_SECONDS = 86_400
FORECAST_CACHE_SECONDS = 1_800

# Open-Meteo lets us request only the fields we care about. Keeping these lists
# together makes the outgoing request easy to scan and easy to edit.
CURRENT_FIELDS = (
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
    "wind_direction_10m",
    "is_day",
)

HOURLY_FIELDS = (
    "temperature_2m",
    "apparent_temperature",
    "precipitation_probability",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
)

DAILY_FIELDS = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_probability_max",
    "sunrise",
    "sunset",
)

# Open-Meteo returns numeric WMO weather codes. We translate them into
# human-readable labels once here so the rest of the example can stay clean.
WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def weather_summary(weather_code: int) -> str:
    """Return a readable description for a WMO weather code."""
    return WMO_WEATHER_CODES.get(weather_code, f"Unknown ({weather_code})")


@apimodel(validate=True)
class Location:
    """One geocoding result from Open-Meteo."""

    id: int
    name: str
    latitude: float
    longitude: float
    elevation: float | None
    timezone: str
    country: str | None
    country_code: str | None
    admin1: str | None

    @property
    def label(self) -> str:
        """Build a display label like ``Phoenix, Arizona, United States``."""
        parts = [self.name]
        if self.admin1:
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


@apimodel(validate=True)
class GeocodingResults:
    """Top-level container returned by the geocoding endpoint."""

    results: list[Location]


@apimodel(validate=True)
class CurrentWeather:
    """The current conditions branch from the forecast response."""

    # ``Alias`` lets the Python attribute name stay friendly while still
    # reading from the original API field name.
    time: Annotated[datetime, Timestamp(unit="seconds")]
    temperature_c: Annotated[float, Alias("temperature_2m")]
    feels_like_c: Annotated[float, Alias("apparent_temperature")]
    humidity_pct: Annotated[int, Alias("relative_humidity_2m")]
    precipitation_mm: Annotated[float, Alias("precipitation")]
    weather_code: int
    wind_speed_kmh: Annotated[float, Alias("wind_speed_10m")]
    wind_direction_deg: Annotated[int, Alias("wind_direction_10m")]
    is_day: int

    @property
    def summary(self) -> str:
        return weather_summary(self.weather_code)

    @property
    def daytime(self) -> bool:
        return bool(self.is_day)


@apimodel(validate=True)
class HourlyForecastPoint:
    """One row from Open-Meteo's hourly forecast arrays."""

    time: Annotated[datetime, Timestamp(unit="seconds")]
    temperature_c: Annotated[float, Alias("temperature_2m")]
    feels_like_c: Annotated[float, Alias("apparent_temperature")]
    precipitation_probability_pct: Annotated[int | None, Alias("precipitation_probability")]
    precipitation_mm: Annotated[float, Alias("precipitation")]
    weather_code: int
    wind_speed_kmh: Annotated[float, Alias("wind_speed_10m")]

    @property
    def summary(self) -> str:
        return weather_summary(self.weather_code)


@apimodel(validate=True)
class DailyForecastPoint:
    """One row from Open-Meteo's daily forecast arrays."""

    date: Annotated[datetime, Alias("time"), Timestamp(unit="seconds")]
    weather_code: int
    high_c: Annotated[float, Alias("temperature_2m_max")]
    low_c: Annotated[float, Alias("temperature_2m_min")]
    precipitation_probability_pct: Annotated[int | None, Alias("precipitation_probability_max")]
    sunrise: Annotated[datetime, Timestamp(unit="seconds")]
    sunset: Annotated[datetime, Timestamp(unit="seconds")]

    @property
    def summary(self) -> str:
        return weather_summary(self.weather_code)


@apimodel(validate=True)
class Forecast:
    """Typed forecast response.

    ``current`` is a nested object, while ``hourly`` and ``daily`` arrive as
    dicts of arrays. ``Columns(...)`` tells pypercache how to zip those arrays
    into row-shaped models, and ``Lazy[...]`` delays that work until the field
    is actually accessed.
    """

    latitude: float
    longitude: float
    timezone: str
    timezone_abbreviation: str
    utc_offset_seconds: int
    elevation: float | None
    current: Lazy[CurrentWeather]
    
    hourly: Lazy[
        Annotated[
            list[HourlyForecastPoint],
            Columns(required=("time", "temperature_2m", "apparent_temperature", "weather_code")),
        ]
    ]
    
    daily: Lazy[
        Annotated[
            list[DailyForecastPoint],
            Columns(required=("time", "weather_code", "temperature_2m_max", "temperature_2m_min")),
        ]
    ]

    @property
    def now(self) -> CurrentWeather:
        return self.current

    @property
    def today(self) -> DailyForecastPoint:
        return self.daily[0]

    def next_hours(self, count: int = 6) -> list[HourlyForecastPoint]:
        return self.hourly[:count]


@dataclass(frozen=True)
class ResolvedForecast:
    """Forecast paired with the location that produced it."""

    location: Location
    forecast: Forecast

    @property
    def now(self) -> CurrentWeather:
        return self.forecast.now

    @property
    def today(self) -> DailyForecastPoint:
        return self.forecast.today

    def next_hours(self, count: int = 6) -> list[HourlyForecastPoint]:
        return self.forecast.next_hours(count)


@dataclass(frozen=True)
class BoundLocation:
    """A small convenience object returned by ``client.at(...)``."""

    client: "OpenMeteoClient"
    location: Location

    def forecast(self, *, days: int = 3, timezone: str = "auto") -> ResolvedForecast:
        """Fetch a forecast while keeping the resolved location attached."""
        return ResolvedForecast(
            location=self.location,
            forecast=self.client.forecast(self.location, days=days, timezone=timezone),
        )


class OpenMeteoClient(ApiWrapper):
    """Open-Meteo example client built on pypercache's `ApiWrapper`.

    New pypercache users can treat this class as the main pattern to copy:
    endpoint methods stay thin, while ``ApiWrapper.request(...)`` handles HTTP,
    caching, logging, and model hydration.
    """

    def __init__(
        self,
        *,
        cache_path: str | None = DEFAULT_CACHE_PATH,
        default_expiry: int | float = 1800,
        request_log_path: str | None = None,
        timeout: int | float | None = DEFAULT_TIMEOUT,
        session=None,
    ) -> None:
        # ``origins`` gives one wrapper access to both Open-Meteo hosts. The
        # forecast API stays the default, and geocoding opts in per request.
        super().__init__(
            origins={"forecast": FORECAST_URL, "geocode": GEOCODING_URL},
            default_origin="forecast",
            cache_path=cache_path,
            default_expiry=default_expiry,
            request_log_path=request_log_path,
            timeout=timeout,
            session=session,
        )

    def get_session(self):
        # Override this hook when you want one place to set headers,
        # auth, retries, or any other requests.Session customization.
        session = super().get_session()
        session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "pypercache-openmeteo-example/0.3",
            }
        )
        return session

    def search(
        self,
        query: str,
        *,
        count: int = 5,
        language: str = "en",
        country_code: str | None = None,
    ) -> list[Location]:
        """Search the geocoding API and return typed `Location` objects."""
        result = self.request(
            "GET",
            "/search",
            params={
                "name": query,
                "count": count,
                "language": language,
                "countryCode": country_code,
                "format": "json",
            },
            expected="json",
            cast=GeocodingResults,
            expiry=GEOCODING_CACHE_SECONDS,
            origin="geocode",
        )
        # Open-Meteo may omit ``results`` entirely when nothing matches.
        if result.results is UNSET or result.results is None:
            return []
        return result.results

    def resolve(self, query: str, *, country_code: str | None = None) -> Location:
        """Resolve a user-facing place name into a single `Location`."""
        results = self.search(query, count=1, country_code=country_code)
        if not results:
            raise LookupError(f"Open-Meteo could not resolve {query!r}")
        return results[0]

    def at(
        self,
        place: str | Location,
        *,
        country_code: str | None = None,
    ) -> BoundLocation:
        """Return a resolved location object that can fetch its own forecast."""
        location = place if isinstance(place, Location) else self.resolve(place, country_code=country_code)
        return BoundLocation(self, location)

    def forecast(
        self,
        location: Location | tuple[float, float] | str,
        *,
        days: int = 3,
        timezone: str = "auto",
    ) -> Forecast:
        """Fetch a forecast for a resolved place or raw coordinates."""
        resolved = self._coerce_location(location)
        request_timezone = self._request_timezone(location, resolved, timezone)
        return self.request(
            "GET",
            "/forecast",
            params={
                "latitude": resolved.latitude,
                "longitude": resolved.longitude,
                "forecast_days": days,
                "timezone": request_timezone,
                "timeformat": "unixtime",
                "current": ",".join(CURRENT_FIELDS),
                "hourly": ",".join(HOURLY_FIELDS),
                "daily": ",".join(DAILY_FIELDS),
            },
            expected="json",
            cast=Forecast,
            expiry=FORECAST_CACHE_SECONDS,
        )

    def weather(
        self,
        query: str,
        *,
        country_code: str | None = None,
        days: int = 3,
    ) -> ResolvedForecast:
        """Resolve a place name and immediately fetch its forecast."""
        return self.at(query, country_code=country_code).forecast(days=days)

    @staticmethod
    def _request_timezone(
        original_location: Location | tuple[float, float] | str,
        resolved_location: Location,
        requested_timezone: str,
    ) -> str:
        """Choose the timezone value sent to Open-Meteo.

        ``timezone="auto"`` works well for resolved named places because the
        geocoding result already includes a concrete timezone. For raw
        coordinate tuples we pass ``"auto"`` through so Open-Meteo can infer it.
        """
        if requested_timezone != "auto":
            return requested_timezone
        if isinstance(original_location, tuple):
            return "auto"
        return resolved_location.timezone

    @staticmethod
    def _coerce_location(location: Location | tuple[float, float] | str) -> Location:
        """Normalize supported location inputs for the forecast call."""
        if isinstance(location, Location):
            return location
        if isinstance(location, tuple):
            latitude, longitude = location
            # ``Location.from_dict(...)`` keeps the example on the same typed
            # path used for real API data.
            return Location.from_dict(
                {
                    "id": 0,
                    "name": f"{latitude:.4f},{longitude:.4f}",
                    "latitude": latitude,
                    "longitude": longitude,
                    "elevation": None,
                    "timezone": "auto",
                    "country": None,
                    "country_code": None,
                    "admin1": None,
                }
            )
        if isinstance(location, str):
            raise TypeError("string locations must be resolved through weather(), at(), or resolve() first")
        raise TypeError(f"unsupported location type: {type(location).__name__}")


__all__ = [
    "BoundLocation",
    "CurrentWeather",
    "DailyForecastPoint",
    "Forecast",
    "GeocodingResults",
    "HourlyForecastPoint",
    "Location",
    "OpenMeteoClient",
    "ResolvedForecast",
]
