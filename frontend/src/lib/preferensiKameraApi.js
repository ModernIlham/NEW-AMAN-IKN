/**
 * Muat & simpan preferensi kamera yang MELEKAT PADA AKUN.
 *
 * Server adalah sumber kebenarannya (agar setelan ikut pindah HP), tetapi
 * kamera dipakai di lapangan yang sinyalnya sering hilang — jadi salinan lokal
 * disimpan PER AKUN dan dipakai saat luring. Kuncinya memuat id pengguna:
 * satu HP yang dipakai bergantian dua petugas tak boleh saling mewarisi
 * setelan.
 */
import axios from "axios";

import { PREFERENSI_BAWAAN, normalkanPreferensi } from "./preferensiKamera";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function idPengguna() {
  try {
    const u = JSON.parse(localStorage.getItem("user") || "null");
    return (u && (u.id || u.username)) || "anon";
  } catch { return "anon"; }
}

const kunci = () => `aman_preferensi_kamera_${idPengguna()}`;
const revisi = new Map();
const antrean = new Map();

export function bacaCache(key = kunci()) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? normalkanPreferensi(JSON.parse(raw)) : { ...PREFERENSI_BAWAAN };
  } catch { return { ...PREFERENSI_BAWAAN }; }
}

function tulisCache(p, key) {
  try { localStorage.setItem(key, JSON.stringify(p)); } catch { /* diam */ }
}

/**
 * Preferensi terkini. Mengembalikan nilai server bila terjangkau; bila tidak
 * (luring / server bermasalah), salinan lokal — kamera TIDAK BOLEH gagal
 * dibuka hanya karena setelan tak bisa diambil.
 */
export async function muatPreferensi() {
  const key = kunci(), versi = revisi.get(key) || 0;
  // Edit luring tidak dibuang oleh GET akun lama ketika koneksi pulih.
  try {
    if (localStorage.getItem(`${key}_tertunda`) === "1") return (await simpanPreferensi(bacaCache(key))).pref;
  } catch { /* cache tidak tersedia */ }
  try {
    const r = await axios.get(`${API}/auth/preferensi-kamera`, { timeout: 8000 });
    const p = normalkanPreferensi(r.data);
    if ((revisi.get(key) || 0) !== versi || antrean.has(key)) return bacaCache(key);
    tulisCache(p, key);
    return p;
  } catch {
    return bacaCache(key);
  }
}

/**
 * Simpan preferensi. Salinan lokal ditulis LEBIH DULU supaya perubahan langsung
 * berlaku pada jepretan berikutnya walau server sedang tak terjangkau; hasilnya
 * dikembalikan agar pemanggil tahu apakah sudah tersimpan ke akun.
 */
export async function simpanPreferensi(pref) {
  const key = kunci(), versi = (revisi.get(key) || 0) + 1;
  revisi.set(key, versi);
  const p = normalkanPreferensi(pref);
  tulisCache(p, key);
  try { localStorage.setItem(`${key}_tertunda`, "1"); } catch { /* diam */ }
  const pekerjaan = (antrean.get(key) || Promise.resolve()).catch(() => {}).then(async () => {
    // Jangan mengirim setelan akun lama lewat sesi akun yang baru login.
    if (kunci() !== key || revisi.get(key) !== versi) return { pref: bacaCache(key), tersimpanKeAkun: false };
    try {
      const r = await axios.put(`${API}/auth/preferensi-kamera`, p, { timeout: 8000 });
      const server = normalkanPreferensi(r.data);
      if (revisi.get(key) === versi) {
        tulisCache(server, key);
        try { localStorage.removeItem(`${key}_tertunda`); } catch { /* diam */ }
      }
      return { pref: server, tersimpanKeAkun: true };
    } catch { return { pref: p, tersimpanKeAkun: false }; }
  });
  antrean.set(key, pekerjaan);
  try { return await pekerjaan; }
  finally { if (antrean.get(key) === pekerjaan) antrean.delete(key); }
}
