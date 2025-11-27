"""
data_sources.py
Utilities to fetch free external data (OpenSky, Open-Meteo) with simple caching.
All calls are optional and failures fall back to local data.
"""
import os
import time
import json
import pathlib
import requests

CACHE_DIR = pathlib.Path('.cache')
CACHE_DIR.mkdir(exist_ok=True)


def _cache_get(name, max_age=300):
    path = CACHE_DIR / f"{name}.json"
    if not path.exists():
        return None
    try:
        mtime = path.stat().st_mtime
        if time.time() - mtime > max_age:
            return None
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _cache_set(name, data):
    path = CACHE_DIR / f"{name}.json"
    try:
        with path.open('w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception:
        pass


# --- Open-Meteo (free, no key) ---
def fetch_current_wind(lat=48.8566, lon=2.3522, cache_max_age=300):
    """Return wind in km/h and direction degrees at given lat/lon using Open-Meteo.
    Returns: dict {'windspeed_kmh': float, 'winddirection': float} or None on failure.
    """
    cache_name = f"openmeteo_{lat:.4f}_{lon:.4f}"
    cached = _cache_get(cache_name, max_age=cache_max_age)
    if cached:
        return cached
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current_weather=true"
        )
        r = requests.get(url, timeout=6)
        if r.status_code == 200:
            data = r.json()
            cw = data.get('current_weather')
            if cw:
                # windspeed in m/s => convert to km/h or sometimes m/s per API
                # Open-Meteo uses m/s for windspeed_10m? current_weather 'windspeed' is in km/h according to API docs
                ws = cw.get('windspeed')
                wd = cw.get('winddirection')
                out = {'windspeed_kmh': float(ws) if ws is not None else 0.0, 'winddirection': float(
                    wd) if wd is not None else 0.0}
                _cache_set(cache_name, out)
                return out
    except Exception:
        pass
    return None


# --- OpenSky Network (public endpoint) ---
def fetch_opensky_states(bbox=None, cache_max_age=10):
    """Fetch states from OpenSky. bbox is [minLat, maxLat, minLon, maxLon] or None.
    Returns JSON dict or None.
    """
    cache_name = "opensky_all"
    if bbox:
        cache_name = f"opensky_{bbox[0]}_{bbox[1]}_{bbox[2]}_{bbox[3]}"
    cached = _cache_get(cache_name, max_age=cache_max_age)
    if cached:
        return cached
    try:
        base = 'https://opensky-network.org/api/states/all'
        params = {}
        if bbox:
            # OpenSky expects bbox as minLat, maxLat, minLon, maxLon
            params['bbox'] = ','.join(map(str, bbox))
        r = requests.get(base, params=params, timeout=6)
        if r.status_code == 200:
            data = r.json()
            _cache_set(cache_name, data)
            return data
    except Exception:
        pass
    return None


if __name__ == '__main__':
    print('data_sources test:')
    print('Open-Meteo wind (Paris):', fetch_current_wind(48.8566, 2.3522))
    print('OpenSky states sample:', bool(fetch_opensky_states()))
