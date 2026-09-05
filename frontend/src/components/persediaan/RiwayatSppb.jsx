import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import { ringkasTtdDokumen, kelasNada } from "@/lib/statusTtd";
import TautanTtdDialog from "@/components/ttd/TautanTtdDialog";
import { tanggalId } from "@/components/persediaan/RiwayatNotaDinas";
import { ClipboardSignature, FileDown, PenLine } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Riwayat SPPB — bukti pengeluaran barang persediaan.
 *
 * Sisi MASUK sudah punya Riwayat LPB sejak lama; sisi KELUAR tak punya apa-apa.
 * Pengeluaran barang hanya meninggalkan baris jurnal: ada catatan bahwa stok
 * berkurang, tak ada naskah yang bisa ditandatangani penerimanya, dan tak ada
 * layar tempat naskah itu bisa ditemukan lagi.
 *
 * SPPB tanpa nomor ditampilkan apa adanya, bukan disembunyikan: barangnya sudah
 * keluar dan naskahnya sudah sah; nomornya masih bisa dilengkapi dari
 * Registrasi Persuratan.
 */
export default function RiwayatSppb({ versi = 0, user }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [aksiId, setAksiId] = useState("");
  const [tautanTtd, setTautanTtd] = useState(null);

  const muat = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/persediaan/sppb`,
        { params: { page: 1, page_size: 30 } });
      setItems(data?.items || []);
      setTotal(Number(data?.total) || 0);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memuat riwayat SPPB");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { muat(); }, [muat, versi]);

  const kirimTtd = async (s) => {
    setAksiId(s.id);
    try {
      await axios.post(`${API}/persediaan/sppb/${s.id}/kirim-ttd`, {});
      toast.success("SPPB dikirim untuk ditandatangani KPB lalu penerima");
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengirim tanda tangan");
    } finally {
      setAksiId("");
    }
  };

  return (
    <>
      <Button variant="outline" className="h-10 gap-1.5" onClick={() => setOpen(true)}
        aria-label="Riwayat SPPB — bukti pengeluaran barang"
        title="Riwayat SPPB — bukti pengeluaran barang"
        data-testid="persediaan-riwayat-sppb">
        <ClipboardSignature className="w-4 h-4" />
        <span className="hidden sm:inline">SPPB</span>
        {total > 0 && (
          <span className="px-1.5 rounded-full bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[11px]"
            data-testid="persediaan-riwayat-sppb-cacah">{total}</span>
        )}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Riwayat SPPB</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-muted-foreground">
            Surat Perintah Pengeluaran Barang terbit otomatis dari transaksi
            keluar massal, dengan daftar barang yang dibekukan. Ditandatangani
            Kuasa Pengguna Barang lalu penerimanya.
          </p>
          {loading && (
            <p className="text-xs text-muted-foreground py-4 text-center"
              data-testid="persediaan-riwayat-sppb-muat">Memuat…</p>
          )}
          {!loading && items.length === 0 && (
            <p className="text-xs text-muted-foreground py-6 text-center"
              data-testid="persediaan-riwayat-sppb-kosong">
              Belum ada SPPB. Terbit otomatis saat transaksi keluar massal.
            </p>
          )}
          <ul className="divide-y divide-border">
            {items.map((s) => {
              const r = ringkasTtdDokumen(s.ttd);
              const sibuk = aksiId === s.id;
              return (
                <li key={s.id} className="py-2.5 flex items-start gap-2.5 flex-wrap"
                  data-testid={`persediaan-riwayat-sppb-${s.id}`}>
                  <span className="min-w-[160px] flex-1">
                    <span className="block text-sm text-foreground truncate">
                      {s.nomor || (
                        <span className="text-amber-600 dark:text-amber-400">
                          Belum bernomor
                        </span>
                      )}
                    </span>
                    <span className="block text-[11px] text-muted-foreground">
                      {s.jenis_label || s.jenis} · {s.jumlah_barang} barang
                      {" "}· {tanggalId(s.tanggal)}
                      {s.penerima_nama ? ` · ${s.penerima_nama}` : ""}
                      {s.unit_penerima ? ` (${s.unit_penerima})` : ""}
                    </span>
                    {r && (
                      <span className={`mt-1 inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold ${kelasNada(r.nada)}`}
                        data-testid={`persediaan-riwayat-sppb-ttd-${s.id}`}>
                        {r.teks}
                      </span>
                    )}
                  </span>
                  <span className="flex gap-1.5 flex-wrap flex-shrink-0">
                    {s.signature_request_id && s.ttd?.id && (
                      <Button size="sm" variant="outline"
                        onClick={() => setTautanTtd({
                          srId: s.ttd.id,
                          judul: s.ttd.judul || `SPPB ${s.nomor || ""}`.trim(),
                        })}
                        data-testid={`persediaan-riwayat-sppb-tautan-${s.id}`}>
                        <PenLine className="w-3.5 h-3.5 mr-1" />Tautan TTD
                      </Button>
                    )}
                    {!s.signature_request_id && user?.role !== "viewer" && (
                      <Button size="sm" variant="outline" disabled={sibuk}
                        onClick={() => kirimTtd(s)}
                        data-testid={`persediaan-riwayat-sppb-kirim-ttd-${s.id}`}>
                        <PenLine className="w-3.5 h-3.5 mr-1" />Kirim TTD
                      </Button>
                    )}
                    <Button size="sm" variant="outline"
                      onClick={() => downloadFileWithProgress(
                        `${API}/persediaan/sppb/${s.id}/pdf`,
                        `SPPB_${(s.nomor || s.id.slice(0, 8)).replace(/[^\w-]/g, "_")}.pdf`,
                        { label: "SPPB" }).catch(() => {})}
                      data-testid={`persediaan-riwayat-sppb-unduh-${s.id}`}>
                      <FileDown className="w-3.5 h-3.5 mr-1" />Unduh
                    </Button>
                  </span>
                </li>
              );
            })}
          </ul>
        </DialogContent>
      </Dialog>
      {tautanTtd && (
        <TautanTtdDialog srId={tautanTtd.srId} judul={tautanTtd.judul}
          onTutup={() => setTautanTtd(null)} onBerubah={muat} />
      )}
    </>
  );
}
