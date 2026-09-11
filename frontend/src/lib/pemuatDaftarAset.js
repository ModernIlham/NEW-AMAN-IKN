import axios from "axios";
import { toast } from "sonner";
import { getSnapshotAssets, snapshotMeta, isSnapshotExpired } from "@/lib/offlineSnapshot";
import { statistikUntukKartu } from "@/lib/statistikAset";
import { HASIL_USANG } from "@/hooks/usePenjagaPermintaan";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Jalur yang sama dipakai Dashboard dan uji urutan respons. Konteks adalah
// satu render; penjaga menolak seluruh hasilnya begitu lingkup berubah.
export function buatPemuatDaftarAset(konteks) {
  const {
    activity, filters, isOnlineRef, getPendingItems, serverHasPendingRow,
    filterSnapshotRows, sortSnapshotRows, buildFilterParams,
    mobileLoading, mobileCurrentPage, mobileFirstPage, totalPages, pageSize,
    debouncedSearch, filterCategory, sortBy, penjaga, lingkupPermintaan,
    setAssets, setTotalItems, setTotalPages, setCurrentPage, setStats,
    setMobileAssets, setMobileCurrentPage, setMobileFirstPage, setMobileLoading,
    setOfflineLastSync, setOfflineServed, setLoadingMessage,
  } = konteks;
  // === DATA FETCHING ===
  // OFFLINE READ PATH: serve the list from the local snapshot (filter/sort/
  // paginate client-side). Mengembalikan baris/false/HASIL_USANG. TTL >7 hari
  // diperlakukan seperti tidak ada snapshot (pesan kedaluwarsa).
  const serveFromSnapshot = async (tiket, page, size, search, category, sort, appendMobile = false, prependMobile = false, preserveMobile = false) => {
    if (!penjaga.berlaku(tiket)) return HASIL_USANG;
    if (!activity?.id) return false;
    try {
      const rows = await getSnapshotAssets(activity.id);
      if (!penjaga.berlaku(tiket)) return HASIL_USANG;
      // Seluruh await SEBELUM commit layar: metadata lambat tidak boleh
      // meninggalkan daftar separuh baru dan banner dari permintaan lama.
      const meta = await snapshotMeta(activity.id);
      if (!penjaga.berlaku(tiket)) return HASIL_USANG;
      if (!rows) {
        if (isSnapshotExpired(meta)) {
          toast.error("Data offline kedaluwarsa, hubungkan internet untuk sinkron ulang", { id: "snapshot-expired", duration: 6000 });
        }
        return false;
      }
      const filtered = sortSnapshotRows(filterSnapshotRows(rows, { search, category, filters }), sort);
      const totalFiltered = filtered.length;
      const totalPg = Math.max(1, Math.ceil(totalFiltered / size));
      const pg = Math.max(1, Math.min(page, totalPg));
      const pageItems = filtered.slice((pg - 1) * size, pg * size);
      // Unsynced offline CREATEs live only in the save queue — merge them on
      // page 1 exactly like doFetch does after a live refetch.
      const pendingRows = pg === 1 ? getPendingItems()
        .filter(it => !it.isEdit && it.payload && it.payload.activity_id === activity?.id)
        .map(it => ({ ...it.payload, id: it.tempId, thumbnail: it.payload.photo || null, created_at: it.queuedAt || new Date().toISOString() }))
        .filter(row => !pageItems.some(a => serverHasPendingRow(a, row))) : [];
      const merged = pendingRows.length ? [...pendingRows, ...pageItems] : pageItems;
      // Statistik daring yang berangkat sebelum snapshot ini sudah usang.
      penjaga.batalkan("statistik");
      setAssets(merged);
      setTotalItems(totalFiltered);
      setTotalPages(totalPg);
      setCurrentPage(pg);
      // Kartu ringkasan dihitung dari BARIS TERSARING yang sama dengan daftar
      // ini, bukan ditinggal memakai angka daring terakhir. Dihitung atas
      // `filtered` (bukan `merged`) supaya Total Aset selalu sama dengan
      // `totalFiltered` yang baru saja dipasang di atas.
      setStats(statistikUntukKartu(filtered));
      if (prependMobile) {
        setMobileAssets(prev => [...pageItems, ...prev]);   // PREPEND (scroll-atas dua arah)
        setMobileFirstPage(pg);
      } else if (appendMobile && pg > 1) {
        setMobileAssets(prev => [...prev, ...pageItems]);
        setMobileCurrentPage(pg);
      } else if (!preserveMobile) {
        setMobileAssets(merged);
        setMobileCurrentPage(pg);
        setMobileFirstPage(pg);
      }
      setOfflineLastSync(meta?.lastSync || null);
      setOfflineServed(true);
      setLoadingMessage(`Mode offline — menampilkan ${merged.length} dari ${totalFiltered} aset tersimpan`);
      // Kembalikan baris halaman ini (append: hanya slice baru) agar pemanggil
      // seperti loadMoreMobile bisa membuka aset pertama halaman berikutnya
      // (alur simpan-lanjut lintas halaman). Array truthy → pemeriksaan
      // `if (served)` di pemanggil lama tetap benar.
      return prependMobile ? pageItems : (appendMobile && pg > 1) ? pageItems : merged;
    } catch {
      return penjaga.berlaku(tiket) ? false : HASIL_USANG;
    }
  };

  const doFetch = async (page, size, search, category, sort, appendMobile = false, preserveMobile = false) => {
    const tiket = penjaga.mulai("daftar", lingkupPermintaan);
    if (!tiket) return HASIL_USANG;
    const jendela = !preserveMobile ? penjaga.mulai("jendela", lingkupPermintaan) : null;
    if (!preserveMobile) {
      penjaga.batalkan("mobile");
      setMobileLoading(false);
    }
    try {
      // Offline: don't wait for a network timeout — serve the snapshot directly.
      if (!isOnlineRef.current) {
        const served = await serveFromSnapshot(tiket, page, size, search, category, sort, appendMobile, false, preserveMobile);
        if (!penjaga.berlaku(tiket)) return HASIL_USANG;
        if (served) return served;
      }
      try {
        setLoadingMessage(`Memuat halaman ${page}...`);
        // Clamp memakai tiket dan preserveMobile yang SAMA; bukan rekursi
        // yang merebut prioritas dari permintaan pengguna yang lebih baru.
        let r;
        while (true) {
          const params = new URLSearchParams();
          if (search) params.append("search", search);
          params.append("sort_by", sort || "newest");
          params.append("page", String(page));
          params.append("page_size", String(size));
          if (activity?.id) params.append("activity_id", activity.id);
          buildFilterParams(params);
          r = await axios.get(`${API}/assets?${params.toString()}`);
          if (!penjaga.berlaku(tiket)) return HASIL_USANG;
          // Halaman di luar rentang (mis. baris terakhir baru dihapus) → mundur ke
          // halaman terakhir yang berisi data alih-alih menampilkan layar kosong.
          const totalPagesResp = r.data.total_pages || 1;
          if ((r.data.total || 0) > 0 && !(r.data.items || []).length && page > totalPagesResp) {
            page = totalPagesResp;
            continue;
          }
          break;
        }
        const newItems = r.data.items || [];
        // Keep unsynced CREATE rows visible: a refetch replaces the list, but
        // rows still waiting in the save queue don't exist on the server yet.
        const pendingRows = getPendingItems()
          .filter(it => !it.isEdit && it.payload && it.payload.activity_id === activity?.id)
          .map(it => ({ ...it.payload, id: it.tempId, thumbnail: it.payload.photo || null, created_at: it.queuedAt || new Date().toISOString() }))
          .filter(row => !newItems.some(a => serverHasPendingRow(a, row)));
        const merged = pendingRows.length ? [...pendingRows, ...newItems] : newItems;
        setAssets(merged);
        setTotalItems(r.data.total || 0);
        setTotalPages(r.data.total_pages || 1);
        setCurrentPage(r.data.page || 1);
        if (appendMobile && page > 1) {
          setMobileAssets(prev => [...prev, ...newItems]);
        } else if (!preserveMobile) {
          // Jendela galeri = [P, P]: JANGAN reset ke 1. Bila pindah dari halaman
          // tabel (mis. hal. 5) lalu ke galeri, jendela mulai di 5 sehingga
          // scroll-atas dapat memuat 4,3,2,1 (dua arah) dan scroll-bawah 6,7…
          setMobileAssets(merged);
          setMobileCurrentPage(r.data.page || 1);
          setMobileFirstPage(r.data.page || 1);
        }
        // preserveMobile: sengaja TIDAK menyentuh mobileAssets/halaman galeri —
        // jendela infinite-scroll + posisi scroll HP tetap; baris yang baru
        // disimpan sudah diperbarui optimis + via onRowSynced.
        setOfflineServed(false); // live data on screen again
        setLoadingMessage(`Berhasil memuat ${newItems.length} dari ${r.data.total || 0} aset`);
        // Kembalikan baris halaman ini agar pemanggil (goToPage → alur simpan-
        // lanjut lintas halaman mode list/tabel) bisa membuka aset pertamanya.
        return merged;
      } catch {
        if (!penjaga.berlaku(tiket)) return HASIL_USANG;
        // Network failed (offline / server unreachable) → fall back to snapshot
        const served = await serveFromSnapshot(tiket, page, size, search, category, sort, appendMobile, false, preserveMobile);
        if (!penjaga.berlaku(tiket)) return HASIL_USANG;
        if (served) return Array.isArray(served) ? served : null;
        if (!served) {
          const meta = await snapshotMeta(activity?.id);
          if (!penjaga.berlaku(tiket)) return HASIL_USANG;
          if (isSnapshotExpired(meta)) {
            // serveFromSnapshot already toasted "Data offline kedaluwarsa…"
            setLoadingMessage("Data offline kedaluwarsa — hubungkan internet untuk sinkron ulang");
          } else if (!isOnlineRef.current || !navigator.onLine) {
            // Offline with no snapshot yet — actionable message, not a generic error
            toast.error("Anda sedang offline dan belum ada data tersimpan untuk kegiatan ini. Aktifkan Mode Inventarisasi saat online untuk menyiapkan data offline.", { id: "offline-no-snapshot", duration: 7000 });
            setLoadingMessage("Mode offline — data tersimpan belum tersedia");
          } else {
            toast.error("Gagal memuat data");
          }
        }
      }
    } finally { penjaga.selesai(tiket); penjaga.selesai(jendela); }
  };

  // Mengembalikan array baris yang baru dimuat (halaman berikutnya) atau null
  // bila tak ada lagi/ gagal — dipakai alur simpan-lanjut lintas halaman untuk
  // membuka aset pertama halaman baru.
  const loadMoreMobile = async () => {
    if (mobileLoading || penjaga.sibuk("jendela")) return HASIL_USANG;
    const tiket = penjaga.mulai("mobile", lingkupPermintaan, true);
    if (!tiket) return HASIL_USANG;
    if (mobileCurrentPage >= totalPages) { penjaga.selesai(tiket); return null; }
    setMobileLoading(true);
    const nextPage = mobileCurrentPage + 1;
    try {
      // Offline: append the next page straight from the snapshot
      if (!isOnlineRef.current) {
        const served = await serveFromSnapshot(tiket, nextPage, pageSize, debouncedSearch, filterCategory, sortBy, true);
        if (!penjaga.berlaku(tiket)) return HASIL_USANG;
        if (served) return served;
      }
      try {
        const params = new URLSearchParams();
        if (debouncedSearch) params.append("search", debouncedSearch);
        params.append("sort_by", sortBy || "newest");
        params.append("page", String(nextPage));
        params.append("page_size", String(pageSize));
        if (activity?.id) params.append("activity_id", activity.id);
        buildFilterParams(params);
        const r = await axios.get(`${API}/assets?${params.toString()}`);
        if (!penjaga.berlaku(tiket)) return HASIL_USANG;
        const items = r.data.items || [];
        setMobileAssets(prev => [...prev, ...items]);
        setMobileCurrentPage(nextPage);
        return items;
      } catch {
        if (!penjaga.berlaku(tiket)) return HASIL_USANG;
        const served = await serveFromSnapshot(tiket, nextPage, pageSize, debouncedSearch, filterCategory, sortBy, true);
        if (!penjaga.berlaku(tiket)) return HASIL_USANG;
        if (!served) toast.error("Gagal memuat data lanjutan");
        return Array.isArray(served) ? served : null;
      }
    } finally { if (penjaga.selesai(tiket)) setMobileLoading(false); }
  };

  // Muat halaman SEBELUMNYA (scroll ke atas di galeri) — cermin loadMoreMobile,
  // tetapi PREPEND agar urutan global & filter tetap terjaga. Tiket eksklusif
  // menyerialkan terhadap loadMore sehingga sentinel atas & bawah tak
  // saling memicu bersamaan. Mengembalikan baris baru (untuk anchor scroll).
  const loadPrevMobile = async () => {
    if (mobileLoading || penjaga.sibuk("jendela")) return HASIL_USANG;
    const tiket = penjaga.mulai("mobile", lingkupPermintaan, true);
    if (!tiket) return HASIL_USANG;
    if (mobileFirstPage <= 1) { penjaga.selesai(tiket); return null; }
    setMobileLoading(true);
    const prevPage = mobileFirstPage - 1;
    try {
      if (!isOnlineRef.current) {
        const served = await serveFromSnapshot(tiket, prevPage, pageSize, debouncedSearch, filterCategory, sortBy, false, true);
        if (!penjaga.berlaku(tiket)) return HASIL_USANG;
        if (served) return served;
      }
      try {
        const params = new URLSearchParams();
        if (debouncedSearch) params.append("search", debouncedSearch);
        params.append("sort_by", sortBy || "newest");
        params.append("page", String(prevPage));
        params.append("page_size", String(pageSize));
        if (activity?.id) params.append("activity_id", activity.id);
        buildFilterParams(params);
        const r = await axios.get(`${API}/assets?${params.toString()}`);
        if (!penjaga.berlaku(tiket)) return HASIL_USANG;
        const items = r.data.items || [];
        setMobileAssets(prev => [...items, ...prev]);   // PREPEND
        setMobileFirstPage(prevPage);
        return items;
      } catch {
        if (!penjaga.berlaku(tiket)) return HASIL_USANG;
        const served = await serveFromSnapshot(tiket, prevPage, pageSize, debouncedSearch, filterCategory, sortBy, false, true);
        if (!penjaga.berlaku(tiket)) return HASIL_USANG;
        if (!served) toast.error("Gagal memuat data sebelumnya");
        return Array.isArray(served) ? served : null;
      }
    } finally { if (penjaga.selesai(tiket)) setMobileLoading(false); }
  };

  const doFetchStats = async (search) => {
    const tiket = penjaga.mulai("statistik", lingkupPermintaan);
    if (!tiket) return HASIL_USANG;
    try {
      if (!isOnlineRef.current) return;
      const params = new URLSearchParams();
      if (search) params.append("search", search);
      if (activity?.id) params.append("activity_id", activity.id);
      // Filter lanjutan ikut dikirim — perakit yang SAMA dengan daftar
      // (`buildFilterParams`). Sebelum ini kartu ringkasan hanya menerima
      // cari/kategori/kegiatan, sehingga memilih "Kondisi: Rusak Berat"
      // menyusutkan daftarnya tetapi Total Aset di atasnya tetap menyebut
      // angka seluruh kegiatan.
      buildFilterParams(params);
      const r = await axios.get(`${API}/assets/stats?${params.toString()}`);
      if (!penjaga.berlaku(tiket)) return HASIL_USANG;
      setStats({ totalAssets: r.data.total_assets||0, totalValue: (r.data.total_value||0).toLocaleString('id-ID'), activeCount: r.data.active_count||0, maintenanceCount: r.data.maintenance_count||0 });
    } catch {
      if (!penjaga.berlaku(tiket)) return HASIL_USANG;
    } finally { penjaga.selesai(tiket); }
  };

  return { doFetch, doFetchStats, loadMoreMobile, loadPrevMobile };
}
