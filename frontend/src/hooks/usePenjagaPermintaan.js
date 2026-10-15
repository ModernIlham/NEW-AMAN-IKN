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
  const batalkan = (nama) => {
    kanal.get(nama)?.controller?.abort();
    kanal.delete(nama);
  };
  const kosongkan = () => { for (const nama of kanal.keys()) batalkan(nama); };
  return {
    aktifkan(kunci) { kosongkan(); lingkup = kunci; aktif = true; generasi++; },
    tutup() { kosongkan(); aktif = false; generasi++; },
    mulai(nama, kunci, eksklusif = false) {
      if (!aktif || kunci !== lingkup || (eksklusif && kanal.has(nama))) return null;
      batalkan(nama);
      const tiket = { nama, generasi };
      kanal.set(nama, tiket);
      return tiket;
    },
    // Hanya READ diberi AbortController. Tiket mutasi tetap dipakai untuk
    // menjaga commit UI, tanpa mengira pembatalan HTTP membatalkan write server.
    mulaiBaca(nama, kunci, eksklusif = false) {
      const tiket = this.mulai(nama, kunci, eksklusif);
      if (!tiket) return null;
      tiket.controller = new AbortController();
      tiket.signal = tiket.controller.signal;
      return tiket;
    },
    berlaku(tiket) {
      return !!tiket && aktif && tiket.generasi === generasi && kanal.get(tiket.nama) === tiket;
    },
    batalkan,
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
