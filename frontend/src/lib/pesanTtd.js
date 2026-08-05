/**
 * Penyusun pesan permintaan tanda tangan (WA & email).
 *
 * Mandat pemilik: pesan lama hanya berisi judul + tautan, sehingga penerima
 * harus MEMBUKA tautan dulu sekadar untuk tahu dokumen apa itu — dan setelah
 * berbulan-bulan tak ada jejak yang bisa dicari di riwayat percakapannya
 * ("dokumen mana yang dulu saya tanda tangani?"). Kini pesan membawa nomor,
 * perihal, barang (kode + NUP + nama), dan para pihak.
 *
 * Dipakai BERSAMA oleh halaman Tanda Tangan Elektronik dan dialog "Kirim TTD"
 * di Penggunaan — supaya keduanya tak pernah berisi keterangan yang berbeda
 * untuk permintaan yang sama.
 *
 * `ringkas` berasal dari server (dibekukan saat permintaan dibuat) dan bisa
 * kosong — mis. dokumen unggahan bebas yang memang tak punya BAST rujukan.
 * Bentuk pesannya menyusut dengan sendirinya bila datanya tak ada.
 */

const MAKS_BARIS_BARANG = 3;

/**
 * Peluru daftar — KARAKTER sungguhan, bukan sintaks penanda.
 *
 * Jangan diganti "* " atau "- ": WhatsApp memperlakukan awalan itu sebagai
 * perintah daftar (dan "*teks*" sebagai tebal), sehingga tandanya bisa hilang,
 * berubah, atau justru tercetak mentah. Pesan yang sama juga dikirim lewat
 * `mailto:` yang tak mengenal penanda sama sekali — di sana asterisknya akan
 * terbaca apa adanya. Satu bentuk untuk dua kanal: karakter biasa.
 */
const PELURU = "• ";

/**
 * Bentuk state "hasil kirim TTD" dari respons server — SATU pintu untuk semua
 * halaman yang memanggil `.../kirim-ttd`.
 *
 * KENAPA HELPER INI ADA. Layar Riwayat BAST dulu menyusun sendiri
 * `{ judul, links }` dari respons, sehingga `ringkas` (nomor, tanggal, barang,
 * pihak — yang dibekukan server) IKUT TERBUANG. Akibatnya pesan WA dari sana
 * hanya berisi perihal + tautan, sementara pesan dari halaman Tanda Tangan
 * Elektronik lengkap — dua pesan berbeda untuk permintaan yang sama.
 *
 * Kesalahannya tak terlihat: tak ada galat, tombolnya jalan, pesannya cuma
 * lebih pendek. Karena itu penyalinannya dipusatkan di sini dan diuji.
 */
export function hasilTtd(data, judulBawaan = "Dokumen") {
  const d = data || {};
  return {
    id: d.id || "",
    judul: d.judul || judulBawaan,
    links: Array.isArray(d.links) ? d.links : [],
    // `ringkas` WAJIB ikut — inilah isi keterangan pesan WA/email.
    ringkas: d.ringkas || null,
  };
}

/** Baris "Kode / NUP — Nama" untuk satu barang. */
function barisBarang(b) {
  const kiri = [b?.kode, b?.nup ? `NUP ${b.nup}` : ""].filter(Boolean).join(" / ");
  return [kiri, b?.nama].filter(Boolean).join(" — ");
}

/**
 * Rangkaian baris keterangan dokumen (tanpa sapaan & tautan).
 *
 * BENTUKNYA DIRAPIKAN karena versi lama tak selamat di layar penerima.
 * Dulu label diratakan dengan spasi ganjal (`Nomor    : `) dan baris kedua
 * daftar disambung dengan indentasi 11 spasi. Keduanya mengandaikan font
 * monospace dan spasi yang dipertahankan — dua hal yang tidak berlaku di
 * WhatsApp: fontnya proporsional sehingga label tak pernah sejajar, dan spasi
 * beruntun diciutkan sehingga baris barang ke-2 dan ke-3 kehilangan induknya,
 * menggantung tanpa keterangan apa pun.
 *
 * Sekarang: tanpa ganjalan, tanpa indentasi, tiap daftar diberi judul sendiri,
 * dan tiap butir diawali peluru sungguhan. Bentuk yang sama terbaca benar di
 * WhatsApp maupun email.
 */
export function barisKeterangan(judul, ringkas) {
  const r = ringkas || {};

  const identitas = [];
  if (r.nomor) identitas.push(`Nomor: ${r.nomor}`);
  const perihal = r.perihal || judul;
  if (perihal) identitas.push(`Perihal: ${perihal}`);
  if (r.tanggal) identitas.push(`Tanggal: ${r.tanggal}`);

  const barang = Array.isArray(r.barang) ? r.barang : [];
  const total = Number(r.jumlah_barang || barang.length) || 0;
  const tampil = barang.slice(0, MAKS_BARIS_BARANG).map(barisBarang).filter(Boolean);
  const daftarBarang = [];
  if (tampil.length) {
    // Jumlah totalnya di JUDUL daftar, bukan hanya tersirat dari "(+N lainnya)"
    // — penerima langsung tahu ia meneken berapa unit.
    daftarBarang.push(total ? `Barang (${total} unit):` : "Barang:");
    tampil.forEach((t) => daftarBarang.push(`${PELURU}${t}`));
    const sisa = total - tampil.length;
    if (sisa > 0) daftarBarang.push(`${PELURU}(+${sisa} barang lainnya)`);
  } else if (total) {
    daftarBarang.push(`Barang: ${total} unit`);
  }

  const pihak = Array.isArray(r.pihak) ? r.pihak.filter(Boolean) : [];
  const daftarPihak = pihak.length
    ? ["Pihak:", ...pihak.map((p) => `${PELURU}${p}`)]
    : [];

  // Kelompok yang ADA dipisah satu baris kosong; kelompok kosong tak
  // meninggalkan baris kosong menggantung.
  return [identitas, daftarBarang, daftarPihak]
    .filter((g) => g.length)
    .reduce((semua, g) => (semua.length ? [...semua, "", ...g] : [...g]), []);
}

/** Pesan lengkap untuk WA/email. */
export function pesanTtd(nama, judul, link, ringkas) {
  const ket = barisKeterangan(judul, ringkas);
  const blokKet = ket.length ? `\n${ket.join("\n")}\n` : "";
  // Nama kosong (data lama / penanda tangan tanpa nama) tak boleh menghasilkan
  // sapaan buntung "Yth. ,".
  const sapaan = String(nama || "").trim() || "Bapak/Ibu";
  return (
    `Yth. ${sapaan},\n\n` +
    `Mohon berkenan menandatangani dokumen berikut secara elektronik:\n` +
    blokKet +
    `\nTautan tanda tangan (berlaku 14 hari, sekali pakai):\n${link}\n\n` +
    `Simpan pesan ini sebagai catatan dokumen yang Anda tandatangani.\n` +
    `Terima kasih.`
  );
}

/** Judul/subjek email. */
export function subjekTtd(judul, ringkas) {
  const nomor = (ringkas || {}).nomor;
  return `Permintaan Tanda Tangan Elektronik — ${nomor ? `${judul} (${nomor})` : judul}`;
}

export function bagikanWa(nama, judul, link, ringkas) {
  window.open(
    `https://wa.me/?text=${encodeURIComponent(pesanTtd(nama, judul, link, ringkas))}`,
    "_blank", "noopener");
}

export function bagikanEmail(nama, judul, link, ringkas) {
  window.location.href =
    `mailto:?subject=${encodeURIComponent(subjekTtd(judul, ringkas))}` +
    `&body=${encodeURIComponent(pesanTtd(nama, judul, link, ringkas))}`;
}
