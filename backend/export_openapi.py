import json
import os
import sys

# Add the current directory (backend) to path to find app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import create_app

app = create_app()
openapi_schema = app.openapi()

# Write to the parent directory of this script (project root)
output_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "openapi.json"
)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(openapi_schema, f, indent=2)

print(f"OpenAPI spec exported to {output_path}")
