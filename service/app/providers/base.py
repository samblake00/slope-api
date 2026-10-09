from typing import List, Dict

class ProviderBase:
    """Abstract provider interface.

    Implementations should return lists of dicts representing resorts and conditions.
    Resort dict example: { 'external_id': 'vail-usa', 'name': 'Vail', 'location': 'CO, USA', 'lat': 39.6, 'lng': -106.355, 'opens': '08:00', 'closes': '16:00', 'total_runs': 76 }
    Condition dict example: { 'external_id': 'vail-usa', 'temperature_c': -4.2, 'snow_depth_cm': 120.3, 'status': 'open', 'observed_at': datetime }
    """

    def __init__(self, app=None):
        self.app = app

    def fetch_resorts(self) -> List[Dict]:
        raise NotImplementedError

    def fetch_conditions(self, resort_external_id: str = None) -> List[Dict]:
        raise NotImplementedError

