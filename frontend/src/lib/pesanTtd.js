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
 * Dipisah agar bisa dipakai ulang untuk pratinjau di layar.
 */
export function barisKeterangan(judul, ringkas) {
  const r = ringkas || {};
  const baris = [];
  if (r.nomor) baris.push(`Nomor    : ${r.nomor}`);
  const perihal = r.perihal || judul;
  if (perihal) baris.push(`Perihal  : ${perihal}`);
  if (r.tanggal) baris.push(`Tanggal  : ${r.tanggal}`);

  const barang = Array.isArray(r.barang) ? r.barang : [];
  if (barang.length) {
    const tampil = barang.slice(0, MAKS_BARIS_BARANG).map(barisBarang).filter(Boolean);
    const sisa = Number(r.jumlah_barang || barang.length) - tampil.length;
    tampil.forEach((t, i) => baris.push(`${i === 0 ? "Barang   : " : "           "}${t}`));
    if (sisa > 0) baris.push(`           (+${sisa} barang lainnya)`);
  } else if (r.jumlah_barang) {
    baris.push(`Barang   : ${r.jumlah_barang} unit`);
  }

  const pihak = Array.isArray(r.pihak) ? r.pihak.filter(Boolean) : [];
  if (pihak.length) {
    pihak.forEach((p, i) => baris.push(`${i === 0 ? "Pihak    : " : "           "}${p}`));
  }
  return baris;
}

/** Pesan lengkap untuk WA/email. */
export function pesanTtd(nama, judul, link, ringkas) {
  const ket = barisKeterangan(judul, ringkas);
  const blokKet = ket.length ? `\n${ket.join("\n")}\n` : "";
  return (
    `Yth. ${nama},\n\n` +
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
