import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Penanda "sudah disinkronkan" LINTAS-TAMPILAN (galeri ↔ list ↔ kartu HP):
// komponen di-mount ulang saat berganti mode tampilan sehingga state lokal
// hilang, sedangkan data daftar belum tentu langsung dimuat ulang — tanpa
// penanda ini aset yang baru disinkronkan di list masih menampilkan ikon
// sinkronisasi ketika pindah ke galeri. Kunci menyertakan import_id SIMAN:
// impor baru otomatis membatalkan penanda lama (selisih baru tampil lagi).
const sudahSinkron = new Set();

/**
 * useSinkronSiman — sinkronisasi SIMAN V2 langsung dari kartu/baris daftar:
 * terapkan seluruh field selisih (kecuali kode barang — jalur reklasifikasi
 * terpisah di Penatausahaan › Pelaporan). Dipakai kartu galeri, kartu HP,
 * dan baris tabel desktop agar perilakunya identik.
 * - `synced`  : aset ini sudah disinkronkan (termasuk dari tampilan lain /
 *               sebelum berganti mode) → sembunyikan penanda selisih.
 * - `baruSaja`: sinkron terjadi DI KOMPONEN INI → mainkan animasi sukses
 *               sekali saja (tidak diputar ulang tiap mount).
 */
export function useSinkronSiman(asset) {
  const kunci = `${asset.id}|${asset.siman?.import_id || ""}`;
  const [busy, setBusy] = useState(false);
  const [synced, setSynced] = useState(() => sudahSinkron.has(kunci));
  const [baruSaja, setBaruSaja] = useState(false);
  useEffect(() => {
    setSynced(sudahSinkron.has(kunci));
    setBaruSaja(false);
  }, [kunci]);
  const sinkron = useCallback(async (e) => {
    e?.stopPropagation?.();
    const fields = (asset.siman?.selisih || [])
      .map((sel) => sel.field).filter((f) => f !== "asset_code");
    if (!fields.length) {
      toast.info("Selisih tersisa hanya kode barang — sinkronkan lewat Penatausahaan › Pelaporan (reklasifikasi)");
      return;
    }
    setBusy(true);
    try {
      await axios.post(`${API}/siman/terapkan/${asset.id}`, { fields });
      sudahSinkron.add(kunci);
      setSynced(true);
      setBaruSaja(true);
      toast.success(`${asset.asset_code} tersinkron dengan SIMAN V2`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal sinkron dengan SIMAN");
    } finally {
      setBusy(false);
    }
  }, [asset.id, asset.asset_code, asset.siman, kunci]);
  return { busy, synced, baruSaja, sinkron };
}
