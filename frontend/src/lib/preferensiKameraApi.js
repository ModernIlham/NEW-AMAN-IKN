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

export function bacaCache() {
  try {
    const raw = localStorage.getItem(kunci());
    return raw ? normalkanPreferensi(JSON.parse(raw)) : { ...PREFERENSI_BAWAAN };
  } catch { return { ...PREFERENSI_BAWAAN }; }
}

function tulisCache(p) {
  try { localStorage.setItem(kunci(), JSON.stringify(p)); } catch { /* diam */ }
}

/**
 * Preferensi terkini. Mengembalikan nilai server bila terjangkau; bila tidak
 * (luring / server bermasalah), salinan lokal — kamera TIDAK BOLEH gagal
 * dibuka hanya karena setelan tak bisa diambil.
 */
export async function muatPreferensi() {
  try {
    const r = await axios.get(`${API}/auth/preferensi-kamera`, { timeout: 8000 });
    const p = normalkanPreferensi(r.data);
    tulisCache(p);
    return p;
  } catch {
    return bacaCache();
  }
}

/**
 * Simpan preferensi. Salinan lokal ditulis LEBIH DULU supaya perubahan langsung
 * berlaku pada jepretan berikutnya walau server sedang tak terjangkau; hasilnya
 * dikembalikan agar pemanggil tahu apakah sudah tersimpan ke akun.
 */
export async function simpanPreferensi(pref) {
  const p = normalkanPreferensi(pref);
  tulisCache(p);
  try {
    const r = await axios.put(`${API}/auth/preferensi-kamera`, p, { timeout: 8000 });
    const server = normalkanPreferensi(r.data);
    tulisCache(server);
    return { pref: server, tersimpanKeAkun: true };
  } catch {
    return { pref: p, tersimpanKeAkun: false };
  }
}
