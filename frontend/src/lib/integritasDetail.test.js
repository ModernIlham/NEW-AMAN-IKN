/**
 * Dasbor Integritas harus BISA DITELUSURI, bukan sekadar menghitung.
 *
 * Enam endpoint detail §5A (`/integritas/identitas-*`, `/integritas/
 * kodefikasi-aset`, `/integritas/kategori-kodefikasi`) sudah ada di backend
 * tetapi tak pernah punya pemanggil di UI: panel hanya menampilkan angka lalu
 * menyuruh operator memanggil API-nya sendiri. Berkas ini menjaga bagian murni
 * dari drill-down-nya:
 *
 *   1. TIAP register di ringkasan punya endpoint detail — register yang luput
 *      dari peta akan jadi kartu yang tak bisa dibuka, persis keadaan lama.
 *   2. Cacah dibaca dengan KUNCI YANG BENAR per register — `jumlah` untuk
 *      register identitas, `jumlah_kode` / `jumlah_bermasalah` untuk kodefikasi.
 *   3. Bentuk item yang berbeda-beda diratakan tanpa kehilangan isi yang bisa
 *      ditindaklanjuti (snapshot vs master).
 */
const {
  DETAIL_INTEGRITAS, LABEL_FIELD_IDENTITAS, MAKS_TEMUAN_TAMPIL,
  barisTemuan, jalurDetail, jumlahDetail,
} = require("./integritasDetail");

const fs = require("fs");
const path = require("path");

// Register yang didaftarkan `_kumpulkan_bagian_integritas` di backend.
const AUDIT_PY = path.join(__dirname, "..", "..", "..", "backend", "routes", "audit.py");

/** Kunci `register` yang benar-benar dikirim endpoint ringkasan. */
function registerBackend() {
  const src = fs.readFileSync(AUDIT_PY, "utf8");
  const blok = src.split("async def _kumpulkan_bagian_integritas")[1].split("\n@")[0];
  const keluar = new Set();
  // Pemanggilan helper: ("coll", "register", "Label", …) — argumen kedua.
  for (const m of blok.matchAll(/_ringkas_identitas_\w+\(\s*\n?\s*"([\w]+)",\s*"([\w]+)"/g)) {
    keluar.add(m[2]);
  }
  // Dua helper kodefikasi menetapkan register-nya di dalam badan fungsinya.
  if (/_ringkas_kodefikasi\(/.test(blok)) keluar.add("kodefikasi_aset");
  if (/_ringkas_kategori_kodefikasi\(/.test(blok)) keluar.add("kategori_kodefikasi");
  return [...keluar];
}

describe("peta register → endpoint detail", () => {
  const backend = registerBackend();

  test("penjaga ini tidak kosong — register backend memang terbaca", () => {
    // Tanpa ini, gagal-baca membuat daftar jadi kosong dan uji cakupan di bawah
    // lolos tanpa memeriksa apa pun.
    expect(backend.length).toBe(6);
    expect(backend).toContain("usulan_penghapusan");
    expect(backend).toContain("kodefikasi_aset");
  });

  test("setiap register punya endpoint detail yang bisa dibuka", () => {
    const buntu = backend.filter((r) => !jalurDetail(r));
    expect(buntu).toEqual([]);
  });

  test("tak ada entri peta yang menunjuk register yang tak ada", () => {
    const yatim = Object.keys(DETAIL_INTEGRITAS).filter((r) => !backend.includes(r));
    expect(yatim).toEqual([]);
  });

  test("jalur detail berawalan /integritas/ dan unik", () => {
    const jalur = Object.keys(DETAIL_INTEGRITAS).map(jalurDetail);
    jalur.forEach((j) => expect(j.startsWith("/integritas/")).toBe(true));
    expect(new Set(jalur).size).toBe(jalur.length);
  });

  test("register tak dikenal tidak memicu panggilan API", () => {
    expect(jalurDetail("entah_apa")).toBe("");
    expect(jalurDetail(undefined)).toBe("");
  });
});

describe("cacah temuan dibaca dengan kunci yang benar", () => {
  test("register identitas memakai `jumlah`", () => {
    expect(jumlahDetail("psp", { jumlah: 4, items: [1, 2] })).toBe(4);
  });

  test("kodefikasi aset memakai `jumlah_kode`, bukan `jumlah`", () => {
    // Respons endpoint ini TIDAK punya field `jumlah` sama sekali — membacanya
    // akan menampilkan "0 temuan" padahal daftarnya terisi.
    const data = { jumlah_kode: 12, items: [{ asset_code: "3050102001" }] };
    expect(jumlahDetail("kodefikasi_aset", data)).toBe(12);
  });

  test("kategori kodefikasi memakai `jumlah_bermasalah` (bukan jumlah_kategori)", () => {
    // `jumlah_kategori` = SELURUH kategori (termasuk yang sehat). Salah baca di
    // sini melaporkan seluruh master kategori sebagai temuan.
    const data = { jumlah_kategori: 900, jumlah_bermasalah: 7, items: [] };
    expect(jumlahDetail("kategori_kodefikasi", data)).toBe(7);
  });

  test("jatuh ke panjang items bila cacah tak ada / bukan angka", () => {
    expect(jumlahDetail("psp", { items: [1, 2, 3] })).toBe(3);
    expect(jumlahDetail("psp", { jumlah: null, items: [1] })).toBe(1);
    expect(jumlahDetail("psp", {})).toBe(0);
    expect(jumlahDetail("psp", undefined)).toBe(0);
  });
});

describe("perataan item — temuan identitas", () => {
  const basi = {
    usulan_id: "3f2a1b9c-0000-4444-8888-abcdefabcdef",
    asset_id: "aset-1", status: "diusulkan", masalah: "snapshot_basi",
    drift: {
      NUP: { snapshot: "12", master: "13" },
      asset_name: { snapshot: "Kursi Kerja", master: "Kursi Rapat" },
    },
  };

  test("perbandingan snapshot vs master tersaji utuh", () => {
    const b = barisTemuan("usulan_penghapusan", basi);
    expect(b.beda).toEqual([
      { label: LABEL_FIELD_IDENTITAS.NUP, dari: "12", ke: "13" },
      { label: LABEL_FIELD_IDENTITAS.asset_name, dari: "Kursi Kerja", ke: "Kursi Rapat" },
    ]);
  });

  test("judul memakai identitas yang tersedia, urut kode / NUP", () => {
    const b = barisTemuan("usulan_penghapusan", {
      ...basi,
      drift: { asset_code: { snapshot: "3050102001", master: "3050102002" },
               NUP: { snapshot: "12", master: "13" } },
    });
    expect(b.judul).toBe("3050102001 / 12");
  });

  test("judul tak pernah kosong walau backend hanya mengirim field yang basi", () => {
    // Bila yang berubah cuma NAMA, `asset_code`/`NUP` tak ikut dikirim sama
    // sekali — kartu tanpa judul akan tampak seperti baris rusak.
    const namaSaja = barisTemuan("usulan_penghapusan", {
      usulan_id: "u1", masalah: "snapshot_basi",
      drift: { asset_name: { snapshot: "Kursi Kerja", master: "Kursi Rapat" } },
    });
    expect(namaSaja.judul).toBe("Kursi Kerja");

    // NUP telanjang diberi awalan — "12" sendirian terbaca seperti potongan
    // kode barang, bukan nomor urut pendaftaran.
    expect(barisTemuan("usulan_penghapusan", basi).judul).toBe("NUP 12");

    const tanpaApaPun = barisTemuan("psp", { psp_id: "abcdefgh-1111", masalah: "snapshot_basi", drift: {} });
    expect(tanpaApaPun.judul).toBe("SK abcdefgh");
  });

  test("aset master hilang menampilkan snapshot beku + penanda master tak ada", () => {
    const b = barisTemuan("jadwal_pemeliharaan", {
      jadwal_id: "j-1", asset_id: "aset-9", jatuh_tempo: "2026-09-01",
      masalah: "aset_master_hilang",
      snapshot: { asset_code: "3100104001", NUP: "7", asset_name: "AC Split" },
    });
    expect(b.judul).toBe("3100104001 / 7");
    expect(b.beda.map((d) => d.ke)).toEqual([
      "(master tak ada)", "(master tak ada)", "(master tak ada)"]);
    expect(b.beda.map((d) => d.dari)).toEqual(["3100104001", "7", "AC Split"]);
    expect(b.subjudul).toContain("jatuh tempo 2026-09-01");
  });

  test("konteks per register ikut: nomor SK, bentuk, status", () => {
    expect(barisTemuan("psp", { psp_id: "p1", nomor_sk: "SK-9/2026",
      status_pengajuan: "menunggu_persetujuan", masalah: "snapshot_basi",
      drift: { NUP: { snapshot: "1", master: "2" } } }).subjudul)
      .toBe("SK SK-9/2026 · menunggu persetujuan · SK p1");
    expect(barisTemuan("pemindahtanganan", { pemindahtanganan_id: "x1",
      bentuk: "hibah", status: "diusulkan", masalah: "snapshot_basi",
      drift: { NUP: { snapshot: "1", master: "2" } } }).subjudul)
      .toBe("hibah · diusulkan · Usulan x1");
  });

  test("nilai kosong ditandai eksplisit, bukan jadi ruang hampa", () => {
    const b = barisTemuan("usulan_penghapusan", {
      usulan_id: "u1", masalah: "snapshot_basi",
      drift: { NUP: { snapshot: "", master: "13" } },
    });
    expect(b.beda[0]).toEqual({ label: "NUP", dari: "(kosong)", ke: "13" });
  });
});

describe("perataan item — temuan kodefikasi", () => {
  test("kodefikasi aset menampilkan kode + volume aset terdampak", () => {
    const b = barisTemuan("kodefikasi_aset", {
      asset_code: "3050102001", jumlah_aset: 24,
      masalah: "kode_spesifik_tak_terdaftar",
    });
    expect(b.judul).toBe("3050102001");
    expect(b.subjudul).toBe("24 aset memakai kode ini");
    expect(b.masalah).toBe("kode_spesifik_tak_terdaftar");
    expect(b.beda).toEqual([]);
  });

  test("kategori kodefikasi menampilkan kode + label kategorinya", () => {
    const b = barisTemuan("kategori_kodefikasi", {
      kode_aset: "3050199", label: "Alat Kantor Lainnya",
      masalah: "golongan_tak_terdaftar",
    });
    expect(b.judul).toBe("3050199");
    expect(b.subjudul).toBe("Alat Kantor Lainnya");
  });

  test("kode kosong tetap punya judul", () => {
    expect(barisTemuan("kodefikasi_aset", {}).judul).toBe("(tanpa kode)");
    expect(barisTemuan("kategori_kodefikasi", { kode_aset: "  " }).judul).toBe("(tanpa kode)");
  });
});

describe("item cacat tidak meruntuhkan panel", () => {
  test.each(Object.keys(DETAIL_INTEGRITAS))("%s: item undefined aman", (reg) => {
    const b = barisTemuan(reg, undefined);
    expect(typeof b.judul).toBe("string");
    expect(b.judul).not.toBe("");
    expect(Array.isArray(b.beda)).toBe(true);
  });
});

describe("batas tampilan", () => {
  test("plafon baris masuk akal (bukan 0, bukan tak terhingga)", () => {
    // 0 = daftar selalu kosong; terlalu besar = panel sempit merender ribuan
    // baris kodefikasi dan macet.
    expect(MAKS_TEMUAN_TAMPIL).toBeGreaterThanOrEqual(20);
    expect(MAKS_TEMUAN_TAMPIL).toBeLessThanOrEqual(200);
  });
});

describe("panel benar-benar memakai peta ini", () => {
  // Repo belum punya uji render komponen, jadi penjaga ini membaca sumbernya:
  // ia hanya menangkap satu kelas kesalahan — modul murni yang lengkap tetapi
  // tak pernah dipanggil, yaitu keadaan yang justru sedang diperbaiki.
  const PANEL = path.join(__dirname, "..", "components", "assets", "AuditLogPanel.jsx");
  const isi = fs.readFileSync(PANEL, "utf8");

  test("mengimpor & memanggil helper drill-down", () => {
    expect(isi).toContain("integritasDetail");
    expect(isi).toContain("jalurDetail(");
    expect(isi).toContain("barisTemuan(");
    expect(isi).toContain("jumlahDetail(");
  });

  test("menyediakan unduhan CSV ringkasan", () => {
    expect(isi).toContain("/integritas/ekspor-ringkasan");
  });

  test("tak lagi menyuruh operator memanggil endpoint sendiri", () => {
    // Kalimat lama: "Detail per temuan tersedia via endpoint /integritas/*".
    // Petunjuk itu hanya berguna bila punya akses API — dan sekarang salah,
    // karena detailnya sudah ada di layar.
    expect(isi).not.toMatch(/Detail per temuan tersedia via endpoint/);
  });
});
