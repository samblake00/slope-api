from datetime import datetime
from .base import ProviderBase

class MockProvider(ProviderBase):
    """Returns deterministic mock data for resorts and conditions."""
    def fetch_resorts(self):
        return [
            {
                'external_id': 'copper-mountain',
                'name': 'Copper Mountain',
                'location': 'Frisco, Colorado, USA',
                'name': 'Alpine Summit',
                'location': 'Mountain Valley',
                'lat': 39.48,
                'lng': -106.16,
                'opens': '08:00',
                'closes': '16:00',
                'total_runs': 150,
                'website': 'https://www.coppercolorado.com/',
            },
            {
                'external_id': 'snowy-range',
                'name': 'Snowy Range Ski and Recreation Area',
                'location': 'Centennial, Wyoming, USA',
                'lat': 41.34,
                'lng': -106.18,
                'opens': '08:00',
                'closes': '16:00',
                'total_runs': 27,
                'website': 'https://www.coppercolorado.com/',
            },
        ]

    def fetch_conditions(self, resort_external_id: str = None):
        now = datetime.utcnow()
        data = [
            {'external_id': 'copper-mountain', 'temperature_c': -5.0, 'snow_depth_cm': 120.0, 'status': 'open', 'observed_at': now},
            {'external_id': 'snowy-range', 'temperature_c': -2.3, 'snow_depth_cm': 85.0, 'status': 'open', 'observed_at': now},
        ]
        if resort_external_id:
            return [d for d in data if d['external_id'] == resort_external_id]
        return data

