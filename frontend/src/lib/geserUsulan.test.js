import {
  bahanGarisUsulan, jarakMeter, koordinatSah, MODE_GESER, ringkasGeser,
  teksJarak, GAYA_GARIS_USULAN, KETERANGAN_MODE,
} from "./geserUsulan";

describe("koordinatSah", () => {
  test("menolak yang di luar bumi dan yang bukan angka", () => {
    expect(koordinatSah(-0.9, 116.7)).toBe(true);
    expect(koordinatSah(91, 0)).toBe(false);
    expect(koordinatSah(0, 181)).toBe(false);
    expect(koordinatSah(null, 116.7)).toBe(false);
    expect(koordinatSah("bukan angka", 0)).toBe(false);
    expect(koordinatSah(undefined, undefined)).toBe(false);
  });

  test("nol adalah koordinat SAH — jangan tertukar dengan 'kosong'", () => {
    // Menyaring 0 sebagai falsy akan membuang titik di garis khatulistiwa /
    // meridian utama. Jarang di IKN, tapi salahnya senyap dan permanen.
    expect(koordinatSah(0, 0)).toBe(true);
  });
});

describe("bahanGarisUsulan", () => {
  const u = { lat: -0.95, lng: 116.75, lat_asal: -0.9, lng_asal: 116.7 };

  test("memberi dua ujung garis + posisi marker bayangan", () => {
    const r = bahanGarisUsulan(u);
    expect(r.garis).toEqual([[-0.9, 116.7], [-0.95, 116.75]]);
    expect(r.bayangan).toEqual([-0.95, 116.75]);
  });

  test("tanpa posisi asal: bayangan tetap digambar, garisnya tidak", () => {
    // Aset lama yang koordinatnya kosong. Menarik garis ke [0,0] akan
    // membentangkan garis melintasi separuh dunia ke tengah Samudra Atlantik.
    const r = bahanGarisUsulan({ lat: -0.95, lng: 116.75 });
    expect(r.garis).toBeNull();
    expect(r.bayangan).toEqual([-0.95, 116.75]);
  });

  test("posisi usulan tak sah → tak menggambar apa pun", () => {
    expect(bahanGarisUsulan({ lat: 999, lng: 0, lat_asal: -0.9, lng_asal: 116.7 }))
      .toBeNull();
    expect(bahanGarisUsulan(null)).toBeNull();
  });
});

describe("jarakMeter & teksJarak", () => {
  test("jarak nyata terhitung masuk akal", () => {
    // ~0,01° lintang ≈ 1,11 km.
    const m = jarakMeter(-0.90, 116.70, -0.91, 116.70);
    expect(m).toBeGreaterThan(1050);
    expect(m).toBeLessThan(1150);
  });

  test("titik yang sama = 0 meter", () => {
    expect(jarakMeter(-0.9, 116.7, -0.9, 116.7)).toBe(0);
  });

  test("koordinat tak sah → null, bukan NaN", () => {
    expect(jarakMeter(null, 116.7, -0.9, 116.7)).toBeNull();
  });

  test("teks jarak: meter di bawah 1 km, km di atasnya (koma Indonesia)", () => {
    expect(teksJarak(12)).toBe("12 m");
    expect(teksJarak(999)).toBe("999 m");
    expect(teksJarak(1400)).toBe("1,4 km");
    expect(teksJarak(null)).toBe("");
    expect(teksJarak(0)).toBe("0 m");
  });
});

describe("ringkasGeser", () => {
  test("menyebut nama, pengusul, dan identitas barang", () => {
    expect(ringkasGeser({ nama_titik: "Genset", oleh: "Budi", kode: "3100102001", nup: "7" }))
      .toEqual({ nama: "Genset", oleh: "Budi", identitas: "3100102001 · NUP 7" });
  });

  test("data kosong tak menghasilkan 'undefined' di layar", () => {
    expect(ringkasGeser({})).toEqual({ nama: "Aset", oleh: "Tamu", identitas: "" });
    expect(ringkasGeser(null).oleh).toBe("Tamu");
  });
});

describe("kontrak mode & gaya", () => {
  test("dua mode, keterangannya menyatakan bahwa ASLI hanya USULAN", () => {
    expect(Object.values(MODE_GESER)).toEqual(["asli", "usulan"]);
    // Ini bukan uji kosmetik: kalau kalimatnya tak menyebut persetujuan,
    // pemakainya mengira menggeser marker asli langsung mengubah data.
    expect(KETERANGAN_MODE[MODE_GESER.ASLI]).toMatch(/menyetujui/i);
    expect(KETERANGAN_MODE[MODE_GESER.ASLI]).toMatch(/usulkan|mengusulkan/i);
  });

  test("garis penghubung memang PUTUS-PUTUS", () => {
    expect(GAYA_GARIS_USULAN.dashArray).toBeTruthy();
  });
});
