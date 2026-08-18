/**
 * Form "Ubah Perolehan" tidak boleh mengirim lebih dari yang diminta.
 *
 * Dua kesalahan yang mahal dan tak terlihat di layar: mengirim ulang daftar
 * barang yang sudah terkunci, dan ikut mengirim id PPK/penganggaran yang akan
 * menimpa snapshot beku pada dokumen. Keduanya baru ketahuan berbulan kemudian
 * saat ada yang membandingkan register dengan BAST cetaknya.
 */
import { formDariPerolehan, payloadUbahPerolehan } from "./perolehanUbah";

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
    expect(Object.keys(p).sort()).toEqual([
      "barang", "jenis", "keterangan", "nomor_bast", "nomor_kontrak",
      "pihak", "tanggal_bast",
    ]);
  });
});
