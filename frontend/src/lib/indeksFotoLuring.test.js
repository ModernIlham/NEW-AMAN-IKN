import { keIndeksFinal } from "./indeksFotoLuring";

// Skenario lapangan yang dijaga: edit LURING aset ber-3-foto-server, strip
// hanya menampilkan foto BARU di posisi 0. Backend menyusun final =
// [3 foto lama] + [foto baru], jadi foto baru itu sebenarnya indeks 3.
// Menyimpan indeks strip mentah membuat sampul/foto-stiker menunjuk foto lama
// yang bahkan tidak terlihat di layar.

describe("keIndeksFinal", () => {
  test("LURING: indeks strip digeser sejumlah foto server yang tak terlihat", () => {
    expect(keIndeksFinal(0, false, 3)).toBe(3);
    expect(keIndeksFinal(1, false, 3)).toBe(4);
  });

  test("DARING: media dimuat → tanpa geser (perilaku lama utuh)", () => {
    expect(keIndeksFinal(0, true, 3)).toBe(0);
    expect(keIndeksFinal(2, true, 3)).toBe(2);
  });

  test("mode CREATE / tanpa data server → tanpa geser", () => {
    expect(keIndeksFinal(1, false, undefined)).toBe(1);
    expect(keIndeksFinal(1, false, null)).toBe(1);
    expect(keIndeksFinal(1, false, 0)).toBe(1);
  });

  test("cacah server tak sah tidak membuat NaN atau geser negatif", () => {
    expect(keIndeksFinal(2, false, "bukan-angka")).toBe(2);
    expect(keIndeksFinal(2, false, -5)).toBe(2);
  });
});
