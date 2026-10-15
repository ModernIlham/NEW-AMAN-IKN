import fields from "./assetFields.json";

// This explicit data contract is shared by defaults, partial patch and offline
// projection. Backend parity tests compare names/labels to asset_fields.py.
export const ASSET_FIELD_REGISTRY = Object.freeze(Object.fromEntries(
  Object.entries(fields).map(([key, metadata]) => [key, Object.freeze(metadata)]),
));
export const ASSET_SCALAR_FIELDS = Object.freeze(Object.keys(ASSET_FIELD_REGISTRY));
export const ASSET_DEFAULT_SCALARS = Object.freeze(Object.fromEntries(
  ASSET_SCALAR_FIELDS.map(key => [key, ASSET_FIELD_REGISTRY[key].defaultValue]),
));
