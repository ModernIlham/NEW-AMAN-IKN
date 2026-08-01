import {
  JARI_BUMI_M, jarakMeter, panjangJalurMeter, luasMeterPersegi,
  formatJarak, formatLuas, ringkasUkur,
} from "./ukurPeta";

// Toleransi relatif: model bola vs elipsoid WGS84 berbeda ~0,3%; yang diuji di
// sini adalah kebenaran rumusnya, bukan kesamaan dengan geodesi elipsoidal.
const dekat = (a, b, toleransiRel = 0.005) =>
  Math.abs(a - b) <= Math.abs(b) * toleransiRel;

describe("jarakMeter", () => {
  it("nol untuk titik yang sama", () => {
    expect(jarakMeter({ lat: -1.4, lng: 116.7 }, { lat: -1.4, lng: 116.7 })).toBe(0);
  });

  it("1 derajat lintang ≈ 111,2 km di mana pun", () => {
    const d = jarakMeter({ lat: 0, lng: 116 }, { lat: 1, lng: 116 });
    expect(dekat(d, (Math.PI / 180) * JARI_BUMI_M)).toBe(true);
    // Sifat khas lintang: tak bergantung bujur maupun posisi utara-selatan.
    const d2 = jarakMeter({ lat: -50, lng: 20 }, { lat: -49, lng: 20 });
    expect(dekat(d, d2)).toBe(true);
  });

  it("1 derajat bujur MENYUSUT menjauhi khatulistiwa", () => {
    const diKhatulistiwa = jarakMeter({ lat: 0, lng: 116 }, { lat: 0, lng: 117 });
    const diLintang60 = jarakMeter({ lat: 60, lng: 116 }, { lat: 60, lng: 117 });
    // cos(60°) = 0,5 → separuhnya.
    expect(dekat(diLintang60, diKhatulistiwa * 0.5)).toBe(true);
  });

  it("simetris (A→B = B→A)", () => {
    const a = { lat: -1.4, lng: 116.7 }, b = { lat: -1.41, lng: 116.71 };
    expect(jarakMeter(a, b)).toBeCloseTo(jarakMeter(b, a), 9);
  });

  it("tetap teliti pada jarak sangat pendek (sisi ruangan ~10 m)", () => {
    // 0,0001° lintang ≈ 11,1 m.
    const d = jarakMeter({ lat: -1.4, lng: 116.7 }, { lat: -1.4001, lng: 116.7 });
    expect(dekat(d, 11.12, 0.01)).toBe(true);
  });

  it("nol untuk masukan cacat, bukan NaN", () => {
    expect(jarakMeter(null, { lat: 1, lng: 1 })).toBe(0);
    expect(jarakMeter({ lat: "x", lng: 1 }, { lat: 1, lng: 1 })).toBe(0);
    expect(jarakMeter({ lat: 1, lng: 1 }, undefined)).toBe(0);
  });
});

describe("panjangJalurMeter", () => {
  it("nol untuk jalur kurang dari dua titik", () => {
    expect(panjangJalurMeter([])).toBe(0);
    expect(panjangJalurMeter([{ lat: 0, lng: 0 }])).toBe(0);
    expect(panjangJalurMeter(null)).toBe(0);
  });

  it("menjumlahkan ruas berurutan", () => {
    const t = [{ lat: 0, lng: 0 }, { lat: 1, lng: 0 }, { lat: 2, lng: 0 }];
    expect(dekat(panjangJalurMeter(t), 2 * (Math.PI / 180) * JARI_BUMI_M)).toBe(true);
  });
});

describe("luasMeterPersegi", () => {
  it("nol untuk kurang dari tiga titik — garis bukan bidang", () => {
    expect(luasMeterPersegi([{ lat: 0, lng: 0 }, { lat: 1, lng: 0 }])).toBe(0);
  });

  it("persegi 0,01° di khatulistiwa ≈ 1,113 km × 1,113 km", () => {
    const s = 0.01;
    const luas = luasMeterPersegi([
      { lat: 0, lng: 0 }, { lat: 0, lng: s }, { lat: s, lng: s }, { lat: s, lng: 0 },
    ]);
    const sisi = (Math.PI / 180) * JARI_BUMI_M * s;   // ≈ 1112 m
    expect(dekat(luas, sisi * sisi, 0.01)).toBe(true);
  });

  it("arah putaran TIDAK mengubah hasil — pengguna menggambar ke arah mana pun", () => {
    const searah = [{ lat: 0, lng: 0 }, { lat: 0, lng: 0.01 }, { lat: 0.01, lng: 0.01 }];
    const berlawanan = [...searah].reverse();
    expect(luasMeterPersegi(searah)).toBeCloseTo(luasMeterPersegi(berlawanan), 6);
  });

  it("poligon tak perlu ditutup manual", () => {
    const terbuka = [{ lat: 0, lng: 0 }, { lat: 0, lng: 0.01 }, { lat: 0.01, lng: 0.01 }];
    const ditutup = [...terbuka, { lat: 0, lng: 0 }];
    // Menutup manual menambah ruas berpanjang nol → luas sama.
    expect(dekat(luasMeterPersegi(ditutup), luasMeterPersegi(terbuka), 1e-6)).toBe(true);
  });

  it("nol untuk koordinat cacat, bukan NaN", () => {
    const l = luasMeterPersegi([{ lat: 0, lng: 0 }, { lat: "x", lng: 1 }, { lat: 1, lng: 1 }]);
    expect(l).toBe(0);
  });
});

describe("formatJarak", () => {
  it("meter di bawah 1 km", () => {
    expect(formatJarak(5.234)).toBe("5,23 m");
    // Nol di belakang DIPERTAHANKAN — presisi harus terlihat konsisten.
    expect(formatJarak(5.2)).toBe("5,20 m");
    expect(formatJarak(123.45)).toBe("123,5 m");
  });
  it("kilometer di atas 1 km", () => {
    expect(formatJarak(1500)).toBe("1,50 km");
    expect(formatJarak(12345)).toBe("12,35 km");
  });
  it("aman untuk nilai tak wajar", () => {
    expect(formatJarak(NaN)).toBe("0 m");
    expect(formatJarak(-5)).toBe("0 m");
    expect(formatJarak(undefined)).toBe("0 m");
  });
});

describe("formatLuas", () => {
  it("meter persegi di bawah 1 hektar", () => {
    expect(formatLuas(45.6)).toBe("45,60 m²");
    expect(formatLuas(1234.5)).toBe("1.234,5 m²");
  });
  it("HEKTAR mulai 1 ha — satuan dokumen pertanahan", () => {
    expect(formatLuas(15000)).toBe("1,50 ha");
  });
  it("km² ikut ditampilkan saat sudah sangat luas", () => {
    const t = formatLuas(2500000);
    expect(t).toContain("250,00 ha");
    expect(t).toContain("2,50 km²");
  });
  it("aman untuk nilai tak wajar", () => {
    expect(formatLuas(NaN)).toBe("0 m²");
    expect(formatLuas(-1)).toBe("0 m²");
  });
});

describe("ringkasUkur", () => {
  it("dua titik = garis: panjang ada, luas TIDAK dilaporkan", () => {
    const r = ringkasUkur([{ lat: 0, lng: 0 }, { lat: 0, lng: 0.01 }]);
    expect(r.jumlahTitik).toBe(2);
    expect(r.panjangMeter).toBeGreaterThan(0);
    // Melaporkan "luas 0 m²" untuk sebuah garis membingungkan, bukan informatif.
    expect(r.luasMeterPersegi).toBeNull();
    expect(r.teksLuas).toBeNull();
    expect(r.kelilingMeter).toBeNull();
  });

  it("tiga titik = bidang: luas & keliling ikut dihitung", () => {
    const t = [{ lat: 0, lng: 0 }, { lat: 0, lng: 0.01 }, { lat: 0.01, lng: 0.01 }];
    const r = ringkasUkur(t);
    expect(r.luasMeterPersegi).toBeGreaterThan(0);
    expect(r.teksLuas).toMatch(/m²|ha/);
    expect(r.kelilingMeter).toBeGreaterThan(r.panjangMeter);
  });

  it("aman untuk daftar kosong", () => {
    const r = ringkasUkur([]);
    expect(r.jumlahTitik).toBe(0);
    expect(r.panjangMeter).toBe(0);
    expect(r.luasMeterPersegi).toBeNull();
    expect(r.teksPanjang).toBe("0 m");
  });
});
