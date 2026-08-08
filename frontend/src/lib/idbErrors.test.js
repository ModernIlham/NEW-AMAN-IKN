/* eslint-env jest */
import fs from "fs";
import path from "path";
import { isQuotaExceeded, keputusanGagalTulisAntrean } from "./idbErrors";

// Klasifikasi error kuota IndexedDB (perangkat penuh) — lintas-peramban.
// Dipakai agar sync snapshot offline degradasi anggun (cache sebagian), bukan crash.
describe("isQuotaExceeded", () => {
  test("DOMException QuotaExceededError (Blink/WebKit) → true", () => {
    expect(isQuotaExceeded({ name: "QuotaExceededError" })).toBe(true);
  });

  test("nama Firefox NS_ERROR_DOM_QUOTA_REACHED → true", () => {
    expect(isQuotaExceeded({ name: "NS_ERROR_DOM_QUOTA_REACHED" })).toBe(true);
  });

  test("kode lawas 22 (WebKit/Blink) & 1014 (Firefox) → true", () => {
    expect(isQuotaExceeded({ code: 22 })).toBe(true);
    expect(isQuotaExceeded({ code: 1014 })).toBe(true);
  });

  test("error terbungkus event (err.target.error) → true", () => {
    expect(isQuotaExceeded({ target: { error: { name: "QuotaExceededError" } } })).toBe(true);
  });

  test("error non-kuota → false", () => {
    expect(isQuotaExceeded({ name: "AbortError" })).toBe(false);
    expect(isQuotaExceeded({ name: "NotFoundError", code: 8 })).toBe(false);
    expect(isQuotaExceeded(new Error("boom"))).toBe(false);
  });

  test("null/undefined → false (aman)", () => {
    expect(isQuotaExceeded(null)).toBe(false);
    expect(isQuotaExceeded(undefined)).toBe(false);
  });
});

// Temuan C21 tinjauan sistem 2026-08: kuota ditangani anggun di cache BACA,
// tetapi DITELAN DIAM di antrean TULIS. `persistQueueItem` punya cabang catch
// yang di produksi benar-benar kosong — simpanan luring gagal ditulis tanpa
// satu pesan, chip barisnya tetap "queued", lalu seluruh muatannya (termasuk
// foto 900 KB × 6) lenyap begitu tab ditutup. Prioritasnya terbalik: yang
// selalu bisa ditarik ulang diberi peringatan, yang tak bisa dipulihkan diam.
describe("keputusanGagalTulisAntrean", () => {
  test("kuota penuh → beri tahu pengguna", () => {
    expect(keputusanGagalTulisAntrean({ name: "QuotaExceededError" })).toBe("beri_tahu_pengguna");
    expect(keputusanGagalTulisAntrean({ name: "NS_ERROR_DOM_QUOTA_REACHED" })).toBe("beri_tahu_pengguna");
    expect(keputusanGagalTulisAntrean({ code: 22 })).toBe("beri_tahu_pengguna");
    expect(keputusanGagalTulisAntrean({ target: { error: { name: "QuotaExceededError" } } }))
      .toBe("beri_tahu_pengguna");
  });

  test("galat lain → dicatat diam (tak ada obat yang bisa dikerjakan di lapangan)", () => {
    expect(keputusanGagalTulisAntrean({ name: "NotFoundError" })).toBe("catat_diam");
    expect(keputusanGagalTulisAntrean({ name: "VersionError" })).toBe("catat_diam");
    expect(keputusanGagalTulisAntrean(new Error("boom"))).toBe("catat_diam");
  });

  test("null/undefined → catat_diam, bukan toast palsu", () => {
    expect(keputusanGagalTulisAntrean(null)).toBe("catat_diam");
    expect(keputusanGagalTulisAntrean(undefined)).toBe("catat_diam");
  });
});

// Fungsi murni di atas tak ada gunanya bila tak seorang pun memanggilnya.
// Penjaga ini mengurung SAMBUNGANNYA: catch di persistQueueItem benar-benar
// memakai keputusan itu, dan DashboardPage menampilkannya sebagai peringatan
// yang MENETAP. `duration: 0` bukan detail gaya — toast berdurasi normal di
// layar HP dalam saku sama saja dengan tidak ada peringatan.
describe("keputusannya benar-benar tersambung ke kode produksi", () => {
  const baca = (rel) => fs.readFileSync(path.join(__dirname, "..", rel), "utf8");

  test("persistQueueItem memanggil keputusanGagalTulisAntrean, bukan catch kosong", () => {
    const src = baca("hooks/useOptimisticQueue.js");
    const badan = src.slice(src.indexOf("async function persistQueueItem"));
    const catchPertama = badan.slice(badan.indexOf("catch"), badan.indexOf("catch") + 700);
    expect(catchPertama).toMatch(/keputusanGagalTulisAntrean/);
    expect(catchPertama).toMatch(/onKuotaPenuh/);
    expect(src).toMatch(/import \{ keputusanGagalTulisAntrean \} from "\.\.\/lib\/idbErrors"/);
  });

  test("SEMUA pemanggilan persistQueueItem membawa pelapornya", () => {
    // Satu titik panggil yang terlewat = satu jalur simpan yang tetap bisu.
    const src = baca("hooks/useOptimisticQueue.js");
    const panggilan = src.match(/persistQueueItem\([^)]*\)/g)
      .filter((p) => !p.startsWith("persistQueueItem(item, statusKey, onKuotaPenuh"));
    expect(panggilan.length).toBeGreaterThanOrEqual(4);
    for (const p of panggilan) expect(p).toMatch(/laporKuotaPenuh/);
  });

  test("DashboardPage menampilkan peringatan MENETAP (duration: 0)", () => {
    const src = baca("pages/DashboardPage.jsx");
    const i = src.indexOf("onKuotaPenuh:");
    expect(i).toBeGreaterThan(-1);
    const blok = src.slice(i, i + 800);
    expect(blok).toMatch(/toast\.error/);
    expect(blok).toMatch(/duration:\s*0/);
    expect(blok).toMatch(/PENUH/);
  });
});
