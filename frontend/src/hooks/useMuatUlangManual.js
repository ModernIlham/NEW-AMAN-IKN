import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

/** Muat ulang hanya dari tindakan eksplisit, tanpa mengambil alih gestur. */
export function useMuatUlangManual(refreshData) {
  const [refreshing, setRefreshing] = useState(false);
  const sibuk = useRef(false);
  const terpasang = useRef(false);
  useEffect(() => {
    terpasang.current = true;
    return () => { terpasang.current = false; };
  }, []);
  const onRefreshData = useCallback(async () => {
    if (sibuk.current || !terpasang.current) return;
    sibuk.current = true;
    setRefreshing(true);
    try {
      // Pertahankan halaman/filter/urutan, tetapi ganti baris daftar HP juga.
      // preserveMobile hanya cocok untuk rekonsiliasi simpan optimistis:
      // opsi itu sengaja tidak memperbarui baris mobile dari respons server.
      await refreshData(undefined);
    } catch {
      if (terpasang.current) toast.error("Data belum dapat dimuat ulang. Silakan coba lagi.");
    } finally {
      sibuk.current = false;
      if (terpasang.current) setRefreshing(false);
    }
  }, [refreshData]);
  return { refreshing, onRefreshData };
}
