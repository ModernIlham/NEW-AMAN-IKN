import { act, renderHook } from "@testing-library/react";
import { indeksJangkar, useJangkarDaftarAset, usePosisiDaftarAset } from "../usePosisiDaftarAset";

const baris = (...ids) => ids.map(id => ({ id }));

test.each([
  [["a", "b", "c", "d"], 1, ["c", "b", "a"], 1],
  [["a", "b", "c", "d"], 1, ["a", "c", "d"], 1],
  [["a", "b", "c", "d"], 3, ["a", "b"], 1],
  [["a", "b", "c"], 2, ["x"], 0],
  [["a", "b", "c"], 2, [], 0],
])("jangkar memakai ID, tetangga, lalu posisi valid terdekat", (lama, index, baru, hasil) => {
  expect(indeksJangkar(lama, index, baris(...baru))).toBe(hasil);
});

function virtualTest(tambahan = {}) {
  const virtualizer = {
    scrollElement: { scrollTop: 155, clientHeight: 300 },
    getVirtualItems: () => [{ index: 0, start: 0, end: 100 }, { index: 1, start: 100, end: 200 }],
    getOffsetForIndex: jest.fn(index => [index * 100, "start"]),
    scrollToOffset: jest.fn(),
  };
  const perekam = new Map();
  const daftarkan = (nama, fn) => {
    perekam.set(nama, fn);
    return () => perekam.delete(nama);
  };
  const props = { daftarkan, nama: "uji", assets: baris("a", "b", "c", "d"), virtualizer, ...tambahan };
  return { props, perekam, virtualizer, ...renderHook(useJangkarDaftarAset, { initialProps: props }) };
}

test("refresh menjaga barang terlihat dan offset intra-baris meski urutan berubah", () => {
  const p = virtualTest();
  p.perekam.get("uji")();
  p.rerender({ ...p.props, assets: baris("c", "a", "b", "d") });
  expect(p.virtualizer.getOffsetForIndex).toHaveBeenCalledWith(2, "start");
  expect(p.virtualizer.scrollToOffset).toHaveBeenCalledWith(255, { behavior: "auto" });
});

test("galeri menghitung ulang indeks baris dari ID barang dan jumlah kolom", () => {
  const p = virtualTest({ columns: 2, assets: baris("a", "b", "c", "d", "e", "f") });
  p.perekam.get("uji")();
  p.rerender({ ...p.props, assets: baris("c", "d", "e", "f", "a", "b") });
  expect(p.virtualizer.getOffsetForIndex).toHaveBeenCalledWith(0, "start");
  expect(p.virtualizer.scrollToOffset).toHaveBeenCalledWith(55, { behavior: "auto" });
});

test("render biasa tidak mengambil alih gulir dan pembaruan tanpa capture tidak melompat", () => {
  const p = virtualTest();
  p.rerender({ ...p.props, assets: baris("d", "c", "b", "a") });
  expect(p.virtualizer.scrollToOffset).not.toHaveBeenCalled();
});

test("capture mengambil gulir terbaru ketika commit, bukan posisi awal request", () => {
  const p = virtualTest();
  p.virtualizer.scrollElement.scrollTop = 180;
  p.perekam.get("uji")();
  p.rerender({ ...p.props, assets: baris("a", "b", "c", "d") });
  expect(p.virtualizer.scrollToOffset).toHaveBeenCalledWith(180, { behavior: "auto" });
  p.virtualizer.scrollToOffset.mockClear();
  p.rerender({ ...p.props, assets: baris("a", "c", "d") });
  expect(p.virtualizer.scrollToOffset).not.toHaveBeenCalled(); // hanya satu commit
});

test("komponen tersembunyi atau hasil kosong tidak memaksakan scroll", () => {
  const p = virtualTest();
  p.virtualizer.scrollElement.clientHeight = 0;
  p.perekam.get("uji")();
  p.rerender({ ...p.props, assets: [] });
  expect(p.virtualizer.scrollToOffset).not.toHaveBeenCalled();
  p.unmount();
  expect(p.perekam.size).toBe(0);
});

test.each([false, true])("main mengompensasi panel tanpa menggandakan native scroll anchoring; native=%s", native => {
  let offset = 100;
  const mainRef = { current: { scrollTop: 500 } };
  const daftarRef = { current: { getBoundingClientRect: () => ({ top: offset }) } };
  const { result, rerender } = renderHook(() => usePosisiDaftarAset(mainRef, daftarRef));
  act(() => result.current.rekamPosisi());
  // Panel setinggi 200 hilang. Jika browser sudah mengurangi scrollTop,
  // posisi daftar relatif viewport tetap sama dan hook tidak menguranginya lagi.
  if (native) mainRef.current.scrollTop = 300;
  else offset = -100;
  rerender();
  expect(mainRef.current.scrollTop).toBe(300);
});

test("capture main tidak merekam daftar kecuali tepat sebelum pergantian data", () => {
  const { result, rerender } = renderHook(() => usePosisiDaftarAset({ current: null }, { current: null }));
  const rekam = jest.fn();
  const lepas = result.current.daftarkan("daftar", rekam);
  result.current.rekamPosisi(); expect(rekam).not.toHaveBeenCalled();
  result.current.rekamPosisi(true); expect(rekam).toHaveBeenCalledTimes(1);
  lepas(); rerender();
  result.current.rekamPosisi(true); expect(rekam).toHaveBeenCalledTimes(1);
});
