/**
 * TAMBATAN POPUP TANGGAL — cacat yang lolos dari 16 uji sebelumnya.
 *
 * Laporan pemilik (19 Agu 2026): di tablet dan desktop, pada halaman Penilaian
 * dan Perencanaan Kebutuhan, "popup tanggalnya tidak tepat di bawah tanggal
 * malah bergeser ke kiri".
 *
 * Sebabnya bukan di JavaScript-nya — `buka()` sudah diuji dan benar-benar
 * memanggil `showPicker()`. Sebabnya di KOTAK yang dipakai peramban sebagai
 * tambatan popup itu. `<input type="date">`-nya memakai kelas `sr-only`, yang
 * berarti `position:absolute` + 1x1 piksel + `clip`. Elemen absolut di dalam
 * wadah flex — dan SETIAP baris kepala halaman memakai `BARIS_KEPALA` yang
 * `flex` — mengambil posisi statiknya di sudut awal wadah itu, yaitu pojok
 * KIRI baris kepala, bukan di tempat tombolnya berdiri. Popupnya pun terbit
 * di sana.
 *
 * Uji lama tak mungkin menangkapnya: semuanya bertanya "apakah pemilihnya
 * terpanggil", tak satu pun bertanya "bertambat ke mana". Berkas ini yang
 * bertanya begitu.
 */
const fs = require("fs");
const path = require("path");
import React, { useRef } from "react";
import { render, screen } from "@testing-library/react";
import TanggalanButton, { kelasBungkus, BUNGKUS_TAMPAK } from "@/components/ui/TanggalanButton";

const SRC = path.join(__dirname, "..", "..");
const BERKAS_TANGGALAN = path.join(SRC, "components/ui/TanggalanButton.jsx");

/** Kelas Tailwind yang membuat sebuah elemen jadi blok penampung (containing
 *  block) bagi anak `absolute` di dalamnya. */
const KELAS_POSISI = ["relative", "absolute", "fixed", "sticky"];

/**
 * Leluhur terdekat yang menjadi TAMBATAN kotak absolut `el` — persis yang
 * dipakai peramban untuk menaruh popup pemilih tanggal.
 */
function tambatan(el) {
  let n = el.parentElement;
  while (n && n !== document.body) {
    if (KELAS_POSISI.some((k) => n.classList.contains(k))) return n;
    n = n.parentElement;
  }
  return null;
}

/** Token ukuran (`h-9`, `w-9`) dari daftar kelas. */
function ukuran(el) {
  return [...el.classList].filter((k) => /^[hw]-/.test(k)).sort().join(" ");
}

function Bungkus({ kelasTombol = "" }) {
  const ref = useRef(null);
  return (
    // Wadah flex, persis seperti BARIS_KEPALA di halaman aslinya — di sinilah
    // elemen absolut yatim akan meleset ke pojok kiri.
    <div className="flex items-center gap-2" data-testid="baris">
      <button type="button" data-testid="pemicu"
        onClick={() => ref.current?.buka()}>Tanggal acuan</button>
      <TanggalanButton ref={ref} kelasTombol={kelasTombol}
        value="2026-08-08" onChange={() => {}} testid="tgl" />
    </div>
  );
}

describe("Popup tanggal bertambat ke tombolnya, bukan ke pojok baris kepala", () => {
  test("input tanggal punya tambatan, dan tambatannya memuat tombolnya", () => {
    // Inilah kalimat cacatnya, ditulis sebagai uji: kotak popup harus
    // bertambat pada elemen yang MEMUAT tombol yang baru saja diklik.
    render(<Bungkus />);
    const input = screen.getByTestId("tgl-input");
    const tombol = screen.getByTestId("tgl");
    const jangkar = tambatan(input);
    expect(jangkar).not.toBeNull();
    expect(jangkar).toContainElement(tombol);
    expect(jangkar).toHaveClass("relative");
  });

  test("input ditumpuk tepat di atas tombol, bukan 1x1 piksel ter-clip", () => {
    render(<Bungkus />);
    const input = screen.getByTestId("tgl-input");
    const tombol = screen.getByTestId("tgl");
    expect(input).toHaveClass("absolute", "left-0", "top-0");
    // Ukurannya harus SAMA dengan tombolnya — kalau tidak, popup bertambat ke
    // kotak yang bukan kotak yang dilihat pengguna.
    expect(ukuran(input)).toBe(ukuran(tombol));
    expect(ukuran(input)).not.toBe("");
    expect(input).not.toHaveClass("sr-only");
  });

  test("input tak kasatmata dan tak menangkap klik milik tombolnya", () => {
    render(<Bungkus />);
    const input = screen.getByTestId("tgl-input");
    expect(input).toHaveClass("opacity-0", "pointer-events-none");
    expect(input).toHaveAttribute("aria-hidden", "true");
    expect(input).toHaveAttribute("tabindex", "-1");
  });

  test("nilainya tetap mengalir dua arah — perbaikan tata letak tak memutusnya", () => {
    render(<Bungkus />);
    expect(screen.getByTestId("tgl-input")).toHaveValue("2026-08-08");
    expect(screen.getByTestId("tgl")).toHaveTextContent("08");
  });
});

describe("Tombol tersembunyi di HP: bungkusnya tetap ada, tapi tak makan tempat", () => {
  test("bungkusnya TIDAK ikut disembunyikan — pemilihnya harus tetap hidup", () => {
    // Kalau bungkusnya yang kena `hidden`, inputnya masuk subpohon
    // display:none dan butir menu "Tanggal acuan" di HP jadi tombol mati.
    render(<Bungkus kelasTombol="hidden sm:flex" />);
    const jangkar = tambatan(screen.getByTestId("tgl-input"));
    expect(jangkar).not.toBeNull();
    expect(jangkar).not.toHaveClass("hidden");
    expect(screen.getByTestId("tgl")).toHaveClass("hidden");
  });

  test("bungkusnya keluar dari aliran di bawah breakpoint tombolnya", () => {
    // Bungkus yang selalu hadir akan menyisakan satu `gap` flex kosong di
    // baris kepala HP. `absolute` membuatnya tetap dirender tanpa memakan
    // tempat, lalu `sm:relative` mengembalikannya begitu tombolnya muncul.
    render(<Bungkus kelasTombol="hidden sm:flex" />);
    const jangkar = tambatan(screen.getByTestId("tgl-input"));
    expect(jangkar).toHaveClass("absolute", "sm:relative");
  });
});

describe("kelasBungkus — pemetaan kelasTombol → kelas bungkus", () => {
  test("tombol yang selalu tampak dapat bungkus relative", () => {
    expect(kelasBungkus("")).toBe(BUNGKUS_TAMPAK);
    expect(kelasBungkus()).toBe(BUNGKUS_TAMPAK);
    expect(kelasBungkus("ring-2")).toBe(BUNGKUS_TAMPAK);
    expect(BUNGKUS_TAMPAK).toMatch(/(^|\s)relative(\s|$)/);
  });

  test("breakpoint tombolnya diikuti, bukan diasumsikan sm", () => {
    expect(kelasBungkus("hidden sm:flex")).toBe("absolute sm:relative inline-flex flex-shrink-0");
    expect(kelasBungkus("hidden md:inline-flex")).toBe("absolute md:relative inline-flex flex-shrink-0");
    expect(kelasBungkus("hidden lg:flex")).toBe("absolute lg:relative inline-flex flex-shrink-0");
    expect(kelasBungkus("hidden 2xl:flex")).toBe("absolute 2xl:relative inline-flex flex-shrink-0");
  });

  test("tombol tersembunyi tanpa breakpoint tetap dapat bungkus di luar aliran", () => {
    expect(kelasBungkus("hidden")).toBe("absolute inline-flex flex-shrink-0");
  });

  test("bungkus TIDAK PERNAH ikut hidden", () => {
    for (const k of ["", "hidden", "hidden sm:flex", "hidden md:inline-flex", "hidden xl:flex"]) {
      expect(kelasBungkus(k)).not.toMatch(/(^|\s)hidden(\s|$)/);
    }
  });

  test("`overflow-hidden` bukan `hidden` — jangan sampai tertukar", () => {
    // Pencocokan token, bukan substring: kelas seperti `overflow-hidden` tak
    // boleh membuat bungkusnya dikira tersembunyi.
    expect(kelasBungkus("overflow-hidden")).toBe(BUNGKUS_TAMPAK);
  });
});

describe("Kelas responsif harus LITERAL — pemindai Tailwind membaca teks", () => {
  // Komentar dibuang: catatan di berkas itu MENYEBUT bentuk terlarangnya
  // (`${bp}:relative`) sebagai contoh apa yang tak boleh ditulis.
  const teks = fs.readFileSync(BERKAS_TANGGALAN, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

  test("tiap varian bungkus tertulis utuh di berkas sumbernya", () => {
    // `${bp}:relative` akan lolos semua uji perilaku di atas namun kelasnya
    // TAK PERNAH tergenerate ke CSS, jadi bungkusnya diam-diam kehilangan
    // `position` dan cacat ini kembali persis seperti semula.
    for (const bp of ["sm", "md", "lg", "xl", "2xl"]) {
      expect(teks).toContain(`absolute ${bp}:relative inline-flex flex-shrink-0`);
    }
  });

  test("tak ada kelas posisi yang dirakit lewat template", () => {
    expect(teks).not.toMatch(/\$\{[^}]*\}:(relative|absolute|flex|hidden)/);
  });
});

describe("Pemindai: input tanggal native tak boleh disembunyikan dengan sr-only", () => {
  function berkasJsx(dir) {
    return fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
      const p = path.join(dir, d.name);
      if (d.isDirectory()) return d.name === "node_modules" ? [] : berkasJsx(p);
      return /\.(jsx|js)$/.test(d.name) && !/\.test\./.test(d.name) ? [p] : [];
    });
  }

  test("nol pelanggar di seluruh src/", () => {
    // Kelas cacatnya: pemilih native (date/time/month) dipakai sebagai pintu
    // tersembunyi, lalu disembunyikan dengan `sr-only` — 1x1 piksel ter-clip
    // dan `position:absolute` yatim. Popupnya melayang entah ke mana. Cara
    // benarnya: tumpuk di atas pemicunya (`absolute` di dalam `relative`)
    // dengan `opacity-0 pointer-events-none`.
    const pelanggar = [];
    for (const f of berkasJsx(SRC)) {
      const isi = fs.readFileSync(f, "utf8");
      for (const tag of isi.match(/<[Ii]nput\b[^>]*>/g) || []) {
        if (!/type="(date|time|month|datetime-local)"/.test(tag)) continue;
        if (/\bsr-only\b/.test(tag)) pelanggar.push(`${path.relative(SRC, f)}: ${tag.slice(0, 80)}`);
      }
    }
    expect(pelanggar).toEqual([]);
  });

  test("pemindainya benar-benar bisa melihat — dibuktikan pada contoh palsu", () => {
    // Pemindai yang regexnya salah akan selalu melaporkan nol. Ini buktinya
    // bukan nol karena buta.
    const contoh = '<input type="date" className="sr-only" />';
    expect(/<[Ii]nput\b[^>]*>/.test(contoh)).toBe(true);
    const tag = contoh.match(/<[Ii]nput\b[^>]*>/)[0];
    expect(/type="(date|time|month|datetime-local)"/.test(tag)).toBe(true);
    expect(/\bsr-only\b/.test(tag)).toBe(true);
  });
});
