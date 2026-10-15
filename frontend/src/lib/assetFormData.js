import { ASSET_DEFAULT_SCALARS, ASSET_SCALAR_FIELDS } from "./assetFields";
import { normalisasiJenisOperasional } from "./jenisOperasional";
import { bangunChecklist, rekomendasiKelengkapan } from "./kelengkapanBmn";

/** Fresh form containers; no React state, storage, request or media fetch. */
export function emptyAssetForm(activityId) {
  return {
    ...ASSET_DEFAULT_SCALARS,
    photos: [], thumbnail_index: 0, stiker_photo_index: null,
    document_checklist: [], activity_id: activityId || null,
  };
}

/** Preserve the legacy form's truthy fallbacks and custom operational values. */
export function buildEditFormData(asset, activityId) {
  const fields = Object.fromEntries(ASSET_SCALAR_FIELDS.map(key => [
    key, asset[key] || ASSET_DEFAULT_SCALARS[key],
  ]));
  fields.operasional_jenis = normalisasiJenisOperasional(asset.operasional_jenis);
  const existing = Array.isArray(asset.document_checklist) ? asset.document_checklist : [];
  return {
    ...fields, photos: [], thumbnail_index: asset.thumbnail_index || 0,
    stiker_photo_index: asset.stiker_photo_index != null ? asset.stiker_photo_index : null,
    document_checklist: existing.length ? existing : bangunChecklist(rekomendasiKelengkapan(asset.asset_code), []),
    activity_id: activityId || null,
  };
}

/**
 * Pure edit contract. Compression stays in the submit controller; this function
 * consumes its immutable media snapshot/prepared bytes and never reads refs.
 * Missing/unloaded media is omitted unless explicitly edited. Positional photo
 * operations remain fenced to the version that produced their original order.
 */
export function buildAssetPatch({
  formData, original, autoStatus,
  photosModified = false, mediaLoaded = false, photoItems = [],
  compressedNewPhotos = [], assetVersion,
  checklistModified = false, cleanedChecklist,
}) {
  const patch = {};
  for (const key of [...ASSET_SCALAR_FIELDS, "activity_id"]) {
    if (String(formData[key] ?? "") !== String(original[key] ?? "")) {
      patch[key] = formData[key];
    }
  }
  if (autoStatus !== (original.inventory_status ?? "")) patch.inventory_status = autoStatus;
  else delete patch.inventory_status;
  if (formData.thumbnail_index !== original.thumbnail_index) patch.thumbnail_index = formData.thumbnail_index;
  if (formData.stiker_photo_index !== original.stiker_photo_index) patch.stiker_photo_index = formData.stiker_photo_index;
  if (photosModified) {
    const keep = [];
    if (!mediaLoaded) {
      const known = Number(original._photoCount) || 0;
      for (let index = 0; index < known; index++) keep.push(index);
    }
    for (const item of photoItems) {
      if (item.type === "existing") keep.push(item.originalIndex);
    }
    patch.photo_ops = {
      keep, add: compressedNewPhotos,
      thumbnail_index: formData.thumbnail_index || 0, base_version: assetVersion,
    };
  }
  if (checklistModified) patch.document_checklist = cleanedChecklist;
  return patch;
}
