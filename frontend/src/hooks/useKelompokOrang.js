/**
 * Penjawab kelompok bersama (rencana 3.8 butir 3, PGW-08).
 *
 * Satu penampung untuk SEMUA layar: nomor identitas yang sedang tampil
 * dikumpulkan, ditanyakan ke `POST /direktori-pegawai/kelompok` sekali per
 * tumpukan (ditunda sebentar, tanpa kembar, maks. 500 per permintaan), dan
 * jawabannya diingat — termasuk "tak dikenal" (null) — di memori dan di
 * perangkat untuk luring. Penyimpanan perangkat boleh ditolak: layar tetap
 * benar, hanya bertanya ulang.
 */
import { useEffect, useMemo, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const KUNCI_SIMPAN = "aman.kelompokOrang.v1";
const TUNDA_MS = 40;
const BATAS = 500;
const SEGAR_MS = 24 * 3600 * 1000;      // jawaban tersimpan dianggap segar 24 jam
const JEDA_GAGAL_MS = 60 * 1000;        // nomor yang gagal ditanya tak diulang segera

const jawaban = new Map();   // nomor → { k: kunci|null, t: waktu }
const gagal = new Map();     // nomor → waktu gagal
const antre = new Set();
const dalamPerjalanan = new Set();
const pendengar = new Set();
let jam = null;
let termuat = false;

function muatSimpanan() {
  if (termuat) return;
  termuat = true;
  try {
    const v = JSON.parse(window.localStorage.getItem(KUNCI_SIMPAN) || "{}");
    for (const [n, isi] of Object.entries(v || {})) {
      if (isi && typeof isi.t === "number") jawaban.set(n, { k: isi.k ?? null, t: isi.t });
    }
  } catch { /* simpanan rusak/ditolak — mulai kosong */ }
}

function tulisSimpanan() {
  try {
    const obj = {};
    for (const [n, isi] of jawaban) obj[n] = isi;
    window.localStorage.setItem(KUNCI_SIMPAN, JSON.stringify(obj));
  } catch { /* penyimpanan perangkat ditolak — memori tetap berlaku */ }
}

const kabari = () => pendengar.forEach((f) => f());

const bersih = (n) => {
  const s = String(n ?? "").trim();
  return s && !/^[.\-_ ]+$/.test(s) ? s : "";
};

function perluDitanya(n, kini) {
  if (dalamPerjalanan.has(n)) return false;
  const g = gagal.get(n);
  if (g && kini - g < JEDA_GAGAL_MS) return false;
  const j = jawaban.get(n);
  return !j || kini - j.t > SEGAR_MS;
}

async function kirim() {
  jam = null;
  const nomor = [...antre];
  antre.clear();
  for (let i = 0; i < nomor.length; i += BATAS) {
    const potong = nomor.slice(i, i + BATAS);
    potong.forEach((n) => dalamPerjalanan.add(n));
    try {
      const r = await axios.post(`${API}/direktori-pegawai/kelompok`, { nomor: potong });
      const peta = r.data?.nomor || {};
      const t = Date.now();
      potong.forEach((n) => { jawaban.set(n, { k: peta[n] || null, t }); gagal.delete(n); });
      tulisSimpanan();
    } catch {
      const t = Date.now();
      potong.forEach((n) => gagal.set(n, t));
    } finally {
      potong.forEach((n) => dalamPerjalanan.delete(n));
      kabari();
    }
  }
}

function minta(nomorList) {
  muatSimpanan();
  const kini = Date.now();
  let ada = false;
  for (const raw of nomorList) {
    const n = bersih(raw);
    if (n && perluDitanya(n, kini) && !antre.has(n)) { antre.add(n); ada = true; }
  }
  if (ada && !jam) jam = setTimeout(kirim, TUNDA_MS);
}

/**
 * Kunci ikon untuk satu nomor: string kunci, `null` = sudah ditanya dan tak
 * dikenal, `undefined` = belum diketahui (belum ditanya / gagal / luring).
 */
export function bacaKelompok(nomor) {
  muatSimpanan();
  const j = jawaban.get(bersih(nomor));
  return j ? j.k : undefined;
}

/** Daftar nomor yang tampil → peta {nomor: kunci|null|undefined}. */
export default function useKelompokOrang(nomorList) {
  const [, setDetak] = useState(0);
  const kunci = useMemo(() => [...new Set((nomorList || []).map(bersih).filter(Boolean))].sort().join("|"),
    [nomorList]);
  useEffect(() => {
    const f = () => setDetak((x) => x + 1);
    pendengar.add(f);
    return () => { pendengar.delete(f); };
  }, []);
  useEffect(() => { if (kunci) minta(kunci.split("|")); }, [kunci]);
  // Dihitung tiap render (murah): `jawaban` berubah di luar React dan detak
  // di atas yang memicu render ulang.
  const peta = {};
  if (kunci) kunci.split("|").forEach((n) => { peta[n] = bacaKelompok(n); });
  return peta;
}

/** Hanya untuk uji: kosongkan penampung modul. */
export function _setelUlangPenampung() {
  jawaban.clear(); gagal.clear(); antre.clear(); dalamPerjalanan.clear();
  if (jam) clearTimeout(jam);
  jam = null; termuat = false;
}
