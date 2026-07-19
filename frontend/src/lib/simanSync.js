import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Penanda "sudah TUNTAS disinkronkan" LINTAS-TAMPILAN (galeri ↔ list ↔
// kartu HP): komponen di-mount ulang saat berganti mode tampilan sehingga
// state lokal hilang, sedangkan data daftar belum tentu langsung dimuat
// ulang. Kunci menyertakan import_id SIMAN: impor baru otomatis membatalkan
// penanda lama. HANYA diisi bila server menyatakan selisih habis
// (sisa_selisih = 0) — sinkron parsial (kode barang tersisa → wajib jalur
// reklasifikasi) TIDAK menyembunyikan penanda selisih di tampilan mana pun.
const sudahSinkron = new Set();
// Pub-sub kecil: instance hook lain (termasuk yang baru mount ketika
// request masih berjalan — mis. pengguna berpindah mode saat menunggu)
// ikut diperbarui begitu sebuah sinkron tuntas.
const pendengar = new Set();
const umumkan = () => pendengar.forEach((fn) => fn());

/**
 * useSinkronSiman — sinkronisasi SIMAN V2 langsung dari kartu/baris daftar:
 * terapkan seluruh field selisih (kecuali kode barang — jalur reklasifikasi
 * terpisah di Penatausahaan › Pelaporan). Dipakai kartu galeri, kartu HP,
 * dan baris tabel desktop agar perilakunya identik.
 * - `synced`  : selisih aset TUNTAS disinkronkan (termasuk dari tampilan
 *               lain / sebelum berganti mode) → sembunyikan penanda.
 * - `baruSaja`: sinkron tuntas terjadi DI KOMPONEN INI → mainkan animasi
 *               sukses sekali saja (tidak diputar ulang tiap mount).
 */
export function useSinkronSiman(asset) {
  const kunci = `${asset.id}|${asset.siman?.import_id || ""}`;
  const [busy, setBusy] = useState(false);
  const [synced, setSynced] = useState(() => sudahSinkron.has(kunci));
  const [baruSaja, setBaruSaja] = useState(false);
  useEffect(() => {
    const segarkan = () => setSynced(sudahSinkron.has(kunci));
    segarkan();
    setBaruSaja(false);
    pendengar.add(segarkan);
    return () => pendengar.delete(segarkan);
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
      const r = await axios.post(`${API}/siman/terapkan/${asset.id}`, { fields });
      if ((r?.data?.sisa_selisih || 0) > 0) {
        // Parsial: field lain sudah diterapkan tetapi selisih kode barang
        // tersisa — penanda selisih SENGAJA tetap tampil di semua tampilan
        // karena reklasifikasi masih harus dikerjakan.
        toast.warning(
          `${asset.asset_code}: ${fields.length} field diterapkan — selisih KODE BARANG tersisa, sinkronkan lewat reklasifikasi (Penatausahaan › Pelaporan)`);
        return;
      }
      sudahSinkron.add(kunci);
      setSynced(true);
      setBaruSaja(true);
      umumkan();
      toast.success(`${asset.asset_code} tersinkron dengan SIMAN V2`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal sinkron dengan SIMAN");
    } finally {
      setBusy(false);
    }
  }, [asset.id, asset.asset_code, asset.siman, kunci]);
  return { busy, synced, baruSaja, sinkron };
}
