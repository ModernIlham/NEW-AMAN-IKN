/**
 * Ranah Master Pegawai: internal, instansi eksternal, pihak ketiga (PGW-07).
 *
 * Satu sumber jalur API dan parameter lingkup untuk layar Master Pegawai.
 * Untuk ranah INTERNAL hasilnya persis jalur lama (`/pegawai`, `/unit-kerja`)
 * — layar internal tidak boleh berubah perilaku.
 *
 * Rencana: docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md — 3.10, PGW-07.
 */

export const KELOMPOK = [
  { kunci: "internal", label: "Pegawai Internal", ringkas: "Internal" },
  { kunci: "eksternal", label: "Instansi Eksternal", ringkas: "Eksternal" },
  { kunci: "pihak_ketiga", label: "Pihak Ketiga", ringkas: "Pihak Ketiga" },
];

export const TATARAN = [
  { kunci: "pusat", label: "Pusat (Kementerian/Lembaga)", ringkas: "Pusat" },
  { kunci: "daerah", label: "Daerah (Pemda)", ringkas: "Daerah" },
];

export const EMPTY_PIHAK_KETIGA = {
  kapasitas_bertindak: "",
  dasar_kewenangan_jenis: "",
  dasar_kewenangan_nomor: "",
  dasar_kewenangan_tanggal: "",
};

const KUNCI_KELOMPOK = new Set(KELOMPOK.map((k) => k.kunci));
const KUNCI_TATARAN = new Set(TATARAN.map((t) => t.kunci));

export function adalahLuar(kelompok) {
  return kelompok === "eksternal" || kelompok === "pihak_ketiga";
}

export function ranah(kelompok) {
  const k = KUNCI_KELOMPOK.has(kelompok) ? kelompok : "internal";
  const luar = adalahLuar(k);
  return {
    kelompok: k,
    luar,
    pegawai: luar ? "/pegawai-luar" : "/pegawai",
    unit: luar ? "/unit-kerja-luar" : "/unit-kerja",
  };
}

/** Parameter kueri daftar orang luar menurut lingkup aktif. Internal → {}. */
export function paramLingkup(kelompok, tataran, lingkup = {}) {
  if (!adalahLuar(kelompok)) return {};
  const p = { kelompok };
  if (kelompok === "eksternal" && KUNCI_TATARAN.has(tataran)) p.tataran = tataran;
  if (lingkup.provinsi?.id) p.provinsi_id = lingkup.provinsi.id;
  if (lingkup.instansi?.id) p.instansi_id = lingkup.instansi.id;
  if (lingkup.satker?.id) p.satker_luar_id = lingkup.satker.id;
  return p;
}

/** Kunci label_tingkat dari /luar/referensi untuk lingkup aktif. */
export function kunciTingkat(kelompok, tataran) {
  if (kelompok === "pihak_ketiga") return "pihak_ketiga";
  if (kelompok === "eksternal") return tataran === "daerah" ? "eksternal_daerah" : "eksternal_pusat";
  return "";
}

/** "Kementerian X — Sekretariat"; kab/kota & desa menyebut provinsinya. */
export function labelLingkup(lingkup = {}) {
  const i = lingkup.instansi;
  if (!i) return "";
  let nama = i.nama || "";
  if (["pemerintah_kabkota", "pemerintah_desa"].includes(i.jenis) && i.provinsi_nama
      && !nama.includes(i.provinsi_nama)) {
    nama = `${nama}, ${i.provinsi_nama}`;
  }
  return lingkup.satker ? `${nama} — ${lingkup.satker.nama_satker || ""}` : nama;
}

const KUNCI_SIMPAN = "aman.pegawai.ranah";

/** Pilihan tersimpan di perangkat — selalu aman bila penyimpanan ditolak. */
export function bacaPilihan() {
  try {
    const v = JSON.parse(window.localStorage.getItem(KUNCI_SIMPAN) || "null");
    if (!v || !KUNCI_KELOMPOK.has(v.kelompok)) return null;
    return { kelompok: v.kelompok,
             tataran: KUNCI_TATARAN.has(v.tataran) ? v.tataran : "pusat" };
  } catch {
    return null;
  }
}

export function simpanPilihan(kelompok, tataran) {
  try {
    window.localStorage.setItem(KUNCI_SIMPAN, JSON.stringify({ kelompok, tataran }));
  } catch {
    /* penyimpanan perangkat ditolak — pilihan tetap berlaku di sesi ini */
  }
}
