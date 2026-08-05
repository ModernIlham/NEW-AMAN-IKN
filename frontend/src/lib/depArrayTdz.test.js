/**
 * Penjaga: dependency array hook TAK BOLEH merujuk const yang dideklarasikan
 * di bawahnya.
 *
 * KENAPA UJI INI ADA. Peta Aset pernah mati total di produksi dengan
 * "ReferenceError: Cannot access 'Xt' before initialization" — sebuah useEffect
 * mencantumkan `refreshRowVersion` di dependency array-nya, padahal
 * `const refreshRowVersion = useCallback(...)` baru dideklarasikan ~500 baris
 * di bawah. Isi dependency array dievaluasi SAAT BADAN KOMPONEN BERJALAN
 * (bukan nanti saat efeknya dijalankan), jadi ini kena Temporal Dead Zone:
 * komponennya melempar sebelum sempat me-render satu piksel pun.
 *
 * Kenapa tak tertangkap sebelumnya:
 *   - `yarn build` sukses — ini galat RUNTIME, bukan galat sintaks.
 *   - eslint CRA menyetel `no-use-before-define` dengan `variables: false`,
 *     jadi rule bawaannya diam.
 *   - tak ada uji render komponen di repo ini (47 suite semuanya logika murni).
 * Tiga pagar terlewat sekaligus, dan yang menemukannya adalah pemakai.
 *
 * Rujukan di dalam BADAN callback (mis. `load()` dipanggil di dalam useEffect
 * yang ditulis sebelum `const load`) bukan masalah — badan itu baru jalan
 * setelah seluruh komponen selesai dievaluasi. Yang dijaga di sini HANYA
 * dependency array, yaitu satu-satunya bentuk yang benar-benar fatal.
 */

const fs = require("fs");
const path = require("path");

const AKAR = path.join(__dirname, "..");

/** Kata kunci & nilai yang tak mungkin jadi rujukan variabel lokal. */
const BUKAN_RUJUKAN = new Set(["true", "false", "null", "undefined", "typeof", "void"]);

/** Jumlah spasi di depan sebuah baris. */
function indentasi(t) {
  return /^(\s*)/.exec(t)[1].replace(/\t/g, "  ").length;
}

/**
 * Nomor "blok tingkat atas" tiap baris — naik tiap kali file memulai deklarasi
 * baru di kolom 0 (function/const/export). Dipakai sebagai pendekatan LINGKUP:
 * `const kataKata` milik komponen B tak boleh dianggap membayangi pemakaian
 * nama yang sama di komponen A, sekalipun kebetulan berada di file yang sama.
 */
function blokTingkatAtas(baris) {
  let blok = 0;
  return baris.map((t) => {
    if (/^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class)\s/.test(t)
      || /^(?:export\s+)?(?:const|let|var)\s/.test(t)) blok += 1;
    return blok;
  });
}

/**
 * Cari identifier di dependency array hook yang deklarasinya berada di baris
 * LEBIH BAWAH daripada pemakaiannya, DI LINGKUP YANG SAMA.
 *
 * Dua penyaring lingkup — keduanya diperlukan agar tak melapor palsu:
 *   1. blok tingkat atas sama (bukan komponen lain di file yang sama);
 *   2. indentasi deklarasi <= indentasi hook (deklarasi yang lebih menjorok
 *      berada di dalam callback lain, jadi bukan lingkup yang membayangi).
 *
 * @param {string} sumber isi file
 * @returns {{baris: number, nama: string, deklarasi: number}[]}
 */
function cariDepArrayTdz(sumber) {
  const baris = sumber.split("\n");
  const blok = blokTingkatAtas(baris);

  // nama → daftar {baris, indent, blok} deklarasi const/let/var, termasuk
  // destructuring array (`const [a, setA] = useState()`) dan objek.
  const deklarasi = new Map();
  baris.forEach((t, i) => {
    const m = /^\s*(?:const|let|var)\s+(\[[^\]]*\]|\{[^}]*\}|[A-Za-z_$][\w$]*)/.exec(t);
    if (!m) return;
    const nama = m[1].replace(/^[[{]|[\]}]$/g, "");
    for (const bagian of nama.split(",")) {
      // `{ a: b }` → yang mengikat adalah `b`; `a = 1` → `a`.
      const id = bagian.split(":").pop().split("=")[0].trim();
      if (!/^[A-Za-z_$][\w$]*$/.test(id)) continue;
      if (!deklarasi.has(id)) deklarasi.set(id, []);
      deklarasi.get(id).push({ baris: i + 1, indent: indentasi(t), blok: blok[i] });
    }
  });

  const temuan = [];
  baris.forEach((t, i) => {
    // Dua bentuk yang sama-sama fatal:
    //   `}, [a, b]);`                                   (hook multi-baris)
    //   `useEffect(() => { pakai(); }, [a, b]);`        (hook satu baris)
    const m = /,\s*\[([^[\]]*)\]\s*\)\s*;?\s*$/.exec(t);
    if (!m) return;
    const penutupHook = /^\s*[}\])],/.test(t);
    const hookSebaris = /\buse[A-Z][\w$]*\s*\(/.test(t);
    if (!penutupHook && !hookSebaris) return;

    const indentHook = indentasi(t);
    // Buang akses properti (`a.b` → hanya `a` yang dirujuk sebagai variabel).
    for (const tok of m[1].split(/[^\w$.]+/)) {
      if (!tok) continue;
      const nama = tok.split(".")[0];
      if (!/^[A-Za-z_$][\w$]*$/.test(nama) || BUKAN_RUJUKAN.has(nama)) continue;
      // Tak ditemukan = impor/props/global → tak ada TDZ, lewati.
      const d = (deklarasi.get(nama) || []).find(
        (x) => x.blok === blok[i] && x.indent <= indentHook);
      if (d && d.baris > i + 1) temuan.push({ baris: i + 1, nama, deklarasi: d.baris });
    }
  });
  return temuan;
}

/** Semua .js/.jsx di src, kecuali file uji. */
function berkasSumber(dir = AKAR, hasil = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) berkasSumber(p, hasil);
    else if (/\.jsx?$/.test(e.name) && !/\.test\.jsx?$/.test(e.name)) hasil.push(p);
  }
  return hasil;
}

describe("cariDepArrayTdz (pendeteksinya sendiri)", () => {
  test("menangkap rujukan dependency array ke const di bawahnya", () => {
    const buruk = [
      "function C() {",
      "  useEffect(() => { pakai(); }, [aktivitas, muatUlang]);",
      "  const muatUlang = useCallback(() => {}, []);",
      "}",
    ].join("\n");
    const t = cariDepArrayTdz(buruk);
    expect(t).toHaveLength(1);
    expect(t[0]).toMatchObject({ nama: "muatUlang", baris: 2, deklarasi: 3 });
  });

  test("deklarasi di ATAS pemakaian tidak dilaporkan", () => {
    const baik = [
      "function C() {",
      "  const muatUlang = useCallback(() => {}, []);",
      "  useEffect(() => { pakai(); }, [aktivitas, muatUlang]);",
      "}",
    ].join("\n");
    expect(cariDepArrayTdz(baik)).toEqual([]);
  });

  test("panggilan di dalam BADAN callback bukan temuan — itu memang sah", () => {
    // Ini pola yang dipakai di banyak halaman: efek ditulis di atas, fungsinya
    // di bawah. Badan efek baru jalan setelah komponen selesai dievaluasi.
    const sah = [
      "function C() {",
      "  useEffect(() => { muat(); }, []);",
      "  const muat = () => {};",
      "}",
    ].join("\n");
    expect(cariDepArrayTdz(sah)).toEqual([]);
  });

  test("mengurai destructuring useState dan menyebut nama setter-nya juga", () => {
    const buruk = [
      "function C() {",
      "  useEffect(() => {}, [versi]);",
      "  const [versi, setVersi] = useState(0);",
      "}",
    ].join("\n");
    expect(cariDepArrayTdz(buruk).map((x) => x.nama)).toEqual(["versi"]);
  });

  test("nama sama milik komponen LAIN di file yang sama bukan temuan", () => {
    // Ini positif palsu yang nyata: HalamanGalat.jsx punya `kataKata` sebagai
    // parameter di satu fungsi dan `const kataKata` di komponen berikutnya.
    const sah = [
      "function useA(kataKata) {",
      "  useEffect(() => {}, [kataKata]);",
      "}",
      "function B() {",
      "  const kataKata = useMemo(() => [], []);",
      "  return kataKata;",
      "}",
    ].join("\n");
    expect(cariDepArrayTdz(sah)).toEqual([]);
  });

  test("deklarasi yang lebih menjorok (di dalam callback lain) bukan temuan", () => {
    const sah = [
      "function C() {",
      "  useEffect(() => {}, [nilai]);",
      "  function lain() {",
      "    const nilai = 1;",
      "    return nilai;",
      "  }",
      "}",
    ].join("\n");
    expect(cariDepArrayTdz(sah)).toEqual([]);
  });

  test("hook yang menjorok tetap kena bila const komponen ada di bawahnya", () => {
    const buruk = [
      "function C() {",
      "  if (x) {",
      "    useEffect(() => {}, [ambil]);",
      "  }",
      "  const ambil = useCallback(() => {}, []);",
      "}",
    ].join("\n");
    expect(cariDepArrayTdz(buruk).map((x) => x.nama)).toEqual(["ambil"]);
  });
});

describe("seluruh src bebas TDZ dependency array", () => {
  test("tak ada satu pun hook merujuk const yang dideklarasikan di bawahnya", () => {
    const temuan = [];
    for (const f of berkasSumber()) {
      for (const t of cariDepArrayTdz(fs.readFileSync(f, "utf8"))) {
        temuan.push(
          `${path.relative(AKAR, f)}:${t.baris} → '${t.nama}' `
          + `dideklarasikan di baris ${t.deklarasi}`);
      }
    }
    // Pesan galatnya sengaja memuat daftar lengkapnya: yang memperbaiki nanti
    // butuh tahu berkas & baris persisnya, bukan sekadar "0 !== 1".
    expect(temuan).toEqual([]);
  });
});
