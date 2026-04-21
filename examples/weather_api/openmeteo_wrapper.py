from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from pypercache.api_wrapper import ApiWrapper
from pypercache.models.apimodel import Alias, Columns, Timestamp, apimodel
from pypercache.models.lazy import Lazy
from pypercache.utils.sentinel import UNSET


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1"
FORECAST_URL = "https://api.open-meteo.com/v1"

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


@apimodel(validate=True)
class Location:
    id: int
    name: str
    latitude: float
    longitude: float
    elevation: float | None
    timezone: str
    country: str | None
    country_code: Annotated[str | None, Alias("country_code")]
    admin1: str | None

    @property
    def label(self) -> str:
        parts = [self.name]
        if self.admin1:
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


@apimodel(validate=True)
class GeocodingResults:
    results: list[Location]


@apimodel(validate=True)
class CurrentWeather:
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
        return WMO_WEATHER_CODES.get(self.weather_code, f"Unknown ({self.weather_code})")

    @property
    def daytime(self) -> bool:
        return bool(self.is_day)


@apimodel(validate=True)
class HourlyForecastPoint:
    time: Annotated[datetime, Timestamp(unit="seconds")]
    temperature_c: Annotated[float, Alias("temperature_2m")]
    feels_like_c: Annotated[float, Alias("apparent_temperature")]
    precipitation_probability_pct: Annotated[int | None, Alias("precipitation_probability")]
    precipitation_mm: Annotated[float, Alias("precipitation")]
    weather_code: int
    wind_speed_kmh: Annotated[float, Alias("wind_speed_10m")]

    @property
    def summary(self) -> str:
        return WMO_WEATHER_CODES.get(self.weather_code, f"Unknown ({self.weather_code})")


@apimodel(validate=True)
class DailyForecastPoint:
    date: Annotated[datetime, Alias("time"), Timestamp(unit="seconds")]
    weather_code: int
    high_c: Annotated[float, Alias("temperature_2m_max")]
    low_c: Annotated[float, Alias("temperature_2m_min")]
    precipitation_probability_pct: Annotated[int | None, Alias("precipitation_probability_max")]
    sunrise: Annotated[datetime, Timestamp(unit="seconds")]
    sunset: Annotated[datetime, Timestamp(unit="seconds")]

    @property
    def summary(self) -> str:
        return WMO_WEATHER_CODES.get(self.weather_code, f"Unknown ({self.weather_code})")


@apimodel(validate=True)
class Forecast:
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
    client: "OpenMeteoClient"
    location: Location

    def forecast(self, *, days: int = 3, timezone: str = "auto") -> ResolvedForecast:
        return ResolvedForecast(
            location=self.location,
            forecast=self.client.forecast(self.location, days=days, timezone=timezone),
        )


class OpenMeteoClient(ApiWrapper):
    """Open-Meteo example client built on the final pypercache primitives."""

    def __init__(
        self,
        *,
        cache_path: str | None = "openmeteo_cache.db",
        default_expiry: int | float = 1800,
        request_log_path: str | None = None,
        timeout: int | float | None = 10,
        session=None,
    ) -> None:
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
            expiry=86400,
            origin="geocode",
        )
        if result.results is UNSET or result.results is None:
            return []
        return result.results

    def resolve(self, query: str, *, country_code: str | None = None) -> Location:
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
        location = place if isinstance(place, Location) else self.resolve(place, country_code=country_code)
        return BoundLocation(self, location)

    def forecast(
        self,
        location: Location | tuple[float, float] | str,
        *,
        days: int = 3,
        timezone: str = "auto",
    ) -> Forecast:
        resolved = self._coerce_location(location)
        return self.request(
            "GET",
            "/forecast",
            params={
                "latitude": resolved.latitude,
                "longitude": resolved.longitude,
                "forecast_days": days,
                "timezone": resolved.timezone if timezone == "auto" and not isinstance(location, tuple) else timezone,
                "timeformat": "unixtime",
                "current": ",".join(CURRENT_FIELDS),
                "hourly": ",".join(HOURLY_FIELDS),
                "daily": ",".join(DAILY_FIELDS),
            },
            expected="json",
            cast=Forecast,
            expiry=1800,
        )

    def weather(
        self,
        query: str,
        *,
        country_code: str | None = None,
        days: int = 3,
    ) -> ResolvedForecast:
        return self.at(query, country_code=country_code).forecast(days=days)

    @staticmethod
    def _coerce_location(location: Location | tuple[float, float] | str) -> Location:
        if isinstance(location, Location):
            return location
        if isinstance(location, tuple):
            latitude, longitude = location
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
