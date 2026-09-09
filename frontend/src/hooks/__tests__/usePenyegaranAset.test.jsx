import React, { memo, useEffect } from "react";
import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { usePenyegaranAset } from "../usePenyegaranAset";

function konteks(tambahan = {}) {
  return {
    currentPage: 3, pageSize: 50, debouncedSearch: "meja",
    filterCategory: ["Mebel"], sortBy: "newest",
    doFetch: jest.fn().mockResolvedValue(["aset"]),
    doFetchStats: jest.fn().mockResolvedValue("statistik"),
    setPageLoading: jest.fn(), ...tambahan,
  };
}

function tertunda() {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
}

test("refresh biasa memakai halaman aktif, menjalankan daftar dan statistik, tanpa skeleton", async () => {
  const p = konteks();
  const { result } = renderHook(usePenyegaranAset, { initialProps: p });
  await expect(result.current()).resolves.toEqual([["aset"], "statistik"]);
  expect(p.doFetch).toHaveBeenCalledWith(3, 50, "meja", ["Mebel"], "newest", false, false);
  expect(p.doFetchStats).toHaveBeenCalledWith("meja");
  expect(p.setPageLoading).not.toHaveBeenCalled();
});

test("callback lama tetap memakai parameter DAN closure kegiatan/filter/snapshot terbaru", async () => {
  const awal = konteks();
  const { result, rerender } = renderHook(usePenyegaranAset, { initialProps: awal });
  const refreshLama = result.current;
  // Pengganti doFetch membawa konteks kegiatan, filter lanjutan, dan jalur
  // luring terbaru. Mengunci doFetch awal dalam useCallback([]) akan gagal.
  const terbaru = konteks({ currentPage: 7, pageSize: 100, debouncedSearch: "lemari",
    filterCategory: ["Mebel", "Peralatan"], sortBy: "name_asc",
    doFetch: jest.fn().mockResolvedValue(["snapshot-kegiatan-b-filter-baru"]) });
  rerender(terbaru);
  expect(result.current).toBe(refreshLama);
  await expect(refreshLama()).resolves.toEqual([["snapshot-kegiatan-b-filter-baru"], "statistik"]);
  expect(terbaru.doFetch).toHaveBeenCalledWith(7, 100, "lemari", ["Mebel", "Peralatan"], "name_asc", false, false);
  expect(terbaru.doFetchStats).toHaveBeenCalledWith("lemari");
  expect(awal.doFetch).not.toHaveBeenCalled();
  expect(awal.doFetchStats).not.toHaveBeenCalled();
});

test("halaman eksplisit mengalahkan halaman aktif tanpa mengubah filter", async () => {
  const p = konteks();
  const { result } = renderHook(usePenyegaranAset, { initialProps: p });
  await result.current(1);
  expect(p.doFetch).toHaveBeenCalledWith(1, 50, "meja", ["Mebel"], "newest", false, false);
});

test("rekonsiliasi sesudah form ditutup mempertahankan jendela gulir HP", async () => {
  const p = konteks();
  const { result } = renderHook(usePenyegaranAset, { initialProps: p });
  await result.current(undefined, { preserveMobile: true });
  expect(p.doFetch).toHaveBeenCalledWith(3, 50, "meja", ["Mebel"], "newest", false, true);
  expect(p.setPageLoading).not.toHaveBeenCalled();
});

test("skeleton menunggu KEDUA pekerjaan yang dimulai paralel", async () => {
  const daftar = tertunda();
  const statistik = tertunda();
  const p = konteks({ doFetch: jest.fn(() => daftar.promise), doFetchStats: jest.fn(() => statistik.promise) });
  const { result } = renderHook(usePenyegaranAset, { initialProps: p });
  const selesai = result.current(1, { showLoading: true });
  expect(p.doFetch).toHaveBeenCalledTimes(1);
  expect(p.doFetchStats).toHaveBeenCalledTimes(1);
  expect(p.setPageLoading.mock.calls).toEqual([[true]]);
  daftar.resolve(["aset"]);
  await daftar.promise;
  expect(p.setPageLoading.mock.calls).toEqual([[true]]);
  statistik.resolve("statistik");
  await selesai;
  expect(p.setPageLoading.mock.calls).toEqual([[true], [false]]);
});

test("kegagalan tetap diteruskan dan skeleton dibersihkan tanpa promise yatim", async () => {
  const galat = new Error("Gagal membaca snapshot");
  const p = konteks({ doFetch: jest.fn().mockRejectedValue(galat) });
  const { result } = renderHook(usePenyegaranAset, { initialProps: p });
  await expect(result.current(1, { showLoading: true })).rejects.toBe(galat);
  expect(p.setPageLoading.mock.calls).toEqual([[true], [false]]);
});

test("render ulang dengan closure baru tidak memicu ulang efek yang bergantung callback", async () => {
  const p = konteks();
  const { rerender } = renderHook(props => {
    const refresh = usePenyegaranAset(props);
    useEffect(() => { refresh(); }, [refresh]);
  }, { initialProps: p });
  expect(p.doFetch).toHaveBeenCalledTimes(1);
  const terbaru = konteks();
  await act(async () => { rerender(terbaru); });
  expect(terbaru.doFetch).not.toHaveBeenCalled();
});

test("konsumen memo tidak dirender ulang tetapi klik tetap menjalankan closure baru", async () => {
  const renderAnak = jest.fn();
  const Anak = memo(function Anak({ refresh }) {
    renderAnak();
    return <button onClick={() => refresh()}>Muat ulang uji</button>;
  });
  function Induk({ data }) {
    const refresh = usePenyegaranAset(data);
    return <Anak refresh={refresh} />;
  }
  const awal = konteks();
  const { rerender } = render(<Induk data={awal} />);
  const terbaru = konteks();
  rerender(<Induk data={terbaru} />);
  expect(renderAnak).toHaveBeenCalledTimes(1);
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Muat ulang uji" })); });
  expect(awal.doFetch).not.toHaveBeenCalled();
  expect(terbaru.doFetch).toHaveBeenCalledTimes(1);
});
