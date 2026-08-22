/**
 * Penanggung jawab tambahan BAST — aturan yang menjaga dokumennya, bukan
 * kerapian layarnya.
 *
 * Dua di antaranya tak terlihat dari membaca komponennya:
 *
 *   1. Satu BMN hanya boleh melekat pada SATU orang. Daftar pilihan yang
 *      menawarkan barang yang sudah diambil orang lain membuat pertanyaan
 *      "siapa yang memegang ini" — pertanyaan yang justru dijawab BAST —
 *      kembali tak terjawab.
 *   2. BMN yang dicabut centangnya harus ikut lepas dari penanggung jawabnya.
 *      Kalau tidak, payload membawa aset di luar daftar dan server menolaknya
 *      dengan pesan yang menunjuk tempat yang SALAH: operator diberi tahu
 *      penanggung jawabnya bermasalah, padahal yang ia ubah daftar asetnya.
 */
import {
  asetTerpakai, asetTersedia, labelAset, lepasAset, payloadPj, pjKosong,
  selaraskanAset,
} from "./pjTambahan";

const ROWS = [
  { id: "a1", asset_code: "3.05.01", NUP: "1", asset_name: "Laptop" },
  { id: "a2", asset_code: "3.05.02", NUP: "2", asset_name: "Printer" },
  { id: "a3", asset_code: "3.06.01", NUP: "1", asset_name: "Kamera" },
];
const SEMUA = new Set(["a1", "a2", "a3"]);

describe("labelAset", () => {
  test("kode dan NUP dirapatkan, nama menyusul", () => {
    expect(labelAset(ROWS[0])).toBe("3.05.01·1 — Laptop");
  });

  test("data tak lengkap tak melahirkan pemisah menggantung", () => {
    expect(labelAset({ asset_name: "Meja" })).toBe("Meja");
    expect(labelAset({ asset_code: "3.05" })).toBe("3.05");
    expect(labelAset({})).toBe("-");
    expect(labelAset(null)).toBe("-");
  });

  test("NUP 0 tetap tercetak — bukan dianggap kosong", () => {
    expect(labelAset({ asset_code: "3.05", NUP: 0, asset_name: "X" }))
      .toBe("3.05·0 — X");
  });
});

describe("pjKosong", () => {
  test("membawa keempat kolomnya sejak awal", () => {
    // `asset_ids` yang undefined akan lolos ke payload sebagai undefined dan
    // ditolak server dengan pesan yang tak menyebut sebab sebenarnya.
    expect(pjKosong()).toEqual({
      nama: "", nip: "", unit_tempat_tugas: "", asset_ids: [] });
  });
});

describe("asetTersedia — satu barang satu orang", () => {
  const PJ = [
    { nama: "Budi", asset_ids: ["a1"] },
    { nama: "Sari", asset_ids: ["a2"] },
  ];

  test("barang milik orang lain tak ditawarkan", () => {
    expect(asetTersedia(ROWS, SEMUA, PJ, 0).map((a) => a.id)).toEqual(["a1", "a3"]);
    expect(asetTersedia(ROWS, SEMUA, PJ, 1).map((a) => a.id)).toEqual(["a2", "a3"]);
  });

  test("barang MILIK SENDIRI tetap ditawarkan pada barisnya", () => {
    // Kalau tidak, chip yang sudah terpasang lenyap dari daftar dan operator
    // yang melepasnya sesaat tak bisa memasangnya kembali.
    expect(asetTersedia(ROWS, SEMUA, PJ, 0).map((a) => a.id)).toContain("a1");
  });

  test("barang yang TIDAK dicentang untuk BAST ini tak ditawarkan", () => {
    const sebagian = new Set(["a1", "a2"]);
    expect(asetTersedia(ROWS, sebagian, PJ, 0).map((a) => a.id)).toEqual(["a1"]);
  });

  test("tanpa daftar centang → tak menawarkan apa pun, bukan meledak", () => {
    expect(asetTersedia(ROWS, undefined, PJ, 0)).toEqual([]);
    expect(asetTersedia(null, SEMUA, null, 0)).toEqual([]);
  });

  test("asetTerpakai mengabaikan baris yang diminta dikecualikan", () => {
    expect([...asetTerpakai(PJ, 0)]).toEqual(["a2"]);
    expect([...asetTerpakai(PJ)].sort()).toEqual(["a1", "a2"]);
  });
});

describe("lepasAset & selaraskanAset", () => {
  const PJ = [
    { nama: "Budi", asset_ids: ["a1", "a2"] },
    { nama: "Sari", asset_ids: ["a3"] },
  ];

  test("lepasAset mencabut dari SEMUA penanggung jawab", () => {
    const r = lepasAset(PJ, "a1");
    expect(r[0].asset_ids).toEqual(["a2"]);
    expect(r[1].asset_ids).toEqual(["a3"]);
  });

  test("baris yang tak terpengaruh dikembalikan APA ADANYA", () => {
    // Identitas objek dipertahankan supaya render tak ikut goyang untuk
    // baris yang tak berubah.
    const r = lepasAset(PJ, "a1");
    expect(r[1]).toBe(PJ[1]);
  });

  test("selaraskanAset membuang aset yang centangnya dicabut", () => {
    const r = selaraskanAset(PJ, new Set(["a1", "a3"]));
    expect(r[0].asset_ids).toEqual(["a1"]);
    expect(r[1].asset_ids).toEqual(["a3"]);
    expect(r[1]).toBe(PJ[1]);
  });

  test("mengosongkan seluruh centang mengosongkan seluruh lekatan", () => {
    const r = selaraskanAset(PJ, new Set());
    expect(r.map((p) => p.asset_ids)).toEqual([[], []]);
  });
});

describe("payloadPj", () => {
  test("baris tanpa nama tidak pernah dikirim", () => {
    expect(payloadPj([{ nama: "  ", nip: "9" }, { nama: "Budi" }]))
      .toHaveLength(1);
  });

  test("spasi tepi dipangkas dan kolom hilang diisi kosong", () => {
    expect(payloadPj([{ nama: " Budi " }])).toEqual([
      { nama: "Budi", nip: "", unit_tempat_tugas: "", asset_ids: [] }]);
  });

  test("aset kembar dirapikan", () => {
    expect(payloadPj([{ nama: "Budi", asset_ids: ["a1", "a1", "a2"] }])[0]
      .asset_ids).toEqual(["a1", "a2"]);
  });

  test("daftar kosong / tak ada → array kosong", () => {
    expect(payloadPj([])).toEqual([]);
    expect(payloadPj(null)).toEqual([]);
  });
});
