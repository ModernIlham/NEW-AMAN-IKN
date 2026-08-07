/**
 * Uji kadensi pendamping pelacakan + jam hidup.
 *
 * Yang diuji bukan "fungsi mengembalikan angka", melainkan sifat-sifat yang
 * membuat fitur ini bisa dipercaya: mode bawaan tidak boleh diam-diam menjadi
 * boros, mode tercepat tidak boleh menabrak rate-limit servernya sendiri, dan
 * gerbang jam kerja harus dihitung memakai zona SERVER — bukan zona peramban
 * operator yang kebetulan sedang membuka layar.
 */
import {
  KADENSI, KADENSI_BAWAAN, KUNCI_KADENSI, AMBANG_HIDUP_DETIK,
  profilKadensi, bacaKadensi, simpanKadensi, usiaSingkat, masihHidup,
  diLuarJamAktif,
} from "./kadensiLacak";

function simpananPalsu(awal) {
  const isi = { ...(awal || {}) };
  return {
    getItem: (k) => (k in isi ? isi[k] : null),
    setItem: (k, v) => { isi[k] = String(v); },
    _isi: isi,
  };
}

// ── Bawaan tidak boleh berubah diam-diam ────────────────────────────────────

describe("mode bawaan", () => {
  test("bawaan adalah mode paling hemat, bukan yang tercepat", () => {
    expect(KADENSI_BAWAAN).toBe("hemat");
    const bawaan = KADENSI[KADENSI_BAWAAN];
    for (const p of Object.values(KADENSI)) {
      expect(bawaan.jeda_bergerak).toBeGreaterThanOrEqual(p.jeda_bergerak);
      expect(bawaan.jeda_kirim).toBeGreaterThanOrEqual(p.jeda_kirim);
    }
    expect(bawaan.boros).toBe(false);
  });

  test("angka mode hemat sama persis dengan perilaku sebelum menu ini ada", () => {
    // Menambahkan menu tidak boleh mengubah apa yang dialami perangkat yang
    // pemegangnya tak menyentuh apa pun. Angka rujukan: LacakPage sebelum
    // PR ini (docs/ARSITEKTUR-SPASIAL-IOT §8.4 #20).
    expect(KADENSI.hemat).toMatchObject({
      jeda_bergerak: 60_000, jeda_diam: 900_000,
      ambang_diam: 25, jeda_kirim: 120_000,
    });
  });

  test("nilai rusak jatuh ke bawaan, bukan ke mode terboros", () => {
    for (const buruk of ["", null, undefined, "AKTIF", "turbo", "0", 7]) {
      expect(profilKadensi(buruk).kunci).toBe(KADENSI_BAWAAN);
    }
    expect(profilKadensi("aktif").kunci).toBe("aktif");
  });
});

// ── Mode tercepat tak boleh menabrak plafon servernya sendiri ───────────────

describe("kadensi vs plafon server", () => {
  test("mode tercepat tetap di bawah 60 permintaan/menit", () => {
    // `POST /iot/observasi` memakai @limiter.limit("60/minute"). Perangkat
    // yang men-DDOS servernya sendiri lalu ditolak 429 akan kehilangan posisi
    // justru pada mode yang dipilih supaya tak kehilangan posisi.
    for (const p of Object.values(KADENSI)) {
      const perMenit = 60_000 / p.jeda_kirim;
      expect(perMenit).toBeLessThanOrEqual(60);
    }
    expect(60_000 / KADENSI.aktif.jeda_kirim).toBe(4);
  });

  test("makin aktif berarti makin sering DAN makin peka gerak", () => {
    const urut = [KADENSI.hemat, KADENSI.sedang, KADENSI.aktif];
    for (let i = 1; i < urut.length; i += 1) {
      expect(urut[i].jeda_bergerak).toBeLessThan(urut[i - 1].jeda_bergerak);
      expect(urut[i].jeda_diam).toBeLessThan(urut[i - 1].jeda_diam);
      expect(urut[i].jeda_kirim).toBeLessThan(urut[i - 1].jeda_kirim);
      // Ambang "masih diam" ikut mengecil. Tanpa ini, mode aktif merekam tiap
      // 10 detik tetapi orang yang berjalan pelan tetap dinilai DIAM dan
      // jatuh ke jeda lambat — menu yang tampak bekerja tapi tidak.
      expect(urut[i].ambang_diam).toBeLessThan(urut[i - 1].ambang_diam);
    }
  });

  test("hanya mode aktif yang ditandai boros", () => {
    expect(KADENSI.aktif.boros).toBe(true);
    expect(KADENSI.hemat.boros).toBe(false);
    expect(KADENSI.sedang.boros).toBe(false);
  });
});

// ── Penyimpanan pilihan ─────────────────────────────────────────────────────

describe("penyimpanan pilihan", () => {
  test("pilihan tersimpan dan terbaca kembali", () => {
    const s = simpananPalsu();
    simpanKadensi(s, "aktif");
    expect(s._isi[KUNCI_KADENSI]).toBe("aktif");
    expect(bacaKadensi(s)).toBe("aktif");
  });

  test("isi simpanan yang diedit tangan tak bisa menyelundupkan mode asing", () => {
    expect(bacaKadensi(simpananPalsu({ [KUNCI_KADENSI]: "turbo" })))
      .toBe(KADENSI_BAWAAN);
    simpanKadensi(simpananPalsu(), "turbo");     // tak boleh melempar
  });

  test("penyimpanan yang menolak (mode privat) tak menjatuhkan halaman", () => {
    const galak = {
      getItem: () => { throw new Error("SecurityError"); },
      setItem: () => { throw new Error("QuotaExceeded"); },
    };
    expect(bacaKadensi(galak)).toBe(KADENSI_BAWAAN);
    expect(() => simpanKadensi(galak, "aktif")).not.toThrow();
    expect(bacaKadensi(undefined)).toBe(KADENSI_BAWAAN);
  });
});

// ── Jam hidup ───────────────────────────────────────────────────────────────

describe("usiaSingkat", () => {
  test("detik ditampilkan sebagai detik — bukan dibulatkan jadi 0 menit", () => {
    expect(usiaSingkat(0)).toBe("0 dtk");
    expect(usiaSingkat(12)).toBe("12 dtk");
    expect(usiaSingkat(59)).toBe("59 dtk");
  });

  test("naik satuan tepat di batasnya", () => {
    expect(usiaSingkat(60)).toBe("1 mnt");
    expect(usiaSingkat(3599)).toBe("59 mnt");
    expect(usiaSingkat(3600)).toBe("1 jam");
    expect(usiaSingkat(86_399)).toBe("23 jam");
    expect(usiaSingkat(86_400)).toBe("1 hari");
  });

  test("belum pernah terdengar bukan 0 detik", () => {
    // "0 dtk lalu" untuk perangkat yang tak pernah mengirim adalah kebohongan
    // paling meyakinkan yang bisa dicetak layar ini.
    expect(usiaSingkat(null)).toBe("—");
    expect(usiaSingkat(undefined)).toBe("—");
    expect(usiaSingkat(-5)).toBe("—");
    expect(usiaSingkat(NaN)).toBe("—");
  });
});

describe("masihHidup", () => {
  test("ambang hidup melampaui dua kali jeda kirim mode teraktif", () => {
    expect(AMBANG_HIDUP_DETIK).toBeGreaterThan(
      (KADENSI.aktif.jeda_kirim / 1000) * 2);
  });

  test("hanya usia yang diketahui dan segar yang dinyatakan hidup", () => {
    expect(masihHidup(0)).toBe(true);
    expect(masihHidup(AMBANG_HIDUP_DETIK)).toBe(true);
    expect(masihHidup(AMBANG_HIDUP_DETIK + 1)).toBe(false);
    expect(masihHidup(null)).toBe(false);
    expect(masihHidup(undefined)).toBe(false);
    expect(masihHidup(-1)).toBe(false);
  });
});

// ── Gerbang jam kerja ───────────────────────────────────────────────────────

describe("diLuarJamAktif", () => {
  const personal = {
    jam_mulai: 7, jam_selesai: 18, hari_kerja_saja: true, zona_offset_jam: 8,
  };

  test("dihitung memakai zona SERVER, bukan zona peramban", () => {
    // 23:30 UTC Minggu = 07:30 WITA SENIN. Bila perhitungannya memakai zona
    // apa pun selain +8 yang dikirim server, jawabannya berbalik — jadi satu
    // kasus ini mengunci offset sekaligus pergeseran harinya.
    const t = new Date("2026-07-26T23:30:00Z");
    expect(diLuarJamAktif(personal, t)).toBe(false);
    expect(diLuarJamAktif({ ...personal, zona_offset_jam: 0 }, t)).toBe(true);
  });

  test("akhir pekan di luar jam aktif meski jamnya pas", () => {
    // 04:00 UTC Sabtu = 12:00 WITA Sabtu — jam kerja, hari libur.
    expect(diLuarJamAktif(personal, new Date("2026-08-01T04:00:00Z"))).toBe(true);
    // Hari yang sama tanpa aturan hari kerja → di dalam.
    expect(diLuarJamAktif({ ...personal, hari_kerja_saja: false },
                          new Date("2026-08-01T04:00:00Z"))).toBe(false);
  });

  test("batas jam tertutup di ujung atas", () => {
    // 18:00 WITA = 10:00 UTC. Server memakai `mulai <= jam < selesai`, jadi
    // pukul 18 tepat sudah DI LUAR — layar harus mengatakan hal yang sama.
    expect(diLuarJamAktif(personal, new Date("2026-07-27T10:00:00Z"))).toBe(true);
    expect(diLuarJamAktif(personal, new Date("2026-07-27T09:59:00Z"))).toBe(false);
    // 07:00 WITA = 23:00 UTC hari sebelumnya — batas bawah termasuk.
    expect(diLuarJamAktif(personal, new Date("2026-07-26T23:00:00Z"))).toBe(false);
  });

  test("profil tanpa gerbang jam menjawab TIDAK TAHU, bukan 'sedang aktif'", () => {
    const kendaraan = { jam_mulai: null, jam_selesai: null, zona_offset_jam: 8 };
    expect(diLuarJamAktif(kendaraan, new Date())).toBeNull();
    expect(diLuarJamAktif(undefined, new Date())).toBeNull();
    expect(diLuarJamAktif(personal, new Date("bukan tanggal"))).toBeNull();
  });
});
