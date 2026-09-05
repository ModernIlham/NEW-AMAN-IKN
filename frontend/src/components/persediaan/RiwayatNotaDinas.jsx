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
import { FileDown, PenLine, ScrollText } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const LABEL_JENIS = {
  kritis: "Usulan Pengadaan (Stok Kritis/Habis)",
  kedaluwarsa: "Persediaan Kedaluwarsa",
};

/** Tanggal ISO → "5 September 2026"; yang tak dikenal dikembalikan apa adanya. */
export function tanggalId(iso) {
  const s = String(iso || "").slice(0, 10);
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (!m) return s;
  const bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
    "Agustus", "September", "Oktober", "November", "Desember"];
  return `${Number(m[3])} ${bulan[Number(m[2]) - 1]} ${m[1]}`;
}

/**
 * Riwayat Nota Dinas persediaan yang TERBIT.
 *
 * Tanpa layar ini, nota bernomor hanya hidup di dialog tempat ia dibuat:
 * begitu ditutup, satu-satunya jejaknya adalah nomor di buku agenda yang tak
 * menunjuk balik ke daftar barangnya. Itu persis keluhan yang melahirkan
 * `ttd_penautan` — dokumen yang tak bisa ditemukan lagi dari layar tempat ia
 * lahir akan berakhir sebagai tautan mati.
 *
 * Nota yang gagal memesan nomor ditampilkan APA ADANYA sebagai "belum
 * bernomor", bukan disembunyikan: ia sudah terbit, dan nomornya masih bisa
 * dilengkapi dari Registrasi Persuratan.
 */
export default function RiwayatNotaDinas({ versi = 0, user }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [aksiId, setAksiId] = useState("");
  // Jalan KEMBALI ke tautan permintaan yang sudah dikirim — pola yang sama
  // dengan Riwayat BAST, Riwayat LPB, dan panel permohonan. Tanpa ini
  // tautannya hilang bersama dialog, dan yang tersisa berminggu-minggu
  // kemudian hanya "tautan mati".
  const [tautanTtd, setTautanTtd] = useState(null);

  const muat = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/persediaan/nota-dinas/register`,
        { params: { page: 1, page_size: 30 } });
      setItems(data?.items || []);
      setTotal(Number(data?.total) || 0);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memuat riwayat nota dinas");
    } finally {
      setLoading(false);
    }
  }, []);

  // `versi` naik setiap satu nota terbit — daftarnya ikut segar tanpa
  // halaman perlu dibuka ulang.
  useEffect(() => { muat(); }, [muat, versi]);

  const kirimTtd = async (n) => {
    setAksiId(n.id);
    try {
      await axios.post(`${API}/persediaan/nota-dinas/${n.id}/kirim-ttd`, {});
      toast.success("Nota dinas dikirim ke KPB untuk ditandatangani");
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
        aria-label="Riwayat Nota Dinas terbit"
        title="Riwayat Nota Dinas terbit"
        data-testid="persediaan-riwayat-nota">
        <ScrollText className="w-4 h-4" />
        <span className="hidden sm:inline">Nota Dinas</span>
        {total > 0 && (
          <span className="px-1.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[11px]"
            data-testid="persediaan-riwayat-nota-cacah">{total}</span>
        )}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Riwayat Nota Dinas Persediaan</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-muted-foreground">
            Nota dinas yang sudah terbit: nomornya terpesan di Registrasi
            Persuratan dan daftar barangnya dibekukan pada saat terbit.
            Pratinjau tanpa nomor tidak tercatat di sini.
          </p>
          {loading && (
            <p className="text-xs text-muted-foreground py-4 text-center"
              data-testid="persediaan-riwayat-nota-muat">Memuat…</p>
          )}
          {!loading && items.length === 0 && (
            <p className="text-xs text-muted-foreground py-6 text-center"
              data-testid="persediaan-riwayat-nota-kosong">
              Belum ada nota dinas yang terbit.
            </p>
          )}
          <ul className="divide-y divide-border">
            {items.map((n) => {
              const r = ringkasTtdDokumen(n.ttd);
              const sibuk = aksiId === n.id;
              return (
                <li key={n.id} className="py-2.5 flex items-start gap-2.5 flex-wrap"
                  data-testid={`persediaan-riwayat-nota-${n.id}`}>
                  <span className="min-w-[160px] flex-1">
                    <span className="block text-sm text-foreground truncate">
                      {n.nomor || (
                        <span className="text-amber-600 dark:text-amber-400">
                          Belum bernomor
                        </span>
                      )}
                    </span>
                    <span className="block text-[11px] text-muted-foreground">
                      {LABEL_JENIS[n.jenis] || n.jenis} · {n.jumlah_barang} barang
                      {" "}· {tanggalId(n.tanggal)}
                      {n.seleksi ? " · sebagian dipilih" : ""}
                    </span>
                    {r && (
                      <span className={`mt-1 inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold ${kelasNada(r.nada)}`}
                        data-testid={`persediaan-riwayat-nota-ttd-${n.id}`}>
                        {r.teks}
                      </span>
                    )}
                  </span>
                  <span className="flex gap-1.5 flex-wrap flex-shrink-0">
                    {n.signature_request_id && n.ttd?.id && (
                      <Button size="sm" variant="outline"
                        onClick={() => setTautanTtd({
                          srId: n.ttd.id,
                          judul: n.ttd.judul || `Nota Dinas ${n.nomor || ""}`.trim(),
                        })}
                        data-testid={`persediaan-riwayat-nota-tautan-${n.id}`}>
                        <PenLine className="w-3.5 h-3.5 mr-1" />Tautan TTD
                      </Button>
                    )}
                    {!n.signature_request_id && user?.role !== "viewer" && (
                      <Button size="sm" variant="outline" disabled={sibuk}
                        onClick={() => kirimTtd(n)}
                        data-testid={`persediaan-riwayat-nota-kirim-ttd-${n.id}`}>
                        <PenLine className="w-3.5 h-3.5 mr-1" />Kirim TTD KPB
                      </Button>
                    )}
                    <Button size="sm" variant="outline"
                      onClick={() => downloadFileWithProgress(
                        `${API}/persediaan/nota-dinas/${n.id}/pdf`,
                        `Nota_Dinas_${(n.nomor || n.id.slice(0, 8)).replace(/[^\w-]/g, "_")}.pdf`,
                        { label: "Nota Dinas" }).catch(() => {})}
                      data-testid={`persediaan-riwayat-nota-unduh-${n.id}`}>
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
