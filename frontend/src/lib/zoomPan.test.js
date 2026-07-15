import {
  SKALA_MIN, SKALA_MAKS, jepitSkala, skalaGulir, skalaCubit,
  jarak, titikTengah, zoomKeTitik, jepitGeser,
} from "./zoomPan";

test("jepitSkala membatasi ke [min,max] & aman untuk nilai tak hingga", () => {
  expect(jepitSkala(0.2)).toBe(SKALA_MIN);
  expect(jepitSkala(99)).toBe(SKALA_MAKS);
  expect(jepitSkala(2.5)).toBe(2.5);
  expect(jepitSkala(NaN)).toBe(SKALA_MIN);
  expect(jepitSkala(Infinity)).toBe(SKALA_MIN);
});

test("skalaGulir: gulir atas (deltaY<0) memperbesar, gulir bawah memperkecil", () => {
  expect(skalaGulir(1, -100)).toBeGreaterThan(1);
  expect(skalaGulir(2, 100)).toBeLessThan(2);
  // deltaY 0 → skala tetap
  expect(skalaGulir(1.5, 0)).toBeCloseTo(1.5);
  // terjepit di batas
  expect(skalaGulir(1, 1000)).toBe(SKALA_MIN);
  expect(skalaGulir(SKALA_MAKS, -100000)).toBe(SKALA_MAKS);
});

test("skalaCubit: rasio jarak; jarak awal 0 aman", () => {
  expect(skalaCubit(1, 100, 200)).toBe(2);
  expect(skalaCubit(2, 200, 100)).toBe(1);
  expect(skalaCubit(3, 100, 100)).toBe(3);
  expect(skalaCubit(1, 0, 500)).toBe(1);      // jarak awal 0 → tak dibagi nol
  expect(skalaCubit(2, 100, 100000)).toBe(SKALA_MAKS); // terjepit maks
});

test("jarak & titikTengah", () => {
  expect(jarak(0, 0, 3, 4)).toBe(5);
  expect(titikTengah(0, 0, 10, 20)).toEqual({ x: 5, y: 10 });
});

test("zoomKeTitik menjaga titik fokus tetap di layar", () => {
  // Skala 1, tanpa geser, fokus 100px di kanan pusat → zoom 2×
  const { tx, ty } = zoomKeTitik(1, 0, 0, 2, 100, 0);
  expect(tx).toBe(-100);
  expect(ty).toBe(0);
  // Invarian: konten di bawah fokus tetap di posisi fokus yang sama
  // posisiLayar = pusat(=geser) + skala * konten; konten = (fokus - geserLama)/skalaLama
  const konten = (100 - 0) / 1;
  expect(tx + 2 * konten).toBe(100); // = fokusX semula
  // scale 0 → tak berubah (aman)
  expect(zoomKeTitik(0, 5, 6, 2, 10, 10)).toEqual({ tx: 5, ty: 6 });
});

test("jepitGeser: skala 1 nyaris tak bisa digeser; makin besar makin bebas", () => {
  // skala 1 → hanya margin (40) yang diizinkan
  expect(jepitGeser(500, 500, 1, 1000, 800)).toEqual({ tx: 40, ty: 40 });
  // skala 2, viewport 1000×800 → maksX=(2-1)*500+40=540, maksY=(2-1)*400+40=440
  expect(jepitGeser(10000, -10000, 2, 1000, 800)).toEqual({ tx: 540, ty: -440 });
  // di dalam batas → tak diubah
  expect(jepitGeser(100, -50, 2, 1000, 800)).toEqual({ tx: 100, ty: -50 });
});
