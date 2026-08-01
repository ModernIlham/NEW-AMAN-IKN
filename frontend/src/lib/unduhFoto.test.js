import {
  AMBANG_MACET_MS, ekstensiDariMime, bersihkanNamaBerkas, namaBerkasFoto,
  pemantauMacet, pesanGagalUnduh, persenUnduh,
} from "./unduhFoto";

describe("ekstensiDariMime", () => {
  it("mengenali tipe gambar yang dipakai aplikasi", () => {
    expect(ekstensiDariMime("image/jpeg")).toBe("jpg");
    expect(ekstensiDariMime("image/png")).toBe("png");
    expect(ekstensiDariMime("image/webp")).toBe("webp");
    expect(ekstensiDariMime("image/avif")).toBe("avif");
    expect(ekstensiDariMime("image/heic")).toBe("heic");
    expect(ekstensiDariMime("image/gif")).toBe("gif");
  });
  it("tak peduli huruf besar-kecil & parameter charset", () => {
    expect(ekstensiDariMime("IMAGE/WEBP")).toBe("webp");
    expect(ekstensiDariMime("image/png; charset=binary")).toBe("png");
  });
  it("jatuh ke jpg bila tipe kosong/tak dikenal", () => {
    expect(ekstensiDariMime("")).toBe("jpg");
    expect(ekstensiDariMime(null)).toBe("jpg");
    expect(ekstensiDariMime("application/octet-stream")).toBe("jpg");
  });
});

describe("bersihkanNamaBerkas", () => {
  it("MEMPERTAHANKAN titik kode barang BMN", () => {
    expect(bersihkanNamaBerkas("3.05.02.001")).toBe("3.05.02.001");
  });
  it("mengganti karakter yang ditolak sistem berkas", () => {
    expect(bersihkanNamaBerkas("A/B\\C:D*E?F\"G<H>I|J")).toBe("A-B-C-D-E-F-G-H-I-J");
  });
  it("membuang karakter kendali", () => {
    expect(bersihkanNamaBerkas("AB\u0000C\u001fD")).toBe("ABCD");
  });
  it("merapikan spasi & memangkas titik/spasi di ujung", () => {
    expect(bersihkanNamaBerkas("  Meja   Kerja . ")).toBe("Meja Kerja");
  });
  it("aman untuk nilai kosong/null", () => {
    expect(bersihkanNamaBerkas(null)).toBe("");
    expect(bersihkanNamaBerkas(undefined)).toBe("");
    expect(bersihkanNamaBerkas("")).toBe("");
  });
  it("membatasi panjang", () => {
    expect(bersihkanNamaBerkas("x".repeat(200))).toHaveLength(80);
  });
});

describe("namaBerkasFoto", () => {
  it("memakai kode barang lebih dulu, nomor foto 1-basis", () => {
    expect(namaBerkasFoto({ asset_code: "3.05.02.001" }, 0, "image/jpeg"))
      .toBe("3.05.02.001_foto-1.jpg");
    expect(namaBerkasFoto({ asset_code: "3.05.02.001" }, 2, "image/webp"))
      .toBe("3.05.02.001_foto-3.webp");
  });
  it("jatuh ke NUP lalu id bila kode kosong", () => {
    expect(namaBerkasFoto({ nup: "12" }, 0, "image/png")).toBe("12_foto-1.png");
    // Ejaan NUP huruf besar juga beredar di respons daftar.
    expect(namaBerkasFoto({ NUP: "34" }, 0, "image/png")).toBe("34_foto-1.png");
    expect(namaBerkasFoto({ id: "abc123" }, 0, "image/png")).toBe("abc123_foto-1.png");
  });
  it("tetap menghasilkan nama saat aset kosong sama sekali", () => {
    expect(namaBerkasFoto(null, 0, "")).toBe("foto_foto-1.jpg");
    expect(namaBerkasFoto({}, undefined, "")).toBe("foto_foto-1.jpg");
  });
  it("garis miring pada kode tidak bocor jadi jalur folder", () => {
    expect(namaBerkasFoto({ asset_code: "A/B" }, 0, "image/jpeg")).toBe("A-B_foto-1.jpg");
  });
});

describe("pemantauMacet", () => {
  // Jam palsu: kita kendalikan sendiri kapan pemicu "jatuh tempo".
  function jamPalsu() {
    let idBerikut = 1;
    const antrean = new Map();
    return {
      jadwal: (fn, ms) => { const id = idBerikut++; antrean.set(id, { fn, ms }); return id; },
      batal: (id) => { antrean.delete(id); },
      /** Jalankan semua pemicu yang tersisa (seolah waktunya lewat). */
      majukanWaktu: () => { Array.from(antrean.values()).forEach((t) => t.fn()); },
      jumlahAktif: () => antrean.size,
    };
  }

  it("memicu padaMacet bila tak ada kemajuan sampai ambang", () => {
    const jam = jamPalsu();
    const macet = jest.fn();
    pemantauMacet(macet, { ambangMs: 1000, jadwal: jam.jadwal, batal: jam.batal });
    expect(macet).not.toHaveBeenCalled();
    jam.majukanWaktu();
    expect(macet).toHaveBeenCalledTimes(1);
  });

  it("TIDAK memicu selama byte terus berdatangan — unduhan lambat tak dihukum", () => {
    const jam = jamPalsu();
    const macet = jest.fn();
    const p = pemantauMacet(macet, { ambangMs: 1000, jadwal: jam.jadwal, batal: jam.batal });
    // Tiap kemajuan membatalkan pemicu lama & memasang yang baru.
    for (let i = 0; i < 5; i++) p.maju();
    expect(jam.jumlahAktif()).toBe(1); // tak menumpuk
    expect(macet).not.toHaveBeenCalled();
  });

  it("berhenti memantau setelah hentikan()", () => {
    const jam = jamPalsu();
    const macet = jest.fn();
    const p = pemantauMacet(macet, { ambangMs: 1000, jadwal: jam.jadwal, batal: jam.batal });
    p.hentikan();
    jam.majukanWaktu();
    expect(macet).not.toHaveBeenCalled();
    expect(jam.jumlahAktif()).toBe(0);
  });

  it("hanya memicu SEKALI walau waktu dimajukan berkali-kali", () => {
    const jam = jamPalsu();
    const macet = jest.fn();
    pemantauMacet(macet, { ambangMs: 1000, jadwal: jam.jadwal, batal: jam.batal });
    jam.majukanWaktu();
    jam.majukanWaktu();
    expect(macet).toHaveBeenCalledTimes(1);
  });

  it("maju() setelah macet tak menghidupkan pemantau kembali", () => {
    const jam = jamPalsu();
    const macet = jest.fn();
    const p = pemantauMacet(macet, { ambangMs: 1000, jadwal: jam.jadwal, batal: jam.batal });
    jam.majukanWaktu();
    p.maju();
    jam.majukanWaktu();
    expect(macet).toHaveBeenCalledTimes(1);
  });

  it("memakai ambang baku bila tak disetel", () => {
    expect(AMBANG_MACET_MS).toBeGreaterThan(0);
  });
});

describe("pesanGagalUnduh", () => {
  it("membedakan macet dari kegagalan lain & menyebut jalan keluarnya", () => {
    const p = pesanGagalUnduh(null, true);
    expect(p).toMatch(/terhenti/i);
    expect(p).toMatch(/Layar Penuh/i);
  });
  it("menyebut sebab per status HTTP", () => {
    expect(pesanGagalUnduh({ response: { status: 401 } })).toMatch(/sesi/i);
    expect(pesanGagalUnduh({ response: { status: 403 } })).toMatch(/berhak/i);
    expect(pesanGagalUnduh({ response: { status: 404 } })).toMatch(/tidak ditemukan/i);
    expect(pesanGagalUnduh({ response: { status: 429 } })).toMatch(/tunggu/i);
    expect(pesanGagalUnduh({ response: { status: 503 } })).toMatch(/server/i);
  });
  it("tanpa respons = tak sampai server", () => {
    expect(pesanGagalUnduh(new Error("Network Error"))).toMatch(/sinyal/i);
  });
});

describe("persenUnduh", () => {
  it("menghitung persen bulat", () => {
    expect(persenUnduh(0, 200)).toBe(0);
    expect(persenUnduh(50, 200)).toBe(25);
    expect(persenUnduh(200, 200)).toBe(100);
  });
  it("null bila panjang isi tak diketahui (server tanpa Content-Length)", () => {
    expect(persenUnduh(10, 0)).toBeNull();
    expect(persenUnduh(10, undefined)).toBeNull();
    expect(persenUnduh(10, NaN)).toBeNull();
  });
  it("menjepit nilai di luar rentang", () => {
    expect(persenUnduh(300, 200)).toBe(100);
    expect(persenUnduh(-5, 200)).toBeNull();
  });
});
