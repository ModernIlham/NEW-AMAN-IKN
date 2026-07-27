// ID BARIS ANTREAN LURING — satu gerbong, satu aset.
//
// Setiap simpanan yang belum tersinkron dikunci oleh `statusKey`. Untuk aset
// BARU, statusKey = tempId. Kunci itu dipakai di TIGA tempat sekaligus:
//
//   - `failedItemsRef[statusKey]`      → payload yang akan di-replay
//   - IndexedDB `keyPath: "statusKey"` → salinan yang selamat dari reload/crash
//   - `syncStatuses[statusKey]`        → chip status di baris daftar
//
// Karena ketiganya adalah PETA berkunci, dua aset ber-tempId sama tidak bentrok
// dengan berisik — yang kedua DIAM-DIAM MENIMPA yang pertama. Foto beserta
// koordinat aset pertama lenyap tanpa pesan apa pun, dan baru ketahuan setelah
// sinyal pulih: jumlah aset di server lebih sedikit daripada yang difoto
// surveyor di lapangan.
//
// Implementasi lama `temp_${Date.now()}` punya DUA cara gagal:
//
//  1. Resolusi milidetik. Dua CREATE dalam satu milidetik yang sama menghasilkan
//     id identik.
//  2. **Jam dinding bisa MUNDUR.** Ini yang berbahaya di lapangan: `Date.now()`
//     bukan jam monotonik. Selama survei luring berjam-jam, HP menyinkronkan
//     waktu ke jaringan begitu sinyal sempat menyentuh — koreksi ke BELAKANG
//     beberapa detik sudah cukup membuat aset baru memakai id yang masih
//     dipegang aset lain di antrean. Antrean bertahan lintas reload (IndexedDB),
//     jadi jendela tabrakannya bukan satu milidetik, melainkan SEPANJANG UMUR
//     ANTREAN.
//
// Karena itu id di sini tidak pernah bergantung pada jam untuk keunikannya.
// Stempel waktu tetap disertakan, tetapi HANYA supaya id enak dibaca manusia
// saat menelusuri antrean; keunikan dijamin oleh UUID acak, atau — bila
// peramban lawas tak punya crypto — oleh (garam sesi acak + penghitung monoton).

const AWALAN = "temp_";

// Garam per-SESI: dimint sekali saat modul dimuat. Ini yang memisahkan antrean
// sebelum-reload dari sesudah-reload, sehingga penghitung yang kembali ke 0
// tidak menabrak id lama yang masih tersimpan di IndexedDB.
const GARAM_SESI = acakBase36(8);

let penghitung = 0;

function acakBase36(panjang) {
  try {
    const c = typeof crypto !== "undefined" ? crypto : null;
    if (c && c.getRandomValues) {
      const buf = new Uint32Array(2);
      c.getRandomValues(buf);
      return (buf[0].toString(36) + buf[1].toString(36)).slice(0, panjang).padEnd(panjang, "0");
    }
  } catch { /* jatuh ke Math.random di bawah */ }
  let s = "";
  while (s.length < panjang) s += Math.random().toString(36).slice(2);
  return s.slice(0, panjang);
}

/**
 * ID sementara untuk satu baris antrean simpan. Dijamin berbeda dari SEMUA id
 * lain yang pernah dibuat perangkat ini — termasuk saat jam mundur dan saat
 * dipanggil berkali-kali dalam milidetik yang sama.
 *
 * Awalan `temp_` WAJIB dipertahankan: beberapa tempat membedakan baris yang
 * masih dalam antrean dari aset nyata lewat awalan ini (lihat apakahTempId).
 */
export function buatTempId() {
  return idUnik(AWALAN);
}

/**
 * ID unik berawalan bebas — inti keunikan yang sama dengan buatTempId, dipakai
 * ulang oleh antrean lain yang menghadapi jam-mundur yang persis sama (mis.
 * `scan_id` opname). Keunikannya TIDAK pernah bersandar pada jam.
 */
export function idUnik(awalan = "") {
  penghitung += 1;
  let unik;
  try {
    unik = typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `${GARAM_SESI}${penghitung.toString(36)}${acakBase36(6)}`;
  } catch {
    unik = `${GARAM_SESI}${penghitung.toString(36)}${acakBase36(6)}`;
  }
  // Stempel waktu di DEPAN supaya urutan pembuatan terbaca saat menelusuri
  // antrean — tetapi keunikan TIDAK bergantung padanya.
  return `${awalan}${Date.now().toString(36)}_${unik}`;
}

/** Baris ini masih di antrean (belum punya id nyata dari server)? */
export function apakahTempId(id) {
  return typeof id === "string" && id.startsWith(AWALAN);
}

export default buatTempId;
