import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Urutan NUP LOKAL per (kegiatan|kode aset) untuk aset ber-kategori DUMMY.
// Backend next-nup hanya menghitung aset yang SUDAH tersimpan di DB,
// sedangkan aset yang ditangkap beruntun masih di antrean (belum persist) —
// next-nup akan mengembalikan NUP yang SAMA berulang → kembar. Seed dari
// server (online) / localStorage (offline) lalu naikkan sendiri per aset.
// Dipakai bersama AssetForm (Mode Kamera Penuh) dan tambah-cepat di peta —
// SATU sumber urutan (map modul + localStorage key sama) agar tak kembar.
const nupSeq = {};

export async function reserveDummyNup(activityId, assetCode, categoryLabel) {
  const key = `${activityId || ""}|${assetCode || categoryLabel || ""}`;
  const lsKey = `aman_nupseq_${key}`;
  if (nupSeq[key] == null) {
    let seed = 0;
    try {
      const c = parseInt(localStorage.getItem(lsKey) || "", 10);
      if (Number.isFinite(c)) seed = c;
    } catch { /* storage tak tersedia */ }
    try {
      const params = new URLSearchParams({ activity_id: activityId || "" });
      if (assetCode) params.set("asset_code", assetCode);
      else params.set("category", categoryLabel || "");
      const res = await axios.get(`${API}/assets/next-nup?${params}`);
      const serverNext = parseInt(res?.data?.next_nup, 10);
      if (Number.isFinite(serverNext)) seed = Math.max(seed, serverNext - 1);
    } catch { /* offline: pakai seed lokal */ }
    nupSeq[key] = seed;
  }
  const issued = (nupSeq[key] || 0) + 1;
  nupSeq[key] = issued;
  try { localStorage.setItem(lsKey, String(issued)); } catch { /* noop */ }
  return String(issued);
}

/** Kategori ber-label "dummy" dari daftar kategori (null bila tidak ada). */
export function cariKategoriDummy(categories) {
  return (categories || []).find((c) => /dummy/i.test(c.label || "")) || null;
}
