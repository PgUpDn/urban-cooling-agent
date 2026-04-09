import json
import math
import statistics
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from langsmith import traceable

SINGAPORE_TZ = timezone(timedelta(hours=8))


class NEAWeatherClient:
    """Fetches real-time or historical weather data from data.gov.sg (NEA)."""

    COLLECTION_ID = 1459
    METADATA_URL = (
        "https://api-production.data.gov.sg/v2/public/api/collections/{collection_id}/metadata"
    )
    DATASET_ENDPOINTS = {
        "temperature": "https://api.data.gov.sg/v1/environment/air-temperature",
        "humidity": "https://api.data.gov.sg/v1/environment/relative-humidity",
        "wind_speed": "https://api.data.gov.sg/v1/environment/wind-speed",
        "wind_direction": "https://api.data.gov.sg/v1/environment/wind-direction",
    }

    def __init__(self, timeout: int = 30):
        self.session = requests.Session()
        self.timeout = timeout

    @traceable(name="NEAWeatherClient.fetch_weather_snapshot")
    def fetch_weather_snapshot(
        self, target_datetime: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch metadata and readings near target_datetime (SGT).
        If target_datetime is None, uses the latest available data.
        """
        start = time.time()
        metadata = self._request_json(
            self.METADATA_URL.format(collection_id=self.COLLECTION_ID)
        )
        if metadata is None:
            return None

        params = None
        requested_time_sgt = None
        if target_datetime:
            requested_time_sgt = target_datetime.astimezone(SINGAPORE_TZ)
            params = {
                "date_time": requested_time_sgt.strftime("%Y-%m-%dT%H:%M:%S"),
            }

        dataset_payloads: Dict[str, Dict[str, Any]] = {}
        for key, url in self.DATASET_ENDPOINTS.items():
            dataset_payloads[key] = self._request_json(url, params=params) or {}

        fetched_at = datetime.now(timezone.utc).isoformat()
        snapshot = {
            "source": "data.gov.sg",
            "fetched_at_utc": fetched_at,
            "collection_id": str(self.COLLECTION_ID),
            "collection_metadata": metadata.get("data", {}).get("collectionMetadata", {}),
            "datasets": dataset_payloads,
            "requested_time_sgt": requested_time_sgt.isoformat() if requested_time_sgt else None,
        }
        snapshot["measurements"] = self._derive_measurements(
            dataset_payloads, requested_time_sgt
        )
        snapshot["latency_seconds"] = round(time.time() - start, 3)
        return snapshot

    @traceable(name="NEAWeatherClient.build_solver_parameters")
    def build_solver_parameters(
        self,
        snapshot: Dict[str, Any],
        target_lat: Optional[float] = None,
        target_lon: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Map snapshot measurements into solver parameter suggestions."""
        if target_lat is not None and target_lon is not None:
            measurements = self._derive_measurements(
                snapshot.get("datasets", {}),
                snapshot.get("measurements", {}).get("requested_time_sgt"),
                target_lat=target_lat,
                target_lon=target_lon,
            )
        else:
            measurements = snapshot.get("measurements", {})
        timestamp_iso = (
            measurements.get("timestamp_local")
            or measurements.get("timestamp_utc")
            or datetime.now(timezone.utc).isoformat()
        )

        cfd_params: Dict[str, Any] = {}
        solar_params: Dict[str, Any] = {}

        if measurements.get("wind_speed_ms") is not None:
            cfd_params["wind_speed"] = round(measurements["wind_speed_ms"], 3)
        if measurements.get("wind_direction_deg") is not None:
            cfd_params["wind_direction"] = round(measurements["wind_direction_deg"], 1)
        if measurements.get("temperature_c") is not None:
            cfd_params["temperature"] = round(measurements["temperature_c"], 2)
        if measurements.get("relative_humidity_pct") is not None:
            cfd_params["humidity"] = round(measurements["relative_humidity_pct"], 2)

        if measurements.get("temperature_c") is not None:
            solar_params["ambient_temperature"] = round(measurements["temperature_c"], 2)
        solar_params["time"] = timestamp_iso

        result: Dict[str, Any] = {}
        if cfd_params:
            result["cfd"] = cfd_params
        if solar_params:
            result["solar"] = solar_params
        return result

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @traceable(name="NEAWeatherClient._request_json")
    def _request_json(self, url: str, params: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    def _derive_measurements(
        self,
        payloads: Dict[str, Dict[str, Any]],
        requested_time_sgt: Optional[datetime],
        target_lat: Optional[float] = None,
        target_lon: Optional[float] = None,
    ) -> Dict[str, Any]:
        items = {}
        for key, data in payloads.items():
            items[key] = self._extract_latest(
                data, target_lat=target_lat, target_lon=target_lon
            )

        timestamp_local = None
        for key in ("temperature", "humidity", "wind_speed", "wind_direction"):
            ts = items.get(key, {}).get("timestamp")
            if ts:
                timestamp_local = ts
                break
        timestamp_utc = None
        if timestamp_local:
            try:
                timestamp_utc = (
                    datetime.fromisoformat(timestamp_local.replace("Z", "+00:00"))
                    .astimezone(timezone.utc)
                    .isoformat()
                )
            except Exception:
                timestamp_utc = None

        return {
            "temperature_c": self._mean_reading(items.get("temperature", {})),
            "relative_humidity_pct": self._mean_reading(items.get("humidity", {})),
            "wind_speed_ms": self._mean_reading(items.get("wind_speed", {})),
            "wind_direction_deg": self._circular_mean(items.get("wind_direction", {})),
            "timestamp_local": timestamp_local or (requested_time_sgt.isoformat() if requested_time_sgt else None),
            "timestamp_utc": timestamp_utc,
            "requested_time_sgt": requested_time_sgt.isoformat() if requested_time_sgt else None,
        }

    def _extract_latest(
        self,
        data: Dict[str, Any],
        target_lat: Optional[float] = None,
        target_lon: Optional[float] = None,
    ) -> Dict[str, Any]:
        items = data.get("items") or []
        if not items:
            return {}
        latest = items[0]
        readings = latest.get("readings") or []
        stations_meta = {
            station.get("id"): station
            for station in data.get("metadata", {}).get("stations", [])
        }

        station_id = None
        if (
            target_lat is not None
            and target_lon is not None
            and readings
            and stations_meta
        ):
            chosen, _ = self._nearest_station_reading(
                readings, stations_meta, target_lat, target_lon
            )
            station_id = chosen.get("station_id") if chosen else None
            values = (
                [chosen.get("value")] if chosen and chosen.get("value") is not None else []
            )
        else:
            values = [
                reading.get("value")
                for reading in readings
                if reading.get("value") is not None
            ]

        return {
            "timestamp": latest.get("timestamp"),
            "station_count": len(readings),
            "station_id": station_id,
            "values": values,
        }

    @staticmethod
    def _mean_reading(entry: Dict[str, Any]) -> Optional[float]:
        values = entry.get("values") or []
        values = [v for v in values if isinstance(v, (int, float))]
        if not values:
            return None
        return statistics.fmean(values)

    @staticmethod
    def _circular_mean(entry: Dict[str, Any]) -> Optional[float]:
        values = entry.get("values") or []
        values = [v for v in values if isinstance(v, (int, float))]
        if not values:
            return None
        sin_sum = sum(math.sin(math.radians(v)) for v in values)
        cos_sum = sum(math.cos(math.radians(v)) for v in values)
        angle = math.degrees(math.atan2(sin_sum, cos_sum))
        return (angle + 360.0) % 360.0

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _nearest_station_reading(
        self,
        readings: List[Dict[str, Any]],
        stations_meta: Dict[str, Dict[str, Any]],
        target_lat: float,
        target_lon: float,
    ) -> Tuple[Dict[str, Any], float]:
        best_reading: Dict[str, Any] = {}
        best_dist = float("inf")
        for reading in readings:
            station_id = reading.get("station_id")
            station = stations_meta.get(station_id or "")
            if not station:
                continue
            location = station.get("location") or {}
            lat = location.get("latitude")
            lon = location.get("longitude")
            if lat is None or lon is None:
                continue
            dist = self._haversine_km(float(lat), float(lon), target_lat, target_lon)
            if dist < best_dist:
                best_reading = reading
                best_dist = dist
        if not best_reading and readings:
            best_reading = readings[0]
        return best_reading, best_dist


