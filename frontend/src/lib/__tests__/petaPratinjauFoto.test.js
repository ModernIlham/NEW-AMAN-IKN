/**
 * Tombol hapus (×) pada pratinjau foto popup "Aset baru di titik ini" tidak
 * boleh menutupi fotonya di HP/tablet.
 *
 * Cacat aslinya: tombol diberi `width:16px;height:16px` lewat gaya inline,
 * tetapi aturan tap-target global di `index.css` memakai
 * `min-width`/`min-height: 44px`. Dalam CSS, min-* SELALU menang atas
 * width/height — sespesifik apa pun gaya inline-nya. Di ≤1023px tombol
 * membengkak jadi 44×44 px di atas thumbnail 40 px, sehingga lingkaran merah
 * menutupi hampir seluruh foto.
 *
 * CATATAN kenapa uji ini membaca CSS, bukan merender:
 * jsdom TIDAK mengevaluasi `@media` — `getComputedStyle` pada tombol di dalam
 * jsdom mengembalikan `min-width: ""` walau aturan 44px terpasang. Artinya uji
 * render justru akan LULUS meski cacatnya utuh: ia tak pernah menerapkan
 * aturan yang jadi biang masalah. Karena itu invariannya diperiksa langsung
 * pada sumber CSS — di sanalah aturan dan penawarnya hidup berdampingan.
 */
const fs = require("fs");
const path = require("path");

const SRC = path.resolve(__dirname, "..", "..");
const CSS = fs.readFileSync(path.join(SRC, "index.css"), "utf8");
const JSX = fs.readFileSync(
  path.join(SRC, "components", "assets", "AssetMapFullView.jsx"), "utf8");

/** Isi blok `{...}` yang dimulai pada indeks `buka`, dengan pencocokan kurung. */
function blok(teks, buka) {
  let dalam = 0;
  for (let i = buka; i < teks.length; i += 1) {
    if (teks[i] === "{") dalam += 1;
    else if (teks[i] === "}") {
      dalam -= 1;
      if (dalam === 0) return teks.slice(buka + 1, i);
    }
  }
  throw new Error("kurung kurawal tak seimbang di index.css");
}

/** Deklarasi (`{prop: nilai}`) dari aturan `selektor` di dalam `teks`. */
function deklarasi(teks, selektor) {
  const at = teks.indexOf(selektor);
  if (at < 0) return null;
  const buka = teks.indexOf("{", at);
  // Komentar dibuang SEBELUM memisah pada `;` — komentar CSS boleh memuat
  // titik koma, dan memisah lebih dulu akan memotongnya di tengah sehingga
  // deklarasi sesudahnya terbaca sebagai nama properti yang aneh.
  const isi = blok(teks, buka).replace(/\/\*[\s\S]*?\*\//g, "");
  const out = {};
  isi.split(";").forEach((baris) => {
    const bersih = baris.trim();
    const p = bersih.indexOf(":");
    if (p > 0) out[bersih.slice(0, p).trim()] = bersih.slice(p + 1).trim();
  });
  return out;
}

/** Blok `@media (max-width: 1023px)` yang memuat `penanda`. */
function blokLayarSempit(penanda) {
  let dari = 0;
  for (;;) {
    const at = CSS.indexOf("@media (max-width: 1023px)", dari);
    if (at < 0) return null;
    const isi = blok(CSS, CSS.indexOf("{", at));
    if (isi.includes(penanda)) return isi;
    dari = at + 1;
  }
}

const px = (v) => {
  const m = /^(-?\d+(?:\.\d+)?)px$/.exec(String(v || "").trim());
  return m ? Number(m[1]) : NaN;
};

// ---------------------------------------------------------------------------
// Premis: aturan yang menyebabkan cacatnya memang masih ada
// ---------------------------------------------------------------------------

describe("premis — aturan tap-target 44px global", () => {
  test("aturan 44px untuk button/a di ≤1023px masih terpasang", () => {
    const isi = blokLayarSempit("button, a {");
    expect(isi).not.toBeNull();
    const d = deklarasi(isi, "button, a {");
    expect(px(d["min-height"])).toBe(44);
    expect(px(d["min-width"])).toBe(44);
  });
});

// ---------------------------------------------------------------------------
// Penawar
// ---------------------------------------------------------------------------

describe("pratinjau foto peta — tombol hapus tak menutupi foto", () => {
  const dasarKotak = deklarasi(CSS, ".peta-pratinjau-foto {");
  const dasarTombol = deklarasi(CSS, ".peta-pratinjau-foto button {");

  test("kelasnya ada di index.css", () => {
    expect(dasarKotak).not.toBeNull();
    expect(dasarTombol).not.toBeNull();
  });

  test("SETIAP min-* dari aturan global dinetralkan ke 0", () => {
    // Diturunkan dari aturan globalnya, bukan didaftar manual: bila kelak
    // aturan 44px menambah properti min-* lain, uji ini langsung menagihnya.
    const global = deklarasi(blokLayarSempit("button, a {"), "button, a {");
    const minProps = Object.keys(global).filter((k) => k.startsWith("min-"));
    expect(minProps.length).toBeGreaterThan(0);
    minProps.forEach((p) => {
      expect(String(dasarTombol[p])).toBe("0");
    });
  });

  test("tombol jauh lebih kecil daripada fotonya", () => {
    const foto = px(dasarKotak.width);
    const tombol = px(dasarTombol.width);
    expect(foto).toBeGreaterThan(0);
    expect(tombol).toBeGreaterThan(0);
    // Inti keluhan: lingkaran merah menutupi foto. Sepertiga sisi foto berarti
    // ia hanya menempel di sudut.
    expect(tombol).toBeLessThanOrEqual(foto / 2.5);
  });

  test("tombol berbentuk lingkaran utuh (lebar = tinggi)", () => {
    expect(px(dasarTombol.width)).toBe(px(dasarTombol.height));
  });

  test("posisinya di sudut, hanya menjorok sedikit", () => {
    const tombol = px(dasarTombol.width);
    [dasarTombol.top, dasarTombol.right].forEach((v) => {
      // Menjorok keluar maksimal separuh diameter — lebih dari itu tombolnya
      // menggantung di luar popup dan bisa terpotong.
      expect(Math.abs(px(v))).toBeLessThanOrEqual(tombol / 2);
    });
  });
});

describe("pratinjau foto peta — layar sentuh (≤1023px)", () => {
  const isi = blokLayarSempit(".peta-pratinjau-foto");
  const kotak = isi && deklarasi(isi, ".peta-pratinjau-foto {");
  const tombol = isi && deklarasi(isi, ".peta-pratinjau-foto button {");

  test("ada penyesuaian khusus layar sentuh", () => {
    expect(isi).not.toBeNull();
    expect(kotak).not.toBeNull();
    expect(tombol).not.toBeNull();
  });

  test("min-* tetap dinetralkan DI DALAM media query", () => {
    // Aturan global berada di media query yang sama; menuliskannya kembali di
    // sini membuat penawarnya tak bergantung pada urutan berkas.
    expect(String(tombol["min-width"])).toBe("0");
    expect(String(tombol["min-height"])).toBe("0");
  });

  test("thumbnail diperbesar dibanding desktop", () => {
    const dasar = px(deklarasi(CSS, ".peta-pratinjau-foto {").width);
    expect(px(kotak.width)).toBeGreaterThan(dasar);
    expect(px(kotak.width)).toBe(px(kotak.height));
  });

  test("tombol cukup besar untuk jari, tapi tetap tak menutupi foto", () => {
    const t = px(tombol.width);
    expect(t).toBeGreaterThanOrEqual(20);   // jangan jadi titik yang mustahil ditekan
    expect(t).toBeLessThanOrEqual(px(kotak.width) / 2.5);
  });

  test("tombol TIDAK ikut membesar jadi 44px", () => {
    // Regresi persis yang dilaporkan dari lapangan.
    expect(px(tombol.width)).toBeLessThan(44);
    expect(px(tombol.height)).toBeLessThan(44);
  });
});

// ---------------------------------------------------------------------------
// Markup popup benar-benar memakai kelas itu
// ---------------------------------------------------------------------------

describe("AssetMapFullView — markup pratinjau", () => {
  const potong = () => {
    const at = JSX.indexOf("const gambarUlangPratinjau");
    expect(at).toBeGreaterThan(-1);
    return JSX.slice(at, at + 1600);
  };

  test("kotak pratinjau memakai kelas .peta-pratinjau-foto", () => {
    expect(potong()).toContain('className = "peta-pratinjau-foto"');
  });

  test("tombol hapus TIDAK diberi ukuran inline", () => {
    // Gaya inline tak sanggup menahan min-*; memakainya lagi = cacatnya pulih
    // sementara CSS-nya terlihat masih benar.
    const src = potong();
    const btn = src.slice(src.indexOf("<button"), src.indexOf("</button>"));
    expect(btn).not.toMatch(/style\s*=/);
    expect(btn).not.toMatch(/width\s*:/);
  });

  test("gambar pratinjau tak lagi menyetel ukuran inline", () => {
    const src = potong();
    const img = src.slice(src.indexOf("<img"), src.indexOf("/>"));
    expect(img).not.toMatch(/style\s*=/);
  });

  test("tombol hapus punya label yang terbaca pembaca layar", () => {
    expect(potong()).toMatch(/aria-label="Hapus foto/);
  });

  test("tombol hapus punya data-testid", () => {
    expect(potong()).toContain('data-testid="peta-tambah-hapus-foto"');
  });
});
