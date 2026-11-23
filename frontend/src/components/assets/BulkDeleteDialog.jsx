import React, { memo, useState, useCallback, useEffect } from "react";
import { AlertTriangle, Trash2, Loader2 } from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../ui/dialog";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "../../lib/utils";
import { frasaKonfirmasiHapus, konfirmasiCocok } from "../../lib/konfirmasiHapus";
import OverlayProses from "../ui/OverlayProses";
import { jalankanHapusBerat, TENGGAT_HAPUS_BERAT } from "../../lib/prosesHapusBerat";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Hapus SELURUH aset satu kegiatan — permanen, termasuk foto & dokumen.
 *
 * Tinjauan mutu Nov 2026 (F8) membuktikan dialog lama berbahaya: ia
 * menampilkan jumlah aset TERFILTER (prop `totalItems`, mis. 248) sementara
 * endpoint menghapus SELURUH kegiatan (600), dan tombolnya bertooltip
 * "aset yang terfilter". Kini:
 *  - jumlah diambil dari server TANPA filter saat dialog dibuka;
 *  - bila filter/pencarian aktif, peringatan eksplisit bahwa filter TIDAK
 *    membatasi penghapusan;
 *  - konfirmasi dengan MENGETIK nama kegiatan (pola baku aksi destruktif);
 *  - jumlah yang dikonfirmasi dikirim sebagai `jumlah_konfirmasi`: server
 *    menolak (409) bila jumlah berubah sejak dialog dibuka.
 */
const BulkDeleteDialog = memo(({ open, onClose, activityId, activityName, totalItems, filterAktif = false, onSuccess }) => {
  const [deleting, setDeleting] = useState(false);
  const [jumlah, setJumlah] = useState(null);       // jumlah SEBENARNYA di server
  const [galatJumlah, setGalatJumlah] = useState("");
  const [ketikan, setKetikan] = useState("");
  const frasa = frasaKonfirmasiHapus(activityName);

  const muatJumlah = useCallback(async () => {
    if (!activityId) return;
    setJumlah(null);
    setGalatJumlah("");
    try {
      const r = await axios.get(`${API}/assets`, {
        params: { activity_id: activityId, page: 1, page_size: 1 },
        timeout: 15000,
      });
      setJumlah(Number(r.data?.total) || 0);
    } catch (err) {
      setGalatJumlah(getApiError(err, "Jumlah aset tidak dapat dimuat — periksa koneksi lalu coba lagi."));
    }
  }, [activityId]);

  // Setiap kali dialog dibuka: kosongkan ketikan & ambil jumlah terbaru.
  useEffect(() => {
    if (!open) return;
    setKetikan("");
    muatJumlah();
  }, [open, muatJumlah]);

  const siap = jumlah !== null && jumlah > 0 && konfirmasiCocok(ketikan, frasa) && !deleting;

  const handleDelete = useCallback(async () => {
    if (!activityId) { toast.error("Pilih kegiatan inventarisasi terlebih dahulu"); return; }
    if (!siap) return;
    setDeleting(true);
    try {
      const hasil = await jalankanHapusBerat(
        () => axios.delete(`${API}/assets/bulk-delete/${activityId}`, {
          params: { jumlah_konfirmasi: jumlah }, timeout: TENGGAT_HAPUS_BERAT,
        }),
        // Jawaban terputus (proses lama) → selesai bila aset kegiatan sudah 0.
        async () => {
          const c = await axios.get(`${API}/assets`, {
            params: { activity_id: activityId, page: 1, page_size: 1 }, timeout: 15000,
          });
          return (Number(c.data?.total) || 0) === 0;
        },
      );
      // Layar tetap buram sampai daftar SELESAI dimuat ulang — kalau tidak,
      // data lama sempat tampil lagi dan terkesan belum terhapus.
      try { await onSuccess?.(); } catch { /* galat muat ulang ditangani pemanggil */ }
      if (hasil.status === "belum_pasti") {
        toast.warning("Penghapusan masih berjalan di server. Muat ulang daftar beberapa saat lagi untuk memastikan.");
      } else {
        toast.success(hasil.data?.message || "Semua aset kegiatan ini sudah dihapus");
      }
      onClose(false);
    } catch (err) {
      toast.error(getApiError(err, "Gagal menghapus data"));
      // Jumlah berubah sejak dialog dibuka (409) → tampilkan angka terbaru
      // dan minta konfirmasi ulang, jangan biarkan angka basi di layar.
      if (err?.response?.status === 409) { setKetikan(""); muatJumlah(); }
    } finally {
      setDeleting(false);
    }
  }, [activityId, siap, jumlah, onClose, onSuccess, muatJumlah]);

  const tampilTerfilter = filterAktif && Number.isFinite(totalItems) && jumlah !== null && totalItems !== jumlah;

  return (
    <>
    <OverlayProses
      aktif={deleting}
      judul="Menghapus semua aset…"
      keterangan={`Sedang menghapus ${jumlah !== null ? `${jumlah.toLocaleString("id-ID")} aset` : "aset"} beserta foto & dokumennya di server. Mohon tunggu dan jangan tutup halaman ini.`}
      testId="overlay-hapus-semua"
    />
    {/* Selama proses berjalan dialog tidak boleh ditutup (Esc/klik luar). */}
    <Dialog open={open} onOpenChange={(v) => { if (!deleting) onClose(v); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-red-600 dark:text-red-400">
            <AlertTriangle className="w-5 h-5" />
            Hapus Semua Aset Kegiatan
          </DialogTitle>
          <DialogDescription className="sr-only">
            Menghapus permanen seluruh aset pada kegiatan ini beserta foto dan dokumennya.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-4" data-testid="bulk-delete-ringkasan">
            <p className="text-sm text-red-800 dark:text-red-300 font-medium mb-2">
              Anda akan menghapus SEMUA aset dari kegiatan:
            </p>
            <p className="text-sm text-red-700 dark:text-red-400 font-bold break-words">"{activityName || "-"}"</p>
            <p className="text-sm text-red-700 dark:text-red-300 mt-2" data-testid="bulk-delete-jumlah">
              {jumlah === null && !galatJumlah && (
                <span className="inline-flex items-center gap-1.5"><Loader2 className="w-3.5 h-3.5 animate-spin" />Menghitung aset…</span>
              )}
              {jumlah !== null && <>Total: <b className="text-base">{jumlah.toLocaleString("id-ID")}</b> aset akan dihapus</>}
            </p>
            {galatJumlah && <p className="text-xs text-red-700 dark:text-red-300 mt-2" role="alert">{galatJumlah}</p>}
          </div>

          {tampilTerfilter && (
            <p className="text-sm rounded-lg border border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200 p-3" data-testid="bulk-delete-peringatan-filter" role="alert">
              <b>Filter/pencarian yang aktif tidak berlaku di sini.</b> Daftar Anda sedang menampilkan{" "}
              {Number(totalItems).toLocaleString("id-ID")} aset, tetapi yang dihapus adalah{" "}
              <b>seluruh {jumlah.toLocaleString("id-ID")} aset</b> kegiatan ini. Untuk menghapus sebagian
              aset saja, hapus aset tersebut satu per satu dari daftar.
            </p>
          )}

          <p className="text-sm text-muted-foreground">
            Tindakan ini <b>tidak dapat dibatalkan</b>. Semua data aset, foto, dan dokumen kelengkapan akan dihapus permanen.
          </p>

          <div className="space-y-1.5">
            <label htmlFor="bulk-delete-konfirmasi" className="text-sm text-foreground">
              Ketik <b className="font-mono break-all select-all">{frasa}</b> untuk mengonfirmasi:
            </label>
            <Input
              id="bulk-delete-konfirmasi"
              value={ketikan}
              onChange={e => setKetikan(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              disabled={deleting || jumlah === null}
              data-testid="bulk-delete-konfirmasi"
              onKeyDown={e => { if (e.key === "Enter" && siap) handleDelete(); }}
            />
          </div>

          <div className="flex flex-wrap gap-3 justify-end">
            <Button variant="outline" onClick={() => onClose(false)} disabled={deleting}>Batal</Button>
            {galatJumlah ? (
              <Button variant="outline" onClick={muatJumlah} data-testid="bulk-delete-muat-ulang">Coba lagi</Button>
            ) : (
              <Button variant="destructive" onClick={handleDelete} disabled={!siap} className="bg-red-600 hover:bg-red-700" data-testid="bulk-delete-konfirmasi-btn">
                {deleting
                  ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Menghapus...</>
                  : <><Trash2 className="w-4 h-4 mr-2" />Hapus {jumlah !== null ? `${jumlah.toLocaleString("id-ID")} aset` : "semua"}</>}
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
    </>
  );
});

BulkDeleteDialog.displayName = "BulkDeleteDialog";

export default BulkDeleteDialog;
