/**
 * Form "Ubah Perolehan" tidak boleh mengirim lebih dari yang diminta.
 *
 * Dua kesalahan yang mahal dan tak terlihat di layar: mengirim ulang daftar
 * barang yang sudah terkunci, dan ikut mengirim id PPK/penganggaran yang akan
 * menimpa snapshot beku pada dokumen. Keduanya baru ketahuan berbulan kemudian
 * saat ada yang membandingkan register dengan BAST cetaknya.
 */
import {
  dokumenSetelahGantiSifat, formDariPerolehan, payloadUbahPerolehan,
} from "./perolehanUbah";

const PEROLEHAN = {
  id: "p1",
  jenis: "pembelian",
  pihak: "PT Sumber Rejeki",
  nomor_kontrak: "KTR-001",
  nomor_bast: "BAST-001",
  tanggal_bast: "2026-03-10T00:00:00",
  keterangan: "",
  ppk_nama: "Budi Santoso",
  ppk_pejabat_id: "pj-ppk",
  barang: [{ uraian: "Printer", kode: "3050102001", jumlah: 2, harga_satuan: 2500000 }],
  ubah: { identitas: true, barang: true, alasan: "" },
};

describe("formDariPerolehan", () => {
  test("tanggal dipotong ke YYYY-MM-DD agar terbaca input date", () => {
    expect(formDariPerolehan(PEROLEHAN).data.tanggal_bast).toBe("2026-03-10");
  });

  test("angka jadi string supaya input terkendali tidak melompat ke tak-terkendali", () => {
    const b = formDariPerolehan(PEROLEHAN).barang[0];
    expect(b.jumlah).toBe("2");
    expect(b.harga_satuan).toBe("2500000");
  });

  test("register tanpa status kunci dianggap terbuka", () => {
    const { ubah, ...tanpaStatus } = PEROLEHAN;
    expect(formDariPerolehan(tanpaStatus).kunci).toEqual(
      { identitas: true, barang: true, alasan: "" });
  });
});

describe("payloadUbahPerolehan", () => {
  test("daftar barang terkunci dikirim sebagai null, bukan disalin ulang", () => {
    const form = formDariPerolehan({
      ...PEROLEHAN,
      ubah: { identitas: true, barang: false, alasan: "sudah tercatat" },
    });
    expect(payloadUbahPerolehan(form).barang).toBeNull();
  });

  test("daftar barang bebas dikirim sebagai angka, bukan teks", () => {
    const form = formDariPerolehan(PEROLEHAN);
    expect(payloadUbahPerolehan(form).barang).toEqual([
      { uraian: "Printer", kode: "3050102001", jumlah: 2, harga_satuan: 2500000 },
    ]);
  });

  test("id PPK & penganggaran TIDAK ikut terkirim", () => {
    const form = formDariPerolehan(PEROLEHAN);
    form.data.ppk_pejabat_id = "pj-lain";      // seandainya form tercemar
    form.data.penganggaran_id = "usulan-lain";
    const p = payloadUbahPerolehan(form);
    expect(p).not.toHaveProperty("ppk_pejabat_id");
    expect(p).not.toHaveProperty("penganggaran_id");
    // Daftar kunci DIKUNCI: yang dijaga uji ini bukan sekadar dua id di
    // atas, melainkan bahwa payload tak pernah membawa kunci yang tak
    // sengaja. Menambah kolom berarti sengaja memperbarui daftar ini.
    expect(Object.keys(p).sort()).toEqual([
      "barang", "jenis", "jenis_up", "keterangan", "no_bukti", "no_dokumen",
      "no_sp_spk", "no_spby", "no_spm", "no_spp", "nomor_bast",
      "nomor_kontrak", "pihak", "sifat", "tanggal_bast",
    ]);
  });

  test("dokumen pengadaan IKUT terkirim, bukan terjatuh", () => {
    // Server menulis ulang seluruh kolomnya; kolom yang tak terkirim akan
    // MENGOSONGKAN dokumen yang sudah tercatat.
    const form = formDariPerolehan({ ...PEROLEHAN, sifat: "non_kontrak",
      jenis_up: "tup", no_spby: " SPBy-1 ", no_spm: "02847T/621001/2024" });
    const p = payloadUbahPerolehan(form);
    expect(p.sifat).toBe("non_kontrak");
    expect(p.jenis_up).toBe("tup");
    expect(p.no_spby).toBe("SPBy-1");
    expect(p.no_spm).toBe("02847T/621001/2024");
  });

  test("No. Bukti/Faktur ikut terkirim", () => {
    // Kolom BARU (permintaan pemilik: "ini tidak ada inputan tambah
    // pengadaan, tolong tambahkan"). Server menulis ulang seluruh kolom
    // dokumen; yang tak terkirim akan MENGOSONGKAN nomor yang sudah tercatat.
    const form = formDariPerolehan({ ...PEROLEHAN, no_bukti: "INV-2026/08/0417" });
    expect(payloadUbahPerolehan(form).no_bukti).toBe("INV-2026/08/0417");
  });
});

describe("dokumenSetelahGantiSifat", () => {
  const ISI = { sifat: "", no_sp_spk: "SPK-1", jenis_up: "up",
    no_spby: "SPBy-1", no_spp: "SPP-1", no_spm: "SPM-1", no_dokumen: "ND-1" };

  test("berpindah ke kontrak membuang UP/TUP dan SPBy", () => {
    const d = dokumenSetelahGantiSifat(ISI, "kontrak");
    expect(d.jenis_up).toBe("");
    expect(d.no_spby).toBe("");
    expect(d.no_sp_spk).toBe("SPK-1");
  });

  test("berpindah ke non-kontrak membuang SP/SPK", () => {
    const d = dokumenSetelahGantiSifat(ISI, "non_kontrak");
    expect(d.no_sp_spk).toBe("");
    expect(d.jenis_up).toBe("up");
  });

  test("kolom yang berlaku di KEDUA jalur tak pernah dibuang", () => {
    for (const s of ["kontrak", "non_kontrak", ""]) {
      const d = dokumenSetelahGantiSifat(ISI, s);
      expect([d.no_spp, d.no_spm, d.no_dokumen]).toEqual(["SPP-1", "SPM-1", "ND-1"]);
    }
  });

  test("kembali ke 'belum ditetapkan' tak membuang apa pun", () => {
    // Operator yang ragu lalu mengosongkan pilihannya tak boleh kehilangan
    // apa yang sudah diketiknya.
    expect(dokumenSetelahGantiSifat(ISI, "")).toEqual({ ...ISI, sifat: "" });
  });
});
