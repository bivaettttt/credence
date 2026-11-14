import json
import sys
from pathlib import Path

from credence.api import app

path = Path("docs/openapi.json")
result = json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
if "--check" in sys.argv:
    if path.read_text() != result:
        raise SystemExit("OpenAPI drift")
else:
    path.write_text(result)
