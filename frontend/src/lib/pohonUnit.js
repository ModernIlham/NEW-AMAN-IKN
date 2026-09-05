/**
 * Perataan pohon unit organisasi (Eselon I–V) menjadi daftar yang dapat
 * ditampilkan — MURNI, tanpa React dan tanpa jaringan.
 *
 * Master unit datang dari server sebagai daftar RATA berisi `parent_id`.
 * Menampilkannya apa adanya membuat "Bagian Rumah Tangga" berdiri sejajar
 * dengan "Sekretariat Jenderal", padahal yang satu ada di dalam yang lain —
 * dan pemilih lingkup kegiatan justru menuntut hubungan itu terbaca, sebab
 * memilih satu unit berarti ikut memilih seluruh keturunannya.
 *
 * Tiga keputusan yang membentuk berkas ini:
 *
 * 1. **Urutannya urutan pohon, bukan urutan datang.** Induk selalu mendahului
 *    anaknya, saudara diurutkan menurut nama. Daftar yang berpindah susunan
 *    setiap kali dimuat ulang membuat pengguna kehilangan tempatnya.
 *
 * 2. **Unit yatim tetap ditampilkan, di akhir.** `parent_id` yang menunjuk
 *    unit terhapus membuat cabangnya tak terjangkau dari puncak mana pun.
 *    Menyembunyikannya berarti unit yang ada di basis data tak dapat dipilih
 *    dan tak dapat diperbaiki — hilang tanpa satu pun tanda.
 *
 * 3. **Penelusuran dibatasi.** Data pohon yang melingkar tak boleh membekukan
 *    tab peramban; simpul yang sudah dikunjungi tak pernah dikunjungi ulang.
 */

const PEMISAH = " / ";

/** Daftar rata berurut pohon: `[{...unit, depth, jalur}]`. */
export function susunPohonUnit(units) {
  const daftar = (units || []).filter((u) => u && u.id);
  const anakDari = new Map();
  const dikenal = new Set(daftar.map((u) => u.id));
  daftar.forEach((u) => {
    // Induk yang tak dikenal diperlakukan sama dengan tanpa induk: unitnya
    // tetap muncul, hanya saja sebagai akar.
    const kunci = u.parent_id && dikenal.has(u.parent_id) ? u.parent_id : "";
    if (!anakDari.has(kunci)) anakDari.set(kunci, []);
    anakDari.get(kunci).push(u);
  });
  anakDari.forEach((arr) => arr.sort((a, b) => {
    const ea = String(a.eselon || ""), eb = String(b.eselon || "");
    if (ea !== eb) return ea < eb ? -1 : 1;
    return String(a.nama_unit || "").localeCompare(String(b.nama_unit || ""));
  }));

  const keluar = [];
  const dikunjungi = new Set();
  const turun = (indukId, depth, jalurInduk) => {
    for (const u of anakDari.get(indukId) || []) {
      if (dikunjungi.has(u.id)) continue;      // pohon melingkar
      dikunjungi.add(u.id);
      const nama = String(u.nama_unit || "").trim();
      const jalur = jalurInduk ? `${jalurInduk}${PEMISAH}${nama}` : nama;
      keluar.push({ ...u, depth, jalur });
      turun(u.id, depth + 1, jalur);
    }
  };
  turun("", 0, "");

  // Sisa yang tak terjangkau dari akar mana pun (cabang melingkar).
  daftar.filter((u) => !dikunjungi.has(u.id)).forEach((u) => {
    keluar.push({ ...u, depth: 0, jalur: String(u.nama_unit || "").trim() });
  });
  return keluar;
}

/** Jalur satu unit, atau id-nya apa adanya bila tak dikenal. */
export function jalurUnit(id, pohon) {
  const u = (pohon || []).find((x) => x.id === id);
  return u ? u.jalur : String(id || "");
}

/**
 * Ringkasan lingkup untuk ditampilkan: berapa unit, dan jalurnya.
 *
 * Id yang TIDAK ada pada pohon tetap dihitung dan ditandai. Lingkup adalah
 * penyaring; id mati tidak menyaring apa pun, dan menyembunyikannya membuat
 * kegiatan yang dikira terbatas diam-diam menampilkan seluruh satker.
 */
export function ringkasLingkup(ids, pohon) {
  const daftar = (ids || []).filter(Boolean);
  const dikenal = new Set((pohon || []).map((u) => u.id));
  return {
    jumlah: daftar.length,
    jalur: daftar.map((i) => jalurUnit(i, pohon)),
    tak_dikenal: daftar.filter((i) => !dikenal.has(i)),
  };
}

/** Peta id → induk, dari daftar unit apa adanya. */
function petaInduk(pohon) {
  const m = new Map();
  (pohon || []).forEach((u) => { if (u && u.id) m.set(u.id, u.parent_id || ""); });
  return m;
}

/** Rantai leluhur satu unit, dari terjauh ke induk langsung. */
function rantaiInduk(id, peta) {
  const naik = [];
  const terlihat = new Set([id]);
  let kini = peta.get(id) || "";
  while (kini && !terlihat.has(kini) && naik.length < 16) {
    naik.push(kini);
    terlihat.add(kini);
    kini = peta.get(kini) || "";
  }
  return naik.reverse();
}

/**
 * Unit yang boleh dipilih untuk sebuah kegiatan.
 *
 * Lingkup KOSONG berarti seluruhnya — kegiatan yang belum mencatat lingkup tak
 * boleh mendadak kehilangan seluruh pilihannya. Unit lingkup mencakup dirinya
 * sendiri DAN seluruh keturunannya: mencatat "Biro Umum" sebagai lingkup
 * berarti Bagian dan Subbagian di bawahnya ikut dapat dipilih, sebab itulah
 * arti membawahi. Cerminan `organisasi_utils.dalam_lingkup` di sisi server.
 */
export function unitDalamLingkup(pohon, lingkupIds) {
  const lingkup = new Set((lingkupIds || []).filter(Boolean));
  if (lingkup.size === 0) return pohon || [];
  const peta = petaInduk(pohon);
  return (pohon || []).filter((u) => lingkup.has(u.id)
    || rantaiInduk(u.id, peta).some((i) => lingkup.has(i)));
}

/**
 * `{eselon1..eselon5}` untuk satu unit — label tiap tingkat pada rantainya.
 *
 * Aset menyimpan unitnya sebagai lima kolom teks; ini yang mengisinya dari
 * satu pilihan. Tingkat yang tak ada pada rantai dikembalikan sebagai string
 * KOSONG, bukan dihilangkan: mengosongkan kolom itulah yang menghapus sisa
 * unit sebelumnya saat pengguna memindahkan aset ke cabang yang lebih dangkal.
 */
export function fieldEselon(unitId, pohon) {
  const keluar = { eselon1: "", eselon2: "", eselon3: "", eselon4: "", eselon5: "" };
  if (!unitId) return keluar;
  const byId = new Map((pohon || []).map((u) => [u.id, u]));
  const peta = petaInduk(pohon);
  [...rantaiInduk(unitId, peta), unitId].forEach((i) => {
    const u = byId.get(i);
    const lv = parseInt(String(u?.eselon || ""), 10);
    if (u && lv >= 1 && lv <= 5) keluar[`eselon${lv}`] = String(u.nama_unit || "").trim();
  });
  return keluar;
}

/**
 * Unit yang cocok dengan lima kolom eselon sebuah aset — untuk mengembalikan
 * pilihan saat form dibuka lagi.
 *
 * Dicocokkan pada unit TERDALAM yang tercatat beserta seluruh jalurnya, bukan
 * pada namanya saja: dua Bagian Tata Usaha di bawah dua Biro berbeda adalah
 * dua unit berlainan. Tak ada yang cocok → "" , dan formnya menampilkan apa
 * yang tercatat apa adanya alih-alih diam-diam memilih unit yang keliru.
 */
export function unitDariField(data, pohon) {
  const nama = (n) => String((data || {})[`eselon${n}`] || "").trim();
  let terdalam = 0;
  for (let n = 1; n <= 5; n += 1) if (nama(n)) terdalam = n;
  if (!terdalam) return "";
  const cocok = (pohon || []).filter((u) => {
    if (parseInt(String(u.eselon || ""), 10) !== terdalam) return false;
    const f = fieldEselon(u.id, pohon);
    for (let n = 1; n <= terdalam; n += 1) {
      if (String(f[`eselon${n}`] || "") !== nama(n)) return false;
    }
    return true;
  });
  return cocok.length === 1 ? cocok[0].id : "";
}

/**
 * Perubahan massal lima kolom eselon untuk satu unit terpilih.
 *
 * Bedanya dengan `fieldEselon`: tingkat yang TIDAK dipakai unit terpilih
 * ditandai `"__clear__"`, bukan string kosong. Ubah massal hanya menuliskan
 * kunci yang dikirimnya, jadi string kosong pun harus dinyatakan sebagai
 * perintah kosongkan — kalau tidak, aset yang dipindahkan dari Subbagian ke
 * Biro tetap membawa `eselon3` lamanya, dan baris itu terbaca sebagai unit
 * yang tak pernah ada di sana.
 */
export function perubahanEselonMassal(unitId, pohon) {
  if (!unitId) return {};
  const f = fieldEselon(unitId, pohon);
  const keluar = {};
  for (let n = 1; n <= 5; n += 1) {
    const k = `eselon${n}`;
    keluar[k] = f[k] || "__clear__";
  }
  return keluar;
}

/**
 * Nama unit TERDALAM yang tercatat pada sebuah aset/pegawai (Eselon V → I).
 *
 * Tampilan sempit hanya punya ruang untuk satu nama, dan yang benar adalah
 * yang TERDALAM: aset sebuah Subbagian yang ditampilkan sebagai Bironya
 * menyebut unit yang bukan pemegangnya. Cerminan
 * `organisasi_utils.unit_terdalam` di sisi server.
 */
export function unitTerdalam(data) {
  for (let n = 5; n >= 1; n -= 1) {
    const v = String((data || {})[`eselon${n}`] || "").trim();
    if (v) return v;
  }
  return "";
}

/**
 * Jalur unit aset sebagai satu teks: `"Setjen / Biro Umum / Bagian RT"`.
 *
 * `maks` membatasi berapa tingkat TERDALAM yang ikut ditulis — ruang di kartu
 * memang terbatas. Yang dipotong adalah bagian AWAL, bukan akhir: yang paling
 * menjelaskan letak barang adalah unit terdalamnya, sedangkan Eselon I sama
 * untuk hampir semua aset satker dan karenanya paling sedikit membedakan.
 * Pemotongannya ditandai "…" supaya tak terbaca sebagai jalur yang utuh.
 */
export function jalurEselon(data, maks = 5) {
  const bagian = [];
  for (let n = 1; n <= 5; n += 1) {
    const v = String((data || {})[`eselon${n}`] || "").trim();
    if (v) bagian.push(v);
  }
  if (bagian.length <= maks) return bagian.join(" / ");
  return `… / ${bagian.slice(bagian.length - maks).join(" / ")}`;
}
