import {
  buatScanId, bacaTertunda, jumlahTertunda, simpanTertunda, hapusTertunda,
  bersihkanKedaluwarsa, kosongkanAntrean, _KONSTANTA,
} from "./antreanScan";

// Skenario lapangan yang menjadi alasan berkas ini ada: petugas memindai 30
// barang di gudang basement tanpa sinyal, lalu naik ke lantai atas dan antrean
// terkirim. Yang dijaga uji di bawah: tak ada pindaian yang hilang, tak ada
// yang terhitung dua kali, dan localStorage yang rusak/mati tak menghentikan
// pekerjaan.

beforeEach(() => { kosongkanAntrean(); });

describe("buatScanId", () => {
  test("tak pernah kembar meski dipanggil beruntun dalam milidetik yang sama", () => {
    const set = new Set(Array.from({ length: 500 }, () => buatScanId()));
    expect(set.size).toBe(500);
  });

  test("berawalan scan_ agar terbaca saat menelusuri antrean", () => {
    expect(buatScanId().startsWith("scan_")).toBe(true);
  });
});

describe("simpanTertunda", () => {
  test("scan tersimpan dan terbaca kembali", () => {
    simpanTertunda({ scan_id: "s1", kode: "3.05-12", node_id: "r305" });
    expect(bacaTertunda()).toHaveLength(1);
    expect(bacaTertunda()[0].kode).toBe("3.05-12");
  });

  test("menitipkan ULANG scan_id yang sama memperbarui, bukan menggandakan", () => {
    // Satu pindaian yang dicoba tiga kali tak boleh tampak seperti tiga barang.
    simpanTertunda({ scan_id: "s1", kode: "A", node_id: "r1" });
    simpanTertunda({ scan_id: "s1", kode: "A", node_id: "r1", percobaan: 2 });
    simpanTertunda({ scan_id: "s1", kode: "A", node_id: "r1", percobaan: 3 });
    expect(jumlahTertunda()).toBe(1);
    expect(bacaTertunda()[0].percobaan).toBe(3);
  });

  test("urutan simpan dipertahankan — antrean dikirim sesuai kejadian", () => {
    ["s1", "s2", "s3"].forEach((id) => simpanTertunda({ scan_id: id }));
    expect(bacaTertunda().map((x) => x.scan_id)).toEqual(["s1", "s2", "s3"]);
  });

  test("tanpa scan_id ditolak — baris tanpa kunci idempotensi tak bisa dikirim ulang aman", () => {
    expect(simpanTertunda({ kode: "A" })).toBe(false);
    expect(simpanTertunda(null)).toBe(false);
    expect(jumlahTertunda()).toBe(0);
  });

  test("melewati plafon membuang yang TERLAMA, bukan menolak yang baru", () => {
    const n = _KONSTANTA.MAKS_BARIS + 5;
    for (let i = 0; i < n; i += 1) simpanTertunda({ scan_id: `s${i}` });
    const daftar = bacaTertunda();
    expect(daftar).toHaveLength(_KONSTANTA.MAKS_BARIS);
    expect(daftar[daftar.length - 1].scan_id).toBe(`s${n - 1}`);
    expect(daftar.find((x) => x.scan_id === "s0")).toBeUndefined();
  });
});

describe("hapusTertunda", () => {
  test("mencoret satu baris yang sudah pasti tersimpan di server", () => {
    simpanTertunda({ scan_id: "s1" });
    simpanTertunda({ scan_id: "s2" });
    expect(hapusTertunda("s1")).toBe(true);
    expect(bacaTertunda().map((x) => x.scan_id)).toEqual(["s2"]);
  });

  test("id yang tak ada tidak mengubah apa pun", () => {
    simpanTertunda({ scan_id: "s1" });
    expect(hapusTertunda("entah")).toBe(false);
    expect(jumlahTertunda()).toBe(1);
  });
});

describe("bersihkanKedaluwarsa", () => {
  test("sisa opname bulan lalu tak ikut terkirim ke opname yang sedang berjalan", () => {
    const lama = Date.now() - _KONSTANTA.MAKS_UMUR_MS - 1000;
    simpanTertunda({ scan_id: "tua", dititip_pada: lama });
    simpanTertunda({ scan_id: "baru" });
    expect(bersihkanKedaluwarsa()).toBe(1);
    expect(bacaTertunda().map((x) => x.scan_id)).toEqual(["baru"]);
  });

  test("tak ada yang kedaluwarsa → antrean utuh", () => {
    simpanTertunda({ scan_id: "s1" });
    expect(bersihkanKedaluwarsa()).toBe(0);
    expect(jumlahTertunda()).toBe(1);
  });
});

describe("penyimpanan bermasalah", () => {
  test("isi localStorage yang rusak dibaca sebagai antrean kosong, bukan melempar", () => {
    window.localStorage.setItem(_KONSTANTA.KUNCI, "{bukan json");
    expect(bacaTertunda()).toEqual([]);
  });

  test("baris tanpa scan_id di penyimpanan lama disaring", () => {
    window.localStorage.setItem(_KONSTANTA.KUNCI,
      JSON.stringify([{ kode: "A" }, { scan_id: "s1" }]));
    expect(bacaTertunda().map((x) => x.scan_id)).toEqual(["s1"]);
  });

  test("localStorage yang menolak menulis (mode privasi) tak menghentikan opname", () => {
    // jsdom membungkus Storage lewat Proxy, jadi penggantian harus di
    // prototipenya — menimpa properti instance saja tak berpengaruh.
    const spy = jest.spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => { throw new Error("QuotaExceeded"); });
    try {
      expect(simpanTertunda({ scan_id: "s1" })).toBe(false);
      expect(() => bacaTertunda()).not.toThrow();
    } finally {
      spy.mockRestore();
    }
  });
});
