/**
 * Lencana keberlakuan tidak boleh terpotong di tepi kolom status.
 *
 * Laporan pemilik (tangkapan layar): pada baris surat yang dibatalkan, lencana
 * "Tidak Berlaku" di sebelah "Dibatalkan" terpotong separuh.
 *
 * Sebabnya bukan ukuran lencananya — melainkan selnya `whitespace-nowrap`
 * sementara kedua lencana adalah elemen INLINE. Keduanya terpaksa berada di
 * satu baris yang tak boleh patah, jadi yang kedua meluber keluar kolom.
 * `mt-0.5` pada lencana kedua memperlihatkan bahwa penulisnya memang
 * membayangkan keduanya bertumpuk — margin itu tak pernah terlihat karena
 * elemennya tak pernah turun baris.
 *
 * Dipindai dari sumber: merender PersuratanPage berarti menghidupkan dialog,
 * unduhan, dan pemanggilan jaringan hanya untuk memeriksa tata letak dua
 * lencana; dan jsdom tidak menghitung tata letak sehingga uji render pun tak
 * bisa membuktikan "terpotong".
 */
import fs from "fs";
import path from "path";

const SUMBER = fs.readFileSync(
  path.join(__dirname, "..", "PersuratanPage.jsx"), "utf8");

/** Potong blok JSX sel status pada tabel desktop. */
function selStatus() {
  const kunci = "WARNA_STATUS[s.status]";
  const i = SUMBER.indexOf("<td", SUMBER.lastIndexOf("<td", SUMBER.indexOf(kunci, SUMBER.indexOf("</thead>"))));
  const j = SUMBER.indexOf("</td>", i);
  expect(i).toBeGreaterThan(-1);
  return SUMBER.slice(i, j);
}

describe("sel status tabel desktop", () => {
  test("sel tidak lagi mengunci seluruh isinya dalam satu baris", () => {
    expect(selStatus()).not.toContain('<td className="px-3 py-2 whitespace-nowrap"');
  });

  test("lencana ditumpuk, bukan dijajarkan", () => {
    expect(selStatus()).toContain("flex flex-col");
  });

  test("tiap lencana tetap utuh — teksnya sendiri tak boleh patah", () => {
    // "Tidak Berlaku" patah jadi dua baris sama buruknya dengan terpotong.
    const sel = selStatus();
    const lencana = sel.match(/rounded-full text-\[10px\]/g) || [];
    const nowrap = sel.match(/whitespace-nowrap px-2 py-0\.5 rounded-full/g) || [];
    expect(lencana.length).toBeGreaterThanOrEqual(2);
    expect(nowrap.length).toBe(lencana.length);
  });
});

describe("kartu HP", () => {
  test("lencana boleh turun baris alih-alih menggencet lencana agenda", () => {
    const i = SUMBER.indexOf("persuratan-cards-mobile");
    const blok = SUMBER.slice(i, i + 2000);
    expect(blok).toContain("flex flex-wrap items-center justify-end gap-1");
  });
});
