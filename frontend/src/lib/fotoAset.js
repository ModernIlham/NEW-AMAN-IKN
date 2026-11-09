import { authMediaUrl } from "./mediaUrl";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Thumbnail hanya untuk strip kecil. Foto baru memakai bytes aslinya, foto
// tersimpan memakai indeks ASAL (urutan draf bisa berubah sebelum disimpan).
export function sumberFotoItem(item, assetId, version) {
  return item.type === "new" ? item.newData
    : authMediaUrl(`${API}/assets/${assetId}/photos/${item.originalIndex}?v=${version}`);
}

/** PATCH foto terikat versi; sampul dan foto stiker mengikuti susunan baru. */
export function patchHapusFoto(asset, index) {
  const count = Number(asset.photo_count) || 0;
  if (!Number.isInteger(index) || index < 0 || index >= count || !(Number(asset.version) > 0)) {
    throw new Error("Susunan foto belum tersedia. Muat ulang aset terlebih dahulu.");
  }
  const shift = (value, fallback) => value == null ? fallback : value === index ? fallback : value > index ? value - 1 : value;
  const cover = shift(Number(asset.thumbnail_index) || 0, 0);
  return {
    photo_ops: { keep: Array.from({ length: count }, (_, i) => i).filter(i => i !== index),
      add: [], thumbnail_index: cover, base_version: Number(asset.version) },
    stiker_photo_index: shift(asset.stiker_photo_index, null),
  };
}
