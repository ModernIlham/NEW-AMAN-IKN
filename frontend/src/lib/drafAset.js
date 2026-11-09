// DRAF ASET — perubahan form aset yang BELUM disimpan, termasuk foto baru.
//
// Masalah yang ditutup: form aset (dan Mode Kamera Penuh) hanya menyimpan
// isian di memori React. Back HP tak sengaja, ketuk latar gelap, pindah baris
// di desktop, tab di-kill Android, atau peramban dimuat ulang = semua isian &
// foto yang baru dijepret hilang tanpa jejak.
//
// Praktik yang dipilih (bukan sekadar dialog "yakin keluar?" di tiap jalan
// keluar — dialog yang muncul terus melatih pengguna menekan "Ya" tanpa
// membaca, dan tetap tak menolong saat tab di-kill):
//  1. AUTOSAVE draf ke IndexedDB (debounce) → perubahan selamat dari Back,
//     tutup, reload, crash, maupun luring. Dipulihkan otomatis saat aset yang
//     sama dibuka lagi.
//  2. Dialog konfirmasi HANYA bila memang ada perubahan bermakna (isian yang
//     diketik / foto). Nilai yang diisi OTOMATIS oleh aplikasi (GPS pinjaman,
//     garansi riwayat, kategori+NUP dummy) tidak memicunya — itulah sumber
//     "dialog muncul terus".
//  3. Pembeda visual: lencana "Belum disimpan", daftar field yang berubah,
//     tanda "Baru" pada foto, dan chip "Draf" di daftar aset.
//
// Bagian murni (tanpa DOM/IDB) diekspor terpisah agar teruji unit.
import { openDB } from "idb";
import { useSyncExternalStore } from "react";
import { ASSET_FIELD_REGISTRY, ASSET_SCALAR_FIELDS } from "./assetFields";

export const ID_BARU = "__baru__";
// Draf lebih tua dari ini dianggap basi dan dibuang saat dibaca.
export const DRAF_TTL_MS = 14 * 24 * 60 * 60 * 1000;

/** Kunci draf: per pengguna + kegiatan + aset (aset baru = ID_BARU). */
export function kunciDraf(userId, activityId, assetId) {
  return `${userId || "anon"}|${activityId || "-"}|${assetId || ID_BARU}`;
}

// Diisi aplikasi, bukan diketik pengguna — tak memicu konfirmasi keluar.
const OTOMATIS_SELALU = ["koordinat_latitude", "koordinat_longitude", "activity_id"];
// Tambahan khusus aset BARU: kategori dummy + NUP otomatis Mode Kamera Penuh.
const OTOMATIS_BARU = ["category", "asset_code", "NUP"];

const LABEL_EKSTRA = {
  thumbnail_index: "Foto sampul",
  stiker_photo_index: "Foto stiker",
};

export function labelField(key) {
  return ASSET_FIELD_REGISTRY[key]?.label || LABEL_EKSTRA[key] || key;
}

const sama = (a, b) => String(a ?? "") === String(b ?? "");

/**
 * Ringkas perubahan yang belum disimpan.
 *
 * @returns {{dirty:boolean, fields:string[], fotoBaru:number, fotoDihapus:number, checklist:boolean}}
 *   `fields` = kunci field bermakna yang berubah (field otomatis dikecualikan).
 */
export function ringkasPerubahan({
  isEditing, formData, original, emptyForm,
  photoItems = [], photosModified = false, mediaLoaded = false,
  checklistModified = false, abaikan = [],
}) {
  const kosong = { dirty: false, fields: [], fotoBaru: 0, fotoDihapus: 0, checklist: false };
  if (!formData) return kosong;
  const dasar = isEditing ? original : emptyForm;
  if (!dasar) return kosong; // data aset belum termuat — belum ada yang bisa diubah
  const skip = new Set([...OTOMATIS_SELALU, ...(isEditing ? [] : OTOMATIS_BARU), ...abaikan]);
  const fields = [];
  for (const key of ASSET_SCALAR_FIELDS) {
    if (skip.has(key)) continue;
    if (!sama(formData[key], dasar[key])) fields.push(key);
  }
  let fotoBaru = 0;
  let fotoDihapus = 0;
  if (isEditing) {
    fotoBaru = photoItems.filter((it) => it?.type === "new").length;
    if (photosModified && mediaLoaded) {
      const ada = photoItems.filter((it) => it?.type === "existing").length;
      fotoDihapus = Math.max(0, (Number(original._photoCount) || 0) - ada);
    }
    // Sampul/stiker hanya bermakna bila fotonya memang ada di server.
    if ((Number(original._photoCount) || 0) + fotoBaru > 0) {
      if (formData.thumbnail_index !== original.thumbnail_index) fields.push("thumbnail_index");
      if (formData.stiker_photo_index !== original.stiker_photo_index) fields.push("stiker_photo_index");
    }
  } else {
    fotoBaru = (formData.photos || []).filter(Boolean).length;
  }
  const checklist = !!checklistModified;
  return {
    dirty: fields.length > 0 || fotoBaru > 0 || fotoDihapus > 0 || checklist,
    fields, fotoBaru, fotoDihapus, checklist,
  };
}

/** Teks ringkas untuk banner/dialog: "Nama Aset, Kondisi, 2 foto baru". */
export function teksPerubahan(r, maks = 4) {
  if (!r?.dirty) return "";
  const bagian = r.fields.map(labelField);
  const tampil = bagian.slice(0, maks);
  if (bagian.length > maks) tampil.push(`+${bagian.length - maks} field lain`);
  if (r.fotoBaru) tampil.push(`${r.fotoBaru} foto baru`);
  if (r.fotoDihapus) tampil.push(`${r.fotoDihapus} foto dihapus`);
  if (r.checklist) tampil.push("kelengkapan dokumen");
  return tampil.join(", ");
}

/**
 * Sidik ringan keadaan form — untuk tahu apakah keadaan SAAT INI sudah
 * diserahkan ke antrean simpan (alur kamera "simpan & tetap di aset ini").
 */
export function sidikForm(formData, photoItems = [], checklistModified = false) {
  const skalar = ASSET_SCALAR_FIELDS.map((k) => String(formData?.[k] ?? "")).join("\u0001");
  const foto = (photoItems.length ? photoItems : (formData?.photos || []).map((p) => ({ type: "new", newData: p })))
    .map((it) => (it.type === "existing" ? `e${it.originalIndex}` : `n${String(it.newData || "").length}`))
    .join(",");
  return `${skalar}|${formData?.thumbnail_index}|${formData?.stiker_photo_index}|${foto}|${checklistModified ? 1 : 0}`;
}

/** Susun rekaman draf siap tulis ke IndexedDB. */
export function bangunRekamanDraf({
  key, userId, activityId, assetId, isEditing, formData, original,
  photoItems = [], photosModified = false, baseVersion = null, checklistModified = false,
}) {
  const skalar = {};
  for (const k of ASSET_SCALAR_FIELDS) skalar[k] = formData[k] ?? "";
  const rec = {
    key, userId: userId || "anon", activityId: activityId || null,
    assetId: isEditing ? assetId : null, baru: !isEditing,
    baseVersion: isEditing ? (Number(baseVersion) || null) : null,
    label: formData.asset_name || formData.asset_code || "",
    formData: {
      ...skalar,
      thumbnail_index: formData.thumbnail_index ?? 0,
      stiker_photo_index: formData.stiker_photo_index ?? null,
    },
    checklist: checklistModified ? (formData.document_checklist || []) : null,
    updatedAt: Date.now(),
  };
  if (isEditing) {
    const orig = {};
    for (const k of ASSET_SCALAR_FIELDS) orig[k] = original?.[k] ?? "";
    rec.original = { ...orig, thumbnail_index: original?.thumbnail_index ?? 0,
      stiker_photo_index: original?.stiker_photo_index ?? null };
    rec.fotoBaru = photoItems.filter((it) => it.type === "new" && it.newData)
      .map((it) => ({ newData: it.newData, thumbnail: it.thumbnail || it.newData }));
    rec.fotoTetap = photoItems.filter((it) => it.type === "existing").map((it) => it.originalIndex);
    rec.fotoDiubah = !!photosModified;
  } else {
    rec.fotoBaru = (formData.photos || []).filter(Boolean).map((p) => ({ newData: p, thumbnail: p }));
  }
  return rec;
}

/**
 * Terapkan draf EDIT di atas data segar server.
 *
 * Hanya field yang DIUBAH pengguna (draf.formData ≠ draf.original) yang
 * ditimpakan, sehingga perubahan server pada field LAIN tetap terbawa. Bila
 * versi server sudah berubah sejak draf dibuat: susunan foto lama mungkin
 * bergeser, jadi penghapusan foto & pilihan sampul/stiker TIDAK diterapkan;
 * field yang juga diubah di server dilaporkan sebagai `bentrok`.
 *
 * @param existingItems strip foto server (type:'existing') hasil muat segar.
 * @param mediaLoaded   false saat luring — foto server tak ada di strip.
 */
export function pulihkanDrafEdit({ draf, lightData, existingItems = [], versiKini, mediaLoaded = true }) {
  const formData = { ...lightData };
  const diubah = [];
  const bentrok = [];
  const versiBerubah = !!(draf.baseVersion && versiKini && Number(draf.baseVersion) !== Number(versiKini));
  for (const k of ASSET_SCALAR_FIELDS) {
    if (sama(draf.formData?.[k], draf.original?.[k])) continue;
    if (versiBerubah && !sama(lightData[k], draf.original?.[k]) && !sama(lightData[k], draf.formData[k])) bentrok.push(k);
    formData[k] = draf.formData[k];
    diubah.push(k);
  }
  let items = existingItems;
  const bolehSusunUlang = !versiBerubah && mediaLoaded;
  if (bolehSusunUlang && Array.isArray(draf.fotoTetap) && draf.fotoDiubah) {
    const tetap = new Set(draf.fotoTetap);
    items = existingItems.filter((it) => tetap.has(it.originalIndex));
  }
  const baru = (draf.fotoBaru || []).map((f) => ({ type: "new", thumbnail: f.thumbnail || f.newData, newData: f.newData }));
  items = [...items, ...baru].slice(0, 6);
  if (bolehSusunUlang) {
    if (draf.formData?.thumbnail_index !== draf.original?.thumbnail_index) formData.thumbnail_index = draf.formData.thumbnail_index;
    if (draf.formData?.stiker_photo_index !== draf.original?.stiker_photo_index) formData.stiker_photo_index = draf.formData.stiker_photo_index;
  }
  if (mediaLoaded && Number(formData.thumbnail_index) >= items.length) formData.thumbnail_index = 0;
  const fotoDisusun = baru.length > 0 || items.length !== existingItems.length;
  return { formData, items, diubah, bentrok, versiBerubah, fotoDisusun, checklist: draf.checklist };
}

/** Terapkan draf aset BARU di atas form kosong. */
export function pulihkanDrafBaru({ draf, emptyForm }) {
  const formData = { ...emptyForm };
  for (const k of ASSET_SCALAR_FIELDS) {
    if (draf.formData && k in draf.formData) formData[k] = draf.formData[k];
  }
  formData.photos = (draf.fotoBaru || []).map((f) => f.newData).slice(0, 6);
  formData.thumbnail_index = Math.min(Number(draf.formData?.thumbnail_index) || 0, Math.max(0, formData.photos.length - 1));
  formData.stiker_photo_index = draf.formData?.stiker_photo_index ?? null;
  if (Array.isArray(draf.checklist)) formData.document_checklist = draf.checklist;
  return formData;
}

export function drafBasi(rec, now = Date.now()) {
  return !rec || !rec.updatedAt || now - rec.updatedAt > DRAF_TTL_MS;
}

// ───────────────────────── Penyimpanan (IndexedDB) ─────────────────────────

const DB_NAME = "aman_draf_aset";
const STORE = "draf";
let dbPromise = null;
function getDB() {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, 1, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: "key" });
      },
    }).catch((e) => { dbPromise = null; throw e; });
  }
  return dbPromise;
}

// Indeks id aset ber-draf untuk chip "Draf" di daftar (tanpa threading prop).
let indeks = new Set();
const pendengar = new Set();
function umumkan() { pendengar.forEach((fn) => { try { fn(); } catch { /* diam */ } }); }
function tandai(assetId, ada) {
  if (!assetId) return;
  if (ada === indeks.has(assetId)) return;
  indeks = new Set(indeks);
  if (ada) indeks.add(assetId); else indeks.delete(assetId);
  umumkan();
}

export async function simpanDraf(rec) {
  const db = await getDB();
  await db.put(STORE, rec);
  tandai(rec.assetId, true);
}

export async function muatDraf(key) {
  try {
    const db = await getDB();
    const rec = await db.get(STORE, key);
    if (!rec) return null;
    if (drafBasi(rec)) { await db.delete(STORE, key); tandai(rec.assetId, false); return null; }
    return rec;
  } catch { return null; }
}

export async function hapusDraf(key) {
  try {
    const db = await getDB();
    const rec = await db.get(STORE, key);
    await db.delete(STORE, key);
    if (rec?.assetId) tandai(rec.assetId, false);
  } catch { /* diam — draf basi dibersihkan TTL */ }
}

/** Muat indeks chip "Draf" untuk pengguna ini (dipanggil saat dasbor dibuka). */
export async function muatIndeksDraf(userId) {
  try {
    const db = await getDB();
    const semua = await db.getAll(STORE);
    const now = Date.now();
    const ids = new Set();
    for (const rec of semua) {
      if (drafBasi(rec, now)) { db.delete(STORE, rec.key).catch(() => {}); continue; }
      if (rec.userId === (userId || "anon") && rec.assetId) ids.add(rec.assetId);
    }
    indeks = ids;
    umumkan();
  } catch { /* IDB tak tersedia (mode privat) — chip tak tampil, form tetap jalan */ }
}

/** Logout eksplisit (perangkat berbagi): buang semua draf. */
export async function hapusSemuaDraf() {
  indeks = new Set();
  umumkan();
  try { const db = await getDB(); await db.clear(STORE); } catch { /* diam */ }
}

function langgan(fn) { pendengar.add(fn); return () => pendengar.delete(fn); }

/** true bila aset ini punya draf belum disimpan di perangkat ini. */
export function useAdaDraf(assetId) {
  return useSyncExternalStore(langgan, () => !!assetId && indeks.has(assetId), () => false);
}

// Preferensi SESI INI: "jangan tanya lagi, simpan sebagai draf saat keluar".
// Sengaja sessionStorage (bukan permanen): pengguna yang lelah dengan dialog
// bisa mematikannya untuk sesi kerja ini tanpa kehilangan pengaman selamanya.
const PREF_KEY = "aman_draf_keluar_otomatis";
export function keluarOtomatisSesiIni() {
  try { return sessionStorage.getItem(PREF_KEY) === "1"; } catch { return false; }
}
export function setKeluarOtomatisSesiIni(on) {
  try { if (on) sessionStorage.setItem(PREF_KEY, "1"); else sessionStorage.removeItem(PREF_KEY); } catch { /* diam */ }
}
