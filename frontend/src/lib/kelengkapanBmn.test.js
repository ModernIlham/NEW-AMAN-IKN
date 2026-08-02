import { bangunChecklist, rekomendasiKelengkapan } from "./kelengkapanBmn";

describe("rekomendasiKelengkapan", () => {
  it("kode kosong = daftar KOSONG (0/0), bukan tebakan", () => {
    for (const k of ["", null, undefined, "   ", "abc"]) {
      expect(rekomendasiKelengkapan(k)).toEqual([]);
    }
  });

  it("golongan tak dikenal tidak dikarang-karang", () => {
    // '9' bukan golongan BMN; '1' = Persediaan (ditolak modul aset).
    expect(rekomendasiKelengkapan("9")).toEqual([]);
    expect(rekomendasiKelengkapan("1010301001")).toEqual([]);
  });

  it("tanah menuntut sertifikat, bukan kabel USB", () => {
    const r = rekomendasiKelengkapan("2010101001");
    expect(r).toContain("Sertifikat Hak Pakai/Hak Pengelolaan");
    expect(r).toContain("SPPT PBB Terakhir");
    expect(r.join(" ")).not.toMatch(/USB|Charger|CD Driver/i);
  });

  it("BIDANG mengalahkan GOLONGAN — kendaraan dapat BPKB/STNK", () => {
    const kendaraan = rekomendasiKelengkapan("3020104001"); // 302 = Alat Angkutan
    const mesinUmum = rekomendasiKelengkapan("3030101001"); // 303 = bidang lain
    expect(kendaraan).toContain("BPKB");
    expect(kendaraan).toContain("STNK");
    expect(kendaraan).toContain("Dongkrak & Kunci Roda");
    expect(mesinUmum).not.toContain("BPKB");
  });

  it("komputer dapat charger & lisensi; gedung dapat IMB", () => {
    expect(rekomendasiKelengkapan("3100102001")).toContain("Media/Lisensi Perangkat Lunak");
    expect(rekomendasiKelengkapan("4010101001")).toContain("IMB / PBG");
    expect(rekomendasiKelengkapan("4010101001")).toContain("Gambar Terbangun (As-Built Drawing)");
  });

  it("aset tak berwujud: seluruh buktinya dokumen, tanpa perlengkapan fisik", () => {
    const r = rekomendasiKelengkapan("8010101001");
    expect(r).toContain("Sertifikat/Bukti Lisensi");
    expect(r.join(" ")).not.toMatch(/Ban Cadangan|Dongkrak|Kunci Cadangan/i);
  });

  it("KDP belum jadi aset utuh — tak menagih BAST barang", () => {
    const r = rekomendasiKelengkapan("7010101001");
    expect(r).toContain("Laporan Kemajuan Pekerjaan");
    expect(r).not.toContain("Berita Acara Serah Terima (BAST)");
  });

  it("kode pendek (golongan/bidang saja) tetap terjawab", () => {
    expect(rekomendasiKelengkapan("2").length).toBeGreaterThan(0);
    expect(rekomendasiKelengkapan("302")).toContain("BPKB");
  });

  it("hasilnya salinan — pemanggil tak bisa merusak registry", () => {
    const a = rekomendasiKelengkapan("2");
    a.push("DISUSUPKAN");
    expect(rekomendasiKelengkapan("2")).not.toContain("DISUSUPKAN");
  });
});

describe("bangunChecklist", () => {
  const isi = (n, extra = {}) => ({
    name: n, checked: false, notes: "", photos: [], documents: [], ...extra,
  });

  it("baris baru lahir belum tercentang", () => {
    const r = bangunChecklist(["A", "B"]);
    expect(r).toHaveLength(2);
    expect(r[0]).toMatchObject({ name: "A", checked: false });
  });

  it("MEMPERTAHANKAN centang, catatan, foto, dan dokumen yang sudah ada", () => {
    const lama = [isi("BPKB", { checked: true, notes: "di brankas", photos: ["x"] })];
    const r = bangunChecklist(["BPKB", "STNK"], lama);
    expect(r[0]).toMatchObject({ name: "BPKB", checked: true, notes: "di brankas" });
    expect(r[0].photos).toEqual(["x"]);
    expect(r[1]).toMatchObject({ name: "STNK", checked: false });
  });

  it("baris tambahan buatan pengguna TIDAK dibuang saat kategori berubah", () => {
    // Bukti yang sudah diunggah petugas lapangan tak boleh lenyap hanya karena
    // kodefikasi aset dikoreksi.
    const lama = [isi("Kunci Gudang", { checked: true, documents: [{ name: "f.pdf" }] })];
    const r = bangunChecklist(["BPKB"], lama);
    expect(r.map((i) => i.name)).toEqual(["BPKB", "Kunci Gudang"]);
    expect(r[1].checked).toBe(true);
    expect(r[1].documents).toHaveLength(1);
  });

  it("daftar rekomendasi kosong = hanya baris pengguna yang tersisa", () => {
    const lama = [isi("Catatan Sendiri")];
    expect(bangunChecklist([], lama).map((i) => i.name)).toEqual(["Catatan Sendiri"]);
    expect(bangunChecklist([], [])).toEqual([]);
  });

  it("masukan tak wajar tidak meledak", () => {
    expect(bangunChecklist(null, null)).toEqual([]);
    expect(bangunChecklist(undefined)).toEqual([]);
  });
});
