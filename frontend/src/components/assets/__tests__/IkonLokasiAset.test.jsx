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
// Keterangan (title/aria-label) dibawa PEMBUNGKUS, bukan glyph-nya: pembungkus
// itulah satuan penandanya — ia memuat latar denah sekaligus glyph koordinat,
// dan dua nama untuk satu penanda akan disebut dua kali pembaca layar.
const penanda = (id) => screen.getByTestId(`lokasi-penanda-${id}`);

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
  const el = penanda("a1");
  expect(el.getAttribute("aria-label")).toContain("-1.234567");
  expect(el.getAttribute("aria-label")).toContain("116.7");
  expect(el.getAttribute("title")).toBe(el.getAttribute("aria-label"));
  // Namanya harus benar-benar terekspos: span ber-aria-label tanpa role tidak
  // menyandang nama apa pun bagi pembaca layar.
  expect(el.getAttribute("role")).toBe("img");
  expect(ikon("a1").getAttribute("aria-hidden")).toBe("true");
});

it("aset tanpa koordinat berketerangan 'belum ada'", () => {
  render(<IkonLokasiAset asset={TANPA} />);
  expect(penanda("a2").getAttribute("aria-label")).toMatch(/belum ada titik koordinat/i);
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

// ── Penanda kedua: sudah masuk denah atau belum ─────────────────────────
//
// Permintaan pemilik: penanda denah harus ada "di dalam icon yang sama" dan
// "masih dapat dilihat baik dalam posisi belum berkoordinat dan sudah
// berkoordinatnya" — dua keterangan yang saling BEBAS, empat keadaan, pada
// glyph selebar 10px.
//
// Kanalnya sengaja tegak lurus: bentuk glyph membawa koordinat, latar kotak
// membawa denah. Yang dijaga di sini adalah kebebasan itu — masing-masing
// terbaca tanpa bergantung pada yang lain.

const DI_DENAH = { id: "d1", di_denah: true, denah_jalur: "Gedung A / Lt 2 / R201" };
const penandaEl = (id) => screen.getByTestId(`lokasi-penanda-${id}`);

it.each([
  ["belum keduanya", {}, "tidak", "tidak"],
  ["koordinat saja", { koordinat_latitude: "-1.2", koordinat_longitude: "116.7" }, "ya", "tidak"],
  ["denah saja", { di_denah: true }, "tidak", "ya"],
  ["keduanya", { koordinat_latitude: "-1.2", koordinat_longitude: "116.7", di_denah: true }, "ya", "ya"],
])("keempat keadaan terbaca terpisah: %s", (_n, aset, koord, denah) => {
  render(<IkonLokasiAset asset={{ id: "z", ...aset }} />);
  expect(ikon("z")).toHaveAttribute("data-berkoordinat", koord);
  expect(penandaEl("z")).toHaveAttribute("data-di-denah", denah);
});

it("latar denah muncul TANPA bergantung pada keadaan koordinat", () => {
  // Inti permintaannya: penanda denah tetap terlihat pada kedua posisi.
  const kelas = (aset) => {
    const { container, unmount } = render(<IkonLokasiAset asset={aset} />);
    const k = container.querySelector('[data-di-denah]').getAttribute("class");
    unmount();
    return k;
  };
  const tanpaKoord = kelas({ id: "p", di_denah: true });
  const denganKoord = kelas({ id: "q", di_denah: true,
    koordinat_latitude: "-1.2", koordinat_longitude: "116.7" });
  expect(tanpaKoord).toContain("bg-sky-500/15");
  expect(denganKoord).toContain("bg-sky-500/15");
});

it("latar TIDAK dipakai untuk menandai koordinat", () => {
  // Kalau latar ikut menyala oleh koordinat, kedua keterangan berhimpit dan
  // tak lagi terbaca terpisah.
  render(<IkonLokasiAset asset={{ id: "r",
    koordinat_latitude: "-1.2", koordinat_longitude: "116.7" }} />);
  expect(penandaEl("r").getAttribute("class")).not.toContain("bg-sky");
});

it("bentuk glyph TIDAK berubah oleh denah", () => {
  // Bentuk sudah bermakna koordinat sejak lama; memindahkannya akan mengubah
  // arti penanda yang sudah dikenal pemakainya.
  const bentuk = (aset) => {
    const { unmount } = render(<IkonLokasiAset asset={aset} />);
    const k = ikon("s").getAttribute("class");
    unmount();
    return k;
  };
  expect(bentuk({ id: "s" })).toBe(bentuk({ id: "s", di_denah: true }));
});

it("keterangannya menyebut KEDUA hal sekaligus", () => {
  render(<IkonLokasiAset asset={DI_DENAH} />);
  const t = penandaEl("d1").getAttribute("aria-label");
  expect(t).toMatch(/belum ada titik koordinat/i);
  expect(t).toMatch(/sudah masuk denah/i);
  expect(t).toContain("Gedung A / Lt 2 / R201");
});

it("yang belum di denah pun dinyatakan, bukan didiamkan", () => {
  // Keterangan yang hanya muncul saat sudah masuk denah membuat pembaca tak
  // bisa membedakan "belum" dari "penandanya memang tak ada".
  render(<IkonLokasiAset asset={{ id: "t" }} />);
  expect(penandaEl("t").getAttribute("aria-label")).toMatch(/belum masuk denah/i);
});

it("pembungkusnya selalu ada agar baris tetap rata", () => {
  // Pembungkus yang hanya muncul saat beralas denah menggeser teks di
  // sebelahnya, dan baris-baris dalam satu daftar tak lagi lurus.
  render(<IkonLokasiAset asset={{ id: "u" }} />);
  expect(penandaEl("u").getAttribute("class")).toContain("p-[2px]");
});
