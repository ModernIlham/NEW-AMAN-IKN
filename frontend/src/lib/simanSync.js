import { useCallback, useState } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * useSinkronSiman — sinkronisasi SIMAN V2 langsung dari kartu/baris daftar:
 * terapkan seluruh field selisih (kecuali kode barang — jalur reklasifikasi
 * terpisah di Penatausahaan › Pelaporan). Dipakai kartu galeri, kartu HP,
 * dan baris tabel desktop agar perilakunya identik.
 * `synced` tetap true sampai data daftar dimuat ulang — penanda tidak
 * muncul kembali sebelum status selisih diperbarui dari server.
 */
export function useSinkronSiman(asset) {
  const [busy, setBusy] = useState(false);
  const [synced, setSynced] = useState(false);
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
      setSynced(true);
      toast.success(`${asset.asset_code} tersinkron dengan SIMAN V2`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal sinkron dengan SIMAN");
    } finally {
      setBusy(false);
    }
  }, [asset.id, asset.asset_code, asset.siman]);
  return { busy, synced, sinkron };
}
