import { useCallback } from "react";
import axios from "axios";
import { editTertunda, perbaruiBaris } from "../lib/rekonsiliasiBaris";
import { upsertSnapshotAsset } from "../lib/offlineSnapshot";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function useRekonsiliasiBaris({ activityId, lingkupPermintaan, penjaga,
  setAssets, setMobileAssets, pendingItemsRef, editAssetRef, wsNeedsRefreshRef }) {
  const terapkanBaris = useCallback((fresh) => {
    if (!fresh?.id) return;
    const items = pendingItemsRef.current();
    if (fresh.activity_id && !editTertunda(items, fresh.id)) {
      upsertSnapshotAsset(fresh.activity_id, fresh);
    }
    setAssets(prev => perbaruiBaris(prev, fresh, items));
    setMobileAssets(prev => perbaruiBaris(prev, fresh, items));
  }, [setAssets, setMobileAssets, pendingItemsRef]);

  const muatBaris = useCallback(async (id, jagaForm = false) => {
    const tiket = penjaga.mulai(`baris:${id}`, lingkupPermintaan);
    if (!tiket) return;
    try {
      const { data: fresh } = await axios.get(`${API}/assets/${id}?exclude_media=true`);
      if (!penjaga.berlaku(tiket) || fresh?.id !== id
        || (fresh.activity_id && activityId && fresh.activity_id !== activityId)) return;
      // Form bisa baru dibuka SETELAH GET dimulai.
      if (jagaForm && editAssetRef.current?.id === id) {
        wsNeedsRefreshRef.current = true;
        return;
      }
      terapkanBaris(fresh);
    } catch { /* Jaringan putus / aset dihapus: muat ulang berikutnya merapikan. */ }
    finally { penjaga.selesai(tiket); }
  }, [activityId, lingkupPermintaan, penjaga, terapkanBaris, editAssetRef, wsNeedsRefreshRef]);

  return { terapkanBaris, muatBaris };
}
