import json
from pathlib import Path

from .base import ProviderBase

DATA_FILE = Path(__file__).resolve().parent.parent / 'data' / 'resorts.json'


class OsmProvider(ProviderBase):
    """Resort list from the bundled OpenStreetMap extract (built by scripts/fetch_resorts.py).

    Data (c) OpenStreetMap contributors, ODbL.
    """

    def fetch_resorts(self):
        with open(DATA_FILE, encoding='utf-8') as f:
            return json.load(f)
