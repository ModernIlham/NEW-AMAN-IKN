/**
 * Penanda status koordinat pada ikon pin lokasi.
 *
 * Permintaan pemilik: *"pada row data aset di setiap kegiatan, baik tampilan
 * list maupun galeri, dan di ukuran layar apa pun — berikan badge centang
 * hijau di ikon pin lokasi sebagai penanda sudah ada titik koordinat, atau
 * ganti dengan ikon lokasi yang bercentang."*
 *
 * Yang dijaga di sini: ikonnya BERGANTI (bukan sekadar berganti warna, yang
 * tak terbaca oleh mata yang sulit membedakan warna), dan keterangannya
 * terbaca pembaca layar.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import IkonLokasiAset from "../IkonLokasiAset";

const BERKOORDINAT = { id: "a1", koordinat_latitude: "-1.234567",
                       koordinat_longitude: "116.700000" };
const TANPA = { id: "a2", koordinat_latitude: "", koordinat_longitude: "" };

const ikon = (id) => screen.getByTestId(`lokasi-ikon-${id}`);

it("aset berkoordinat memakai ikon yang BERBEDA, bukan sekadar warna lain", () => {
  const { unmount } = render(<IkonLokasiAset asset={BERKOORDINAT} />);
  const kelasAda = ikon("a1").getAttribute("class");
  unmount();
  render(<IkonLokasiAset asset={TANPA} />);
  const kelasKosong = ikon("a2").getAttribute("class");
  // lucide menyematkan nama ikonnya sebagai kelas (lucide-map-pin-check vs
  // lucide-map-pin) — itulah buktinya bentuknya memang berganti.
  expect(kelasAda).toContain("map-pin-check");
  expect(kelasKosong).not.toContain("map-pin-check");
});

it("aset berkoordinat ditandai hijau", () => {
  render(<IkonLokasiAset asset={BERKOORDINAT} />);
  expect(ikon("a1").getAttribute("class")).toContain("text-emerald-500");
});

it("aset tanpa koordinat SELALU abu-abu, tak bisa dititipi warna lain", () => {
  // Laporan pemilik: pin cyan lama di kartu galeri terbaca seolah hijau,
  // sehingga aset yang BELUM berkoordinat tampak sudah. Warna ikon ini tak
  // lagi bisa dititipkan pemanggil — satu-satunya kontras yang boleh ada di
  // sini adalah kontras yang MENANDAI sesuatu.
  render(<IkonLokasiAset asset={TANPA} warnaKosong="text-cyan-500" />);
  const kelas = ikon("a2").getAttribute("class");
  expect(kelas).toContain("text-muted-foreground");
  expect(kelas).not.toContain("text-cyan-500");
  expect(kelas).not.toContain("text-emerald-500");
});

it("keterangannya menyebut koordinatnya dan terbaca pembaca layar", () => {
  render(<IkonLokasiAset asset={BERKOORDINAT} />);
  const el = ikon("a1");
  expect(el.getAttribute("aria-label")).toContain("-1.234567");
  expect(el.getAttribute("aria-label")).toContain("116.7");
  expect(el.getAttribute("title")).toBe(el.getAttribute("aria-label"));
});

it("aset tanpa koordinat berketerangan 'belum ada'", () => {
  render(<IkonLokasiAset asset={TANPA} />);
  expect(ikon("a2").getAttribute("aria-label")).toMatch(/belum ada titik koordinat/i);
});

it("ukuran ikon mengikuti titipan pemanggil", () => {
  // Kartu galeri memakai 10px; ukuran yang dipatok akan merusak tata letaknya.
  render(<IkonLokasiAset asset={TANPA} className="w-2.5 h-2.5" />);
  expect(ikon("a2").getAttribute("class")).toContain("w-2.5");
});

it("satu sumbu saja BUKAN titik koordinat", () => {
  render(<IkonLokasiAset asset={{ id: "a3", koordinat_latitude: "-1.2" }} />);
  expect(ikon("a3").getAttribute("data-berkoordinat")).toBe("tidak");
});

it("titik nol,nol tetap terhitung berkoordinat", () => {
  render(<IkonLokasiAset asset={{ id: "a4", koordinat_latitude: "0",
                                  koordinat_longitude: "0" }} />);
  expect(ikon("a4").getAttribute("data-berkoordinat")).toBe("ya");
});

it("aset kosong tak melempar", () => {
  expect(() => render(<IkonLokasiAset asset={null} />)).not.toThrow();
});
