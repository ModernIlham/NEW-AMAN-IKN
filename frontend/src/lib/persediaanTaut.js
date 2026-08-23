/**
 * Tautan baris pengadaan → barang persediaan yang SUDAH TERDAFTAR.
 *
 * CERMIN `backend/persediaan_pengadaan.py`, bukan penggantinya. Server tetap
 * yang memutuskan (dan menolak 400 bila tautannya tak masuk akal); yang hidup
 * di sini hanya keputusan-keputusan yang harus terjadi SEBELUM tombol simpan
 * ditekan — memilih, melepas, dan memperingatkan — supaya operator tak
 * mengetahui kesalahannya lewat pesan galat.
 *
 * Semua fungsi MURNI: tanpa React, tanpa jaringan. Itu yang membuat aturan
 * "kapan tautan gugur" bisa diuji tanpa merender halaman.
 */

/** Golongan barang = digit pertama kode (kodefikasi BMN). '' bila kosong. */
export function golonganKode(kode) {
  const k = String(kode ?? "").trim();
  return k && k[0] >= "0" && k[0] <= "9" ? k[0] : "";
}

/** Baris ini bermuara ke kartu stok persediaan (golongan 1)? */
export function barisPersediaan(kode) {
  return golonganKode(kode) === "1";
}

/**
 * Baris setelah operator MEMILIH barang persediaan terdaftar.
 *
 * Kode baris mengadopsi kode master (16 digit), bukan sebaliknya: LPB, BAST,
 * dan kartu stok harus mencetak kode yang sama persis. Uraian hanya diisi
 * bila masih kosong — nama di BAST kadang memang lebih panjang daripada nama
 * di master, dan menimpanya berarti mengarang isi dokumen sumber.
 */
export function barisSetelahPilihPersediaan(baris, master) {
  const kode = String(master?.kode_barang ?? "").trim();
  const nama = String(master?.nama_barang ?? "").trim();
  return {
    ...baris,
    kode,
    uraian: String(baris?.uraian ?? "").trim() ? baris.uraian : nama,
    psd_master_id: String(master?.id ?? ""),
    psd_master_kode: kode,
    psd_master_nama: nama,
  };
}

/** Baris setelah tautannya DILEPAS — kode dibiarkan apa adanya. */
export function barisTanpaTautPersediaan(baris) {
  return { ...baris, psd_master_id: "", psd_master_kode: "", psd_master_nama: "" };
}

/**
 * Baris setelah kolom kode DIKETIK ULANG.
 *
 * Tautan GUGUR begitu kodenya menunjuk barang lain — kalau tidak, operator
 * bisa memilih "Kertas HVS A4", lalu mengetik kode tinta di kolom kode, dan
 * stok tinta mendarat di kartu kertas tanpa satu pun peringatan. Kode 10
 * digit yang masih menjadi awalan kode master TIDAK menggugurkan tautan: itu
 * barang yang sama, hanya ditulis sampai level kodefikasinya.
 */
export function barisSetelahUbahKode(baris, kodeBaru) {
  const k = String(kodeBaru ?? "").trim();
  const terkait = String(baris?.psd_master_kode ?? "").trim();
  const cocok = terkait && (k === terkait || (k.length === 10 && terkait.startsWith(k)));
  const dasar = { ...baris, kode: kodeBaru };
  return cocok ? dasar : barisTanpaTautPersediaan(dasar);
}

/**
 * Baris persediaan mana yang masternya masih akan DITEBAK server?
 *
 * → [{index, kode, uraian}] — dipakai panel peringatan di form. Baris yang
 * sudah tercatat (psd_item_id) atau sudah jadi aset tak pernah diposting
 * ulang, jadi tak perlu diperingatkan.
 */
export function peringatanPersediaanForm(barang) {
  const keluar = [];
  (barang || []).forEach((b, index) => {
    const kode = String(b?.kode ?? "").trim();
    if (!barisPersediaan(kode)) return;
    if (String(b?.psd_item_id ?? "").trim()) return;
    if (String(b?.asset_id ?? "").trim()) return;
    if (String(b?.psd_master_id ?? "").trim()) return;
    keluar.push({
      index,
      kode,
      uraian: String(b?.uraian ?? "").trim() || "(tanpa uraian)",
      kodePendek: kode.length < 16,
    });
  });
  return keluar;
}
