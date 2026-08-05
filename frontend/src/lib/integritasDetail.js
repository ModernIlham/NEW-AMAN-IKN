/**
 * Peta & perataan hasil endpoint detail integritas (§5A).
 *
 * Dasbor Integritas di panel Riwayat hanya menampilkan HITUNGAN per register,
 * lalu menutupnya dengan kalimat "Detail per temuan tersedia via endpoint
 * /integritas/*" — petunjuk yang hanya berguna bagi orang yang bisa memanggil
 * API sendiri. Enam endpoint detailnya sudah ada di backend sejak §5A, tetapi
 * tak satu pun pernah punya pemanggil di UI: operator melihat "12 temuan" dan
 * berhenti di situ, tanpa cara tahu aset mana yang bermasalah.
 *
 * Berkas ini memegang bagian MURNI-nya — peta register → endpoint, pembacaan
 * cacah yang KUNCINYA BERBEDA per register, dan perataan bentuk item yang tak
 * seragam — supaya bisa diuji tanpa me-render panel.
 *
 * Bentuk item per register (dari backend/routes/audit.py):
 *   usulan_penghapusan   {usulan_id, asset_id, status, masalah, snapshot|drift}
 *   pemindahtanganan     {pemindahtanganan_id, bentuk, status, asset_id, …}
 *   psp                  {psp_id, nomor_sk, status_pengajuan, asset_id, …}
 *   jadwal_pemeliharaan  {jadwal_id, asset_id, jatuh_tempo, …}
 *   kodefikasi_aset      {asset_code, jumlah_aset, level_kode, level_terdaftar}
 *   kategori_kodefikasi  {kode_aset, label, masalah}
 */

/** Label manusiawi field identitas yang di-snapshot register hilir. */
export const LABEL_FIELD_IDENTITAS = {
  asset_code: "Kode Barang",
  NUP: "NUP",
  asset_name: "Nama Barang",
};

const URUT_FIELD = ["asset_code", "NUP", "asset_name"];

/** Baris temuan yang dirender per register (sisanya diringkas "+N lainnya"). */
export const MAKS_TEMUAN_TAMPIL = 50;

/**
 * Register (kunci `bagian[].register` dari /integritas/ringkasan) → endpoint
 * detail + cara membaca cacahnya.
 *
 * `kunciJumlah` berbeda-beda: register identitas memakai `jumlah`, kodefikasi
 * aset `jumlah_kode`, kategori `jumlah_bermasalah`. Membaca `jumlah` untuk
 * semuanya akan menampilkan "0 temuan" pada dua register terakhir padahal
 * daftarnya terisi.
 */
export const DETAIL_INTEGRITAS = {
  usulan_penghapusan: {
    jalur: "identitas-penghapusan", kunciId: "usulan_id",
    labelId: "Usulan", kunciJumlah: "jumlah",
  },
  pemindahtanganan: {
    jalur: "identitas-pemindahtanganan", kunciId: "pemindahtanganan_id",
    labelId: "Usulan", kunciJumlah: "jumlah",
  },
  psp: {
    jalur: "identitas-psp", kunciId: "psp_id",
    labelId: "SK", kunciJumlah: "jumlah",
  },
  jadwal_pemeliharaan: {
    jalur: "identitas-jadwal-pemeliharaan", kunciId: "jadwal_id",
    labelId: "Jadwal", kunciJumlah: "jumlah",
  },
  kodefikasi_aset: { jalur: "kodefikasi-aset", kunciJumlah: "jumlah_kode" },
  kategori_kodefikasi: {
    jalur: "kategori-kodefikasi", kunciJumlah: "jumlah_bermasalah",
  },
};

/** Path endpoint detail (relatif ke base API), "" bila register tak dikenal. */
export function jalurDetail(register) {
  const d = DETAIL_INTEGRITAS[register];
  return d ? `/integritas/${d.jalur}` : "";
}

/** Cacah temuan dari respons detail — kunci berbeda per register. */
export function jumlahDetail(register, data) {
  const d = DETAIL_INTEGRITAS[register];
  const dt = data || {};
  const mentah = d ? dt[d.kunciJumlah] : undefined;
  // `Number(null)` = 0 (dan finite), jadi cacah yang hilang akan terbaca "0
  // temuan" padahal `items` terisi — saring dulu nilai hampa.
  const n = mentah === null || mentah === undefined || mentah === ""
    ? NaN : Number(mentah);
  if (Number.isFinite(n)) return n;
  return Array.isArray(dt.items) ? dt.items.length : 0;
}

const _rapikan = (v) => String(v ?? "").replace(/_/g, " ").trim();

/** Ambil nilai identitas: field yang basi ada di `drift`, sisanya di `snapshot`. */
function _identitas(item, field) {
  const d = (item.drift || {})[field];
  if (d) return String(d.snapshot ?? "").trim();
  return String((item.snapshot || {})[field] ?? "").trim();
}

function _barisIdentitas(register, item) {
  const cfg = DETAIL_INTEGRITAS[register] || {};
  const kode = _identitas(item, "asset_code");
  const nup = _identitas(item, "NUP");
  const nama = _identitas(item, "asset_name");
  const id = String(item[cfg.kunciId] || "");
  const pendek = id ? id.slice(0, 8) : "";

  // Untuk temuan `snapshot_basi`, backend HANYA mengirim field yang berbeda —
  // bila yang basi cuma nama, kode & NUP tak ada sama sekali. Judul karena itu
  // turun bertahap sampai nomor record; jangan pernah kosong. NUP tanpa kode
  // diberi awalan agar "12" tak terbaca sebagai potongan kode barang.
  let judul;
  if (kode && nup) judul = `${kode} / ${nup}`;
  else if (kode) judul = kode;
  else if (nup) judul = `NUP ${nup}`;
  else if (nama) judul = nama;
  else judul = pendek ? `${cfg.labelId || "Record"} ${pendek}` : "(identitas kosong)";

  const konteks = [];
  if (item.nomor_sk) konteks.push(`SK ${item.nomor_sk}`);
  if (item.bentuk) konteks.push(_rapikan(item.bentuk));
  if (item.status) konteks.push(_rapikan(item.status));
  if (item.status_pengajuan) konteks.push(_rapikan(item.status_pengajuan));
  if (item.jatuh_tempo) konteks.push(`jatuh tempo ${item.jatuh_tempo}`);
  if (pendek && judul.indexOf(pendek) === -1) {
    konteks.push(`${cfg.labelId || "Record"} ${pendek}`);
  }

  let beda = [];
  if (item.masalah === "aset_master_hilang") {
    const snap = item.snapshot || {};
    beda = URUT_FIELD
      .filter((f) => String(snap[f] ?? "").trim())
      .map((f) => ({ label: LABEL_FIELD_IDENTITAS[f], dari: String(snap[f]).trim(),
                     ke: "(master tak ada)" }));
  } else {
    const drift = item.drift || {};
    beda = URUT_FIELD.filter((f) => drift[f]).map((f) => ({
      label: LABEL_FIELD_IDENTITAS[f],
      dari: String(drift[f].snapshot ?? "").trim() || "(kosong)",
      ke: String(drift[f].master ?? "").trim() || "(kosong)",
    }));
  }
  return { judul, subjudul: konteks.join(" · "), masalah: item.masalah || "", beda };
}

/**
 * Ratakan satu item detail jadi bentuk seragam untuk dirender:
 * `{judul, subjudul, masalah, beda: [{label, dari, ke}]}`.
 *
 * `beda` berisi perbandingan snapshot vs master (temuan identitas) — itulah
 * isi yang bisa ditindaklanjuti; kosong untuk temuan kodefikasi yang cukup
 * ditunjukkan kode + volumenya.
 */
export function barisTemuan(register, item) {
  const it = item || {};
  if (register === "kodefikasi_aset") {
    const jml = Number(it.jumlah_aset || 0);
    return {
      judul: String(it.asset_code || "").trim() || "(tanpa kode)",
      subjudul: jml ? `${jml} aset memakai kode ini` : "",
      masalah: it.masalah || "",
      beda: [],
    };
  }
  if (register === "kategori_kodefikasi") {
    return {
      judul: String(it.kode_aset || "").trim() || "(tanpa kode)",
      subjudul: String(it.label || "").trim(),
      masalah: it.masalah || "",
      beda: [],
    };
  }
  return _barisIdentitas(register, it);
}
