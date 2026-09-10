import { useLayoutEffect, useRef } from "react";

// Berbeda dari halaman kosong/gagal: pemanggil tidak boleh menutup form atau
// mengumumkan sukses ketika hasilnya sudah digantikan permintaan lain.
export const HASIL_USANG = Symbol("hasil-permintaan-usang");

/** Tiket per kanal, hanya untuk lingkup render yang sudah di-commit. */
export function buatPenjagaPermintaan() {
  let lingkup;
  let generasi = 0;
  let aktif = false;
  const kanal = new Map();
  return {
    aktifkan(kunci) { lingkup = kunci; aktif = true; generasi++; kanal.clear(); },
    tutup() { aktif = false; generasi++; kanal.clear(); },
    mulai(nama, kunci, eksklusif = false) {
      if (!aktif || kunci !== lingkup || (eksklusif && kanal.has(nama))) return null;
      const tiket = { nama, generasi };
      kanal.set(nama, tiket);
      return tiket;
    },
    berlaku(tiket) {
      return !!tiket && aktif && tiket.generasi === generasi && kanal.get(tiket.nama) === tiket;
    },
    batalkan(nama) { kanal.delete(nama); },
    sibuk(nama) { return kanal.has(nama); },
    selesai(tiket) {
      if (!this.berlaku(tiket)) return false;
      kanal.delete(tiket.nama);
      return true;
    },
  };
}

export function usePenjagaPermintaan(lingkup) {
  const ref = useRef(null);
  if (!ref.current) ref.current = buatPenjagaPermintaan();
  useLayoutEffect(() => {
    const penjaga = ref.current;
    penjaga.aktifkan(lingkup);
    return () => penjaga.tutup();
  }, [lingkup]);
  return ref.current;
}
