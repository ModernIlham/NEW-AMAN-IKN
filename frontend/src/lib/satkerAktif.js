// "Satker Aktif" (act-as-satker) untuk SUPER-ADMIN pusat.
//
// Super-admin (role admin + kode_satker kosong) tak terikat satker, sehingga
// data yang ia input tadinya distempel kode kosong = "era lama, terbuka" —
// menggantung tak jelas milik siapa dan mencampur antar satker. Dengan memilih
// Satker Aktif, header `X-Satker-Aktif` dikirim pada SETIAP request; backend
// menyuntikkan kode itu sehingga seluruh scoping & stempel berperilaku sebagai
// satker tersebut. Kosong = "Semua Satker" (lintas-satker seperti biasa).
//
// Disimpan di localStorage agar bertahan antar reload dan konsisten dipakai
// semua interceptor axios.

const KUNCI = "satker_aktif";
const EVT = "satker-aktif-berubah";

export function getSatkerAktif() {
  try {
    return localStorage.getItem(KUNCI) || "";
  } catch {
    return "";
  }
}

export function setSatkerAktif(kode) {
  try {
    if (kode) localStorage.setItem(KUNCI, kode);
    else localStorage.removeItem(KUNCI);
  } catch {
    /* localStorage tak tersedia (mode privat) — abaikan */
  }
  // Beri tahu pendengar (bar + refetch data) di tab yang sama.
  try {
    window.dispatchEvent(new CustomEvent(EVT, { detail: kode || "" }));
  } catch {
    /* SSR / lingkungan tanpa window */
  }
}

export const SATKER_AKTIF_EVENT = EVT;

/** Super-admin PUSAT = role admin DAN kode_satker kosong. Hanya mereka yang
 *  boleh memakai Satker Aktif (backend mengabaikan header untuk user lain). */
export function isSuperAdminPusat(user) {
  return (
    (user?.role === "admin" || user?.role === "super_admin") &&
    !String(user?.kode_satker || "").trim()
  );
}

/** Sisipkan header X-Satker-Aktif ke config axios bila ada nilai tersimpan. */
export function terapkanHeaderSatker(config) {
  const kode = getSatkerAktif();
  if (kode && config?.headers && !config.headers["X-Satker-Aktif"]) {
    config.headers["X-Satker-Aktif"] = kode;
  }
  return config;
}
