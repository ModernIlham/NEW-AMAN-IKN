"""The explicit browser scalar data contract stays aligned with API/export."""
import json
from pathlib import Path

from asset_fields import ASSET_SCALAR_FIELDS


def test_frontend_scalar_registry_names_and_export_labels_match_backend():
    root = Path(__file__).resolve().parents[3]
    registry = json.loads((root / "frontend/src/lib/assetFields.json").read_text())
    expected = {field.name: field.xlsx_label for field in ASSET_SCALAR_FIELDS}
    assert set(registry) == set(expected)
    assert {key: value["label"] for key, value in registry.items()} == expected
    assert all(isinstance(row["defaultValue"], str) for row in registry.values())
