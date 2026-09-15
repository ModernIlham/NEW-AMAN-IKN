// Invalidation lintas layar/tab; tidak menyimpan salinan master atau data akun.
export const REFERENSI_SATKER_EVENT = "referensi-satker-berubah";
export function kabarkanPerubahanSatker() {
  window.dispatchEvent(new Event(REFERENSI_SATKER_EVENT));
  try { localStorage.setItem(REFERENSI_SATKER_EVENT, `${Date.now()}-${Math.random()}`); }
  catch { /* mode privat: tab ini tetap menerima event */ }
}
