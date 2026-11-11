/**
 * Pembaca sumber (PGW-08; rencana 3.8 & 7.3): ikon kelompok tampil di layar
 * yang terdaftar, tidak pernah di naskah/persuratan, dan gambarnya satu
 * sumber.
 */
import fs from "fs";
import path from "path";
import { LARANGAN_IKON, PERMUKAAN_IKON, PERMUKAAN_IKON_MENYUSUL } from "../kelompokOrang";

const SRC = path.resolve(__dirname, "../..");
const baca = (rel) => fs.readFileSync(path.join(SRC, rel), "utf8");
const mengimpor = (teks) => /import\s+IkonKelompok\s+from\s+["'][^"']*IkonKelompok["']/.test(teks);

function semuaBerkas(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    const p = path.join(dir, d.name);
    if (d.isDirectory()) return d.name === "__tests__" ? [] : semuaBerkas(p);
    return /\.(jsx?|tsx?)$/.test(d.name) && !/\.test\./.test(d.name) ? [p] : [];
  });
}
const relatif = (p) => path.relative(SRC, p).split(path.sep).join("/");

test("tiap berkas PERMUKAAN_IKON ada dan mengimpor IkonKelompok", () => {
  for (const rel of PERMUKAAN_IKON) {
    expect(fs.existsSync(path.join(SRC, rel))).toBe(true);
    expect([rel, mengimpor(baca(rel))]).toEqual([rel, true]);
  }
});

test("layar yang menyusul (PGW-08b/11) tercatat dan berkasnya ada", () => {
  for (const rel of PERMUKAAN_IKON_MENYUSUL) {
    expect([rel, fs.existsSync(path.join(SRC, rel))]).toEqual([rel, true]);
    expect(PERMUKAAN_IKON).not.toContain(rel);
  }
});

test("tak satu pun berkas LARANGAN_IKON mengimpor IkonKelompok", () => {
  const berkas = semuaBerkas(SRC).map(relatif);
  const terlarang = berkas.filter((rel) => LARANGAN_IKON.some((l) => (l.endsWith("/")
    ? rel.startsWith(l) : rel === l)));
  expect(terlarang.length).toBeGreaterThan(2);
  for (const rel of terlarang) expect([rel, mengimpor(baca(rel))]).toEqual([rel, false]);
});

test("hanya kelompokOrang.js yang memetakan kelompok ke gambar ikon", () => {
  const pelanggar = semuaBerkas(SRC).map(relatif).filter((rel) => {
    if (rel === "lib/kelompokOrang.js") return false;
    const t = baca(rel);
    return /ikonKelompok\.json/.test(t)
      || /pihak_ketiga["']?\s*:\s*(Handshake|Landmark|MapPinned|IdCard)\b/.test(t)
      || /eksternal(_pusat|_daerah)?["']?\s*:\s*(Handshake|Landmark|MapPinned|IdCard)\b/.test(t);
  });
  expect(pelanggar).toEqual([]);
});

test("ikonKelompok.json sama byte demi byte dengan backend/data/ikon_kelompok.json", () => {
  const fe = fs.readFileSync(path.join(SRC, "lib/ikonKelompok.json"));
  const be = fs.readFileSync(path.resolve(SRC, "../../backend/data/ikon_kelompok.json"));
  expect(fe.equals(be)).toBe(true);
});
