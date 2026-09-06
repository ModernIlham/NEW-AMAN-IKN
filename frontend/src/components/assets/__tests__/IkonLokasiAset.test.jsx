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
// Keterangan (title/aria-label) dibawa PEMBUNGKUS, bukan gambarnya: pembungkus
// itulah satuan penandanya, dan dua nama untuk satu penanda akan disebut dua
// kali pembaca layar.
const penanda = (id) => screen.getByTestId(`lokasi-penanda-${id}`);
// Ikonnya digambar sendiri dari potongan lucide supaya tiap bagian bisa
// diwarnai terpisah; bentuknya karena itu ditagih lewat `data-bentuk`, bukan
// lewat nama kelas yang dulu disematkan lucide.
const bagian = (id, nama) =>
  ikon(id).querySelector(`[data-bagian="${nama}"]`);

it("aset berkoordinat memakai ikon yang BERBEDA, bukan sekadar warna lain", () => {
  const { unmount } = render(<IkonLokasiAset asset={BERKOORDINAT} />);
  const bentukAda = ikon("a1").getAttribute("data-bentuk");
  unmount();
  render(<IkonLokasiAset asset={TANPA} />);
  const bentukKosong = ikon("a2").getAttribute("data-bentuk");
  expect(bentukAda).toContain("cek");
  expect(bentukKosong).toContain("titik");
  expect(bentukAda).not.toBe(bentukKosong);
});

it("aset berkoordinat ditandai hijau", () => {
  render(<IkonLokasiAset asset={BERKOORDINAT} />);
  expect(bagian("a1", "koordinat").getAttribute("class"))
    .toContain("stroke-emerald-500");
});

it("aset tanpa koordinat SELALU abu-abu, tak bisa dititipi warna lain", () => {
  // Laporan pemilik: pin cyan lama di kartu galeri terbaca seolah hijau,
  // sehingga aset yang BELUM berkoordinat tampak sudah. Warna ikon ini tak
  // lagi bisa dititipkan pemanggil — satu-satunya kontras yang boleh ada di
  // sini adalah kontras yang MENANDAI sesuatu.
  render(<IkonLokasiAset asset={TANPA} warnaKosong="text-cyan-500" />);
  const kelas = bagian("a2", "koordinat").getAttribute("class");
  expect(kelas).toContain("stroke-muted-foreground");
  expect(kelas).not.toContain("cyan");
  expect(kelas).not.toContain("emerald");
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

it.each([
  ["belum keduanya", {}, "tidak", "tidak"],
  ["koordinat saja", { koordinat_latitude: "-1.2", koordinat_longitude: "116.7" }, "ya", "tidak"],
  ["denah saja", { di_denah: true }, "tidak", "ya"],
  ["keduanya", { koordinat_latitude: "-1.2", koordinat_longitude: "116.7", di_denah: true }, "ya", "ya"],
])("keempat keadaan terbaca terpisah: %s", (_n, aset, koord, denah) => {
  render(<IkonLokasiAset asset={{ id: "z", ...aset }} />);
  expect(ikon("z")).toHaveAttribute("data-berkoordinat", koord);
  expect(penanda("z")).toHaveAttribute("data-di-denah", denah);
});

it("alas denah muncul TANPA bergantung pada keadaan koordinat", () => {
  // Inti permintaannya: penanda denah tetap terlihat pada kedua posisi.
  const { unmount } = render(<IkonLokasiAset asset={{ id: "p", di_denah: true }} />);
  expect(bagian("p", "denah")).toBeTruthy();
  unmount();
  render(<IkonLokasiAset asset={{ id: "q", di_denah: true,
    koordinat_latitude: "-1.2", koordinat_longitude: "116.7" }} />);
  expect(bagian("q", "denah")).toBeTruthy();
});

it("WARNA denah dan warna koordinat berada pada elemen TERPISAH", () => {
  // Keluhan pemilik atas percobaan pertama: ketika sudah ada denah tetapi
  // belum ada koordinat, warnanya menjadi SARU. Sebabnya latar biru dan pin
  // abu-abu bertumpuk pada bidang yang sama, sehingga mata membacanya sebagai
  // satu penanda setengah menyala alih-alih dua keterangan.
  //
  // Yang dijaga: kedua warna hidup pada elemen yang BERBEDA, dan tak ada satu
  // elemen pun yang menyandang keduanya.
  render(<IkonLokasiAset asset={{ id: "saru", di_denah: true }} />);
  const koord = bagian("saru", "koordinat").getAttribute("class");
  const denah = bagian("saru", "denah").getAttribute("class");
  expect(koord).toContain("stroke-muted-foreground");
  expect(denah).toContain("stroke-sky-500");
  expect(koord).not.toContain("sky");
  expect(denah).not.toContain("muted-foreground");
});

it("alas denah TIDAK muncul untuk menandai koordinat", () => {
  // Kalau alas ikut muncul oleh koordinat, kedua keterangan berhimpit dan
  // tak lagi terbaca terpisah.
  render(<IkonLokasiAset asset={{ id: "r",
    koordinat_latitude: "-1.2", koordinat_longitude: "116.7" }} />);
  expect(bagian("r", "denah")).toBeNull();
});

it("belum ada keduanya: seluruhnya abu-abu, tanpa alas", () => {
  // Permintaan pemilik: "ketika belum memiliki semua maka semua menjadi abu."
  render(<IkonLokasiAset asset={{ id: "kosong" }} />);
  expect(bagian("kosong", "denah")).toBeNull();
  expect(bagian("kosong", "koordinat").getAttribute("class"))
    .toContain("stroke-muted-foreground");
});

it("centang tetap ada saat sudah di denah, hanya berpindah letak", () => {
  // Permintaan pemilik: bentuknya berubah saat di denah, "akan tetapi tetap
  // ada centangnya". Ruang kanan-bawah sudah terpakai alas, jadi centangnya
  // masuk ke dalam kepala pin.
  render(<IkonLokasiAset asset={{ id: "c", di_denah: true,
    koordinat_latitude: "-1.2", koordinat_longitude: "116.7" }} />);
  expect(ikon("c").getAttribute("data-bentuk")).toBe("ringkas-cek");
  // Di sini centang MENGGANTIKAN titik, sebab ia berada di dalam kepala.
  expect(ikon("c").querySelector("circle")).toBeNull();
});

it("pin MENGERUT saat beralas denah agar tak menembus alasnya", () => {
  // Pin lebar menjulur sampai dasar kotak; dipakai bersama alas denah, ia
  // menembusnya. Ditagih lewat path yang BENAR-BENAR digambar.
  const d = (aset) => {
    const { unmount } = render(<IkonLokasiAset asset={aset} />);
    const path = ikon("m").querySelector("path").getAttribute("d");
    unmount();
    return path;
  };
  const ringkas = d({ id: "m", di_denah: true });
  const lebar = d({ id: "m" });
  expect(ringkas).not.toBe(lebar);
  expect(ringkas.startsWith("M18 8")).toBe(true);
  expect(lebar.startsWith("M20 10")).toBe(true);
});

it("penanda bentuk menyebut pin yang BENAR-BENAR digambar", () => {
  // Bukan sekadar menyatakan ulang `di_denah`: atribut yang dihitung dari
  // masukan yang sama dengan yang hendak dibuktikannya tak menjaga apa pun.
  render(<IkonLokasiAset asset={{ id: "n", di_denah: true }} />);
  const el = ikon("n");
  expect(el.getAttribute("data-bentuk")).toBe("ringkas-titik");
  expect(el.querySelector("path").getAttribute("d").startsWith("M18 8")).toBe(true);
});

it("pin bercentang di LUAR tetap punya titik di kepalanya", () => {
  // Ditemukan saat memeriksa hasil cetaknya pada 32px: centang sempat
  // MENGGANTIKAN titik juga di sini, sehingga pinnya tersisa sebagai tapal
  // kuda — bentuk yang tak lagi terbaca sebagai pin lokasi. `MapPinCheck`
  // asli membawa keduanya.
  render(<IkonLokasiAset asset={BERKOORDINAT} />);
  expect(ikon("a1").getAttribute("data-bentuk")).toBe("lebar-cek");
  expect(ikon("a1").querySelector("circle")).toBeTruthy();
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
  const t = penanda("d1").getAttribute("aria-label");
  expect(t).toMatch(/belum ada titik koordinat/i);
  expect(t).toMatch(/sudah masuk denah/i);
  expect(t).toContain("Gedung A / Lt 2 / R201");
});

it("yang belum di denah pun dinyatakan, bukan didiamkan", () => {
  // Keterangan yang hanya muncul saat sudah masuk denah membuat pembaca tak
  // bisa membedakan "belum" dari "penandanya memang tak ada".
  render(<IkonLokasiAset asset={{ id: "t" }} />);
  expect(penanda("t").getAttribute("aria-label")).toMatch(/belum masuk denah/i);
});

it("ukuran kotaknya TETAP di keempat keadaan agar baris rata", () => {
  // Ikon yang berubah ukuran mengikuti keadaannya menggeser teks di
  // sebelahnya, dan baris-baris dalam satu daftar tak lagi lurus. Seluruh
  // bentuk digambar di dalam viewBox yang sama.
  for (const [i, aset] of [{}, { di_denah: true },
    { koordinat_latitude: "-1.2", koordinat_longitude: "116.7" }].entries()) {
    const { unmount } = render(
      <IkonLokasiAset asset={{ id: `u${i}`, ...aset }} className="w-3 h-3" />);
    const el = ikon(`u${i}`);
    expect(el.getAttribute("viewBox")).toBe("0 0 24 24");
    expect(el.getAttribute("class")).toContain("w-3");
    unmount();
  }
});
