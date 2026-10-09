import logging
import time
from datetime import datetime

import requests

from .base import ProviderBase

log = logging.getLogger(__name__)

API_URL = 'https://api.open-meteo.com/v1/forecast'
LOCATIONS_PER_REQUEST = 100
# Free tier allows 600 locations/minute; 100 locations every 11s stays under that
REQUEST_INTERVAL_SECONDS = 11
MAX_ATTEMPTS = 3


class OpenMeteoProvider(ProviderBase):
    """Current temperature and snow depth per location from Open-Meteo (CC BY 4.0).

    The free API is non-commercial and limited to 600 locations/minute and 10,000/day.
    """

    def _get(self, chunk):
        params = {
            'latitude': ','.join(str(r['lat']) for r in chunk),
            'longitude': ','.join(str(r['lng']) for r in chunk),
            'current': 'temperature_2m,snow_depth',
            'timezone': 'UTC',
        }
        for attempt in range(1, MAX_ATTEMPTS + 1):
            resp = requests.get(API_URL, params=params, timeout=30)
            if resp.status_code == 429 and attempt < MAX_ATTEMPTS:
                wait = 30 * attempt
                log.warning('Open-Meteo rate limited (%s); retrying in %ss', resp.text[:200], wait)
                time.sleep(wait)
                continue
            if not resp.ok:
                raise requests.HTTPError(f'{resp.status_code}: {resp.text[:200]}', response=resp)
            return resp.json()

    def fetch_conditions_for(self, resorts):
        """resorts: dicts with external_id, lat, lng. Returns condition dicts."""
        results, failures = [], 0
        for i in range(0, len(resorts), LOCATIONS_PER_REQUEST):
            if i:
                time.sleep(REQUEST_INTERVAL_SECONDS)
            chunk = resorts[i:i + LOCATIONS_PER_REQUEST]
            try:
                data = self._get(chunk)
            except (requests.RequestException, ValueError) as exc:
                log.error('Open-Meteo request failed for %d locations: %s', len(chunk), exc)
                failures += 1
                continue
            if isinstance(data, dict):
                data = [data]
            for resort, item in zip(chunk, data):
                current = item.get('current') or {}
                depth_m = current.get('snow_depth')
                observed = current.get('time')
                results.append({
                    'external_id': resort['external_id'],
                    'temperature_c': current.get('temperature_2m'),
                    'snow_depth_cm': round(depth_m * 100, 1) if depth_m is not None else None,
                    'status': None,
                    'observed_at': datetime.strptime(observed, '%Y-%m-%dT%H:%M') if observed else None,
                })
        if failures and not results:
            raise RuntimeError('All Open-Meteo requests failed')
        return results
