/* eslint-env jest */
import { peekAnim } from "./lightboxAnim";

// Animasi peek kartu info lightbox: opacity kartu tetangga bertambah mengikuti
// geseran; kartu depan mengecil halus.
describe("peekAnim", () => {
  test("diam (dx=0) → kedua kartu samar (base), skala penuh", () => {
    const a = peekAnim(0);
    expect(a.dragP).toBe(0);
    expect(a.nextOpacity).toBeCloseTo(0.3);
    expect(a.prevOpacity).toBeCloseTo(0.3);
    expect(a.frontScale).toBeCloseTo(1);
  });

  test("geser kiri penuh (menuju berikutnya) → kartu KANAN pekat, kiri tetap samar", () => {
    const a = peekAnim(-110);
    expect(a.dragP).toBeCloseTo(1);
    expect(a.nextOpacity).toBeCloseTo(0.95);
    expect(a.prevOpacity).toBeCloseTo(0.3);
    expect(a.frontScale).toBeCloseTo(0.97);
  });

  test("geser kanan penuh (menuju sebelumnya) → kartu KIRI pekat", () => {
    const a = peekAnim(110);
    expect(a.nextOpacity).toBeCloseTo(0.3);
    expect(a.prevOpacity).toBeCloseTo(0.95);
  });

  test("setengah geser → opacity di antara base & peak", () => {
    const a = peekAnim(-55); // 50%
    expect(a.dragP).toBeCloseTo(0.5);
    expect(a.nextOpacity).toBeCloseTo(0.3 + 0.5 * (0.95 - 0.3));
  });

  test("melewati ambang → progress ter-clamp 1 (tak melebihi peak)", () => {
    const a = peekAnim(-500);
    expect(a.dragP).toBe(1);
    expect(a.nextOpacity).toBeCloseTo(0.95);
  });

  test("nilai non-numerik aman → dianggap 0", () => {
    const a = peekAnim(undefined);
    expect(a.dragP).toBe(0);
    expect(a.frontScale).toBeCloseTo(1);
  });
});
