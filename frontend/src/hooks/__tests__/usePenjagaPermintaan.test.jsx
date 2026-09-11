import { useEffect } from "react";
import { renderHook } from "@testing-library/react";
import { usePenjagaPermintaan } from "../usePenjagaPermintaan";

test("kanal terpisah; hanya tiket terakhir di kanal yang sama boleh menulis", () => {
  const { result } = renderHook(() => usePenjagaPermintaan("A"));
  const p = result.current;
  const a = p.mulai("daftar", "A"), s = p.mulai("statistik", "A");
  const b = p.mulai("daftar", "A");
  expect(p.berlaku(a)).toBe(false);
  expect(p.berlaku(b)).toBe(true);
  expect(p.berlaku(s)).toBe(true);
  expect(p.selesai(a)).toBe(false);
  expect(p.berlaku(b)).toBe(true);
});

test("render lingkup sama menjaga tiket; A → B → A tetap membatalkan tiket A pertama", () => {
  const { result, rerender, unmount } = renderHook(usePenjagaPermintaan, { initialProps: "A" });
  const p = result.current, tiket = p.mulai("daftar", "A");
  rerender("A"); expect(p.berlaku(tiket)).toBe(true);
  rerender("B"); expect(p.berlaku(tiket)).toBe(false);
  expect(p.mulai("daftar", "A")).toBeNull();
  rerender("A"); expect(p.berlaku(tiket)).toBe(false);
  const baru = p.mulai("daftar", "A"); expect(p.berlaku(baru)).toBe(true);
  unmount(); expect(p.berlaku(baru)).toBe(false);
  expect(p.mulai("daftar", "A")).toBeNull();
});

test("StrictMode mengaktifkan ulang penjaga dan membatalkan tiket setup pertama", () => {
  const tiket = [];
  const { result, unmount } = renderHook(() => {
    const p = usePenjagaPermintaan("A");
    useEffect(() => { tiket.push(p.mulai("daftar", "A")); }, [p]);
    return p;
  }, { reactStrictMode: true });
  expect(tiket).toHaveLength(2);
  expect(result.current.berlaku(tiket[0])).toBe(false);
  expect(result.current.berlaku(tiket[1])).toBe(true);
  unmount(); expect(result.current.berlaku(tiket[1])).toBe(false);
});

test("kunci eksklusif dilepas hanya oleh pemilik; pembatalan tidak membatalkan kanal lain", () => {
  const { result } = renderHook(() => usePenjagaPermintaan("A"));
  const p = result.current, a = p.mulai("mobile", "A", true);
  expect(p.mulai("mobile", "A", true)).toBeNull();
  p.batalkan("mobile");
  const b = p.mulai("mobile", "A", true);
  expect(p.selesai(a)).toBe(false);
  expect(p.berlaku(b)).toBe(true);
  p.batalkan("statistik"); expect(p.berlaku(b)).toBe(true);
  expect(p.selesai(b)).toBe(true);
  expect(p.sibuk("mobile")).toBe(false);
});
