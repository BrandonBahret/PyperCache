from __future__ import annotations

try:
    from .openmeteo_wrapper import OpenMeteoClient
except ImportError:
    from examples.weather_api.openmeteo_wrapper import OpenMeteoClient


def main() -> None:
    client = OpenMeteoClient(
        cache_path="openmeteo_cache.db",
        request_log_path="openmeteo_requests.log",
    )
    report = client.at("Phoenix", country_code="US").forecast(days=3)

    print(report.location.label)
    print(
        f"Now: {report.now.temperature_c:.1f} C, "
        f"{report.now.summary}, wind {report.now.wind_speed_kmh:.1f} km/h"
    )
    print(
        f"Today: low {report.today.low_c:.1f} C, "
        f"high {report.today.high_c:.1f} C, sunrise {report.today.sunrise.isoformat()}"
    )
    print("Next hours:")
    for hour in report.next_hours(5):
        print(
            f"  {hour.time.isoformat()}  "
            f"{hour.temperature_c:.1f} C  "
            f"{hour.precipitation_probability_pct or 0}%  "
            f"{hour.summary}"
        )

    client.close()


if __name__ == "__main__":
    main()
