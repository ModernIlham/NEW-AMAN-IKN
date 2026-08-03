/**
 * Uji tooltip teks kustom — menjaga dua regresi yang pernah membuat tooltip
 * tabel "kadang muncul, kadang tidak":
 *  1. guliran yang lahir dari animasi marquee (teks berjalan) sempat dianggap
 *     guliran kontainer, sehingga membunuh tooltip yang baru saja dijadwalkan;
 *  2. `mouseout` sel lama menyembunyikan tooltip sel BARU (mouseout tiba
 *     setelah mouseover tetangganya).
 */
import { pasangPenyembunyiTooltip, sembunyikanTooltip, tampilkanTooltip } from "./tooltipTeks";

const kotak = () => document.querySelector('[data-aman-tooltip="1"]');
const tampak = () => kotak()?.style.visibility === "visible";

function elemen({ marquee = false } = {}) {
  const n = document.createElement("div");
  if (marquee) n.dataset.marqueeAktif = "1";
  document.body.appendChild(n);
  return n;
}

beforeAll(() => {
  jest.useFakeTimers();
  pasangPenyembunyiTooltip(document);
});

beforeEach(() => sembunyikanTooltip());

test("tooltip tampil setelah jeda dan memakai warna tema", () => {
  tampilkanTooltip(elemen(), "Jalan Utama Terbangun PUPR");
  expect(tampak()).toBe(false);           // masih menunggu jeda
  jest.advanceTimersByTime(400);
  expect(tampak()).toBe(true);
  expect(kotak().textContent).toBe("Jalan Utama Terbangun PUPR");
  // Latar mengikuti --primary; di jsdom variabel tema tak ada sehingga yang
  // teruji adalah nilai cadangannya — teal tema, bukan gelap netral seperti dulu.
  expect(kotak().style.background).toBe("rgb(24, 103, 95)");
});

test("guliran animasi marquee elemen LAIN tidak membunuh tooltip", () => {
  tampilkanTooltip(elemen(), "Gedung Kantor Blok B");
  const tetangga = elemen({ marquee: true });   // sel lain sedang berjalan pulang
  tetangga.dispatchEvent(new Event("scroll"));
  jest.advanceTimersByTime(400);
  expect(tampak()).toBe(true);
});

test("guliran kontainer biasa tetap menyembunyikan tooltip", () => {
  tampilkanTooltip(elemen(), "Gedung Kantor Blok B");
  jest.advanceTimersByTime(400);
  expect(tampak()).toBe(true);
  elemen().dispatchEvent(new Event("scroll"));   // tabel/panel digulir pengguna
  expect(tampak()).toBe(false);
});

test("meninggalkan sel lain tidak membatalkan tooltip sel yang aktif", () => {
  const aktif = elemen();
  tampilkanTooltip(aktif, "Sel yang sedang di-hover");
  sembunyikanTooltip(elemen());                  // mouseout sel sebelumnya
  jest.advanceTimersByTime(400);
  expect(tampak()).toBe(true);
  sembunyikanTooltip(aktif);                     // kursor benar-benar pergi
  expect(tampak()).toBe(false);
});
