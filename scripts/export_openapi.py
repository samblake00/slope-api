"""Writes docs/openapi.json from the Flask app (run from the repo root)."""
import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / 'service'))
os.environ.setdefault('DATABASE_URL', 'sqlite://')

from app import create_app, api_v1  # noqa: E402

app = create_app()
with app.test_request_context():
    spec = api_v1.__schema__

out = root / 'docs' / 'openapi.json'
out.write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')
print(f'wrote {out}')
