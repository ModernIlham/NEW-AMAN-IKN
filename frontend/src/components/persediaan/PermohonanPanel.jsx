import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import {
  CheckCircle2, ClipboardList, FileDown, PenLine, XCircle,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function getApiError(err, fallback) {
  return err?.response?.data?.detail || fallback;
}

const WARNA_STATUS = {
  diusulkan: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  diproses: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  disetujui: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  ditolak: "bg-red-500/15 text-red-600 dark:text-red-400",
  dibatalkan: "bg-muted text-muted-foreground",
};

/**
 * Panel Permohonan Transaksi Persediaan — SEDIA-KPB (PR UI).
 *
 * Tombol berlencana jumlah "menunggu" + dialog daftar permohonan: admin
 * yang BUKAN pengaju menyetujui/menolak (server menegakkan pemisahan peran;
 * tombolnya pun disembunyikan untuk pengaju sendiri supaya 403-nya tidak
 * perlu ditemukan lewat klik), pengaju membatalkan miliknya, dan permohonan
 * yang disetujui menyediakan unduhan Surat Persetujuan + kirim e-sign KPB.
 */
export default function PermohonanPanel({ user, onSelesai }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState([]);
  const [menunggu, setMenunggu] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [aksiId, setAksiId] = useState("");        // id yang sedang diproses
  const [tolak, setTolak] = useState(null);        // {id, alasan}
  const [gerbang, setGerbang] = useState(false);

  const isAdmin = user?.role === "admin";

  const muat = useCallback(async (status = statusFilter) => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/persediaan/permohonan`,
        { params: { status, page_size: 50 } });
      setRows(r.data?.items || []);
      setMenunggu(r.data?.menunggu || 0);
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat permohonan"));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  const muatGerbang = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/persediaan/permohonan-pengaturan`);
      setGerbang(!!r.data?.aktif);
    } catch { /* indikator saja — biarkan nilai lama */ }
  }, []);

  // Lencana "menunggu" harus hidup tanpa membuka dialog — sekali saat mount.
  useEffect(() => { muat(""); muatGerbang(); }, [muat, muatGerbang]);
  useEffect(() => { if (open) { muat(); muatGerbang(); } }, [open, muat, muatGerbang]);

  const setujui = async (p) => {
    setAksiId(p.id);
    try {
      const r = await axios.post(`${API}/persediaan/permohonan/${p.id}/setujui`);
      toast.success(r.data?.nomor
        ? `Disetujui — Surat Persetujuan ${r.data.nomor}`
        : "Permohonan disetujui dan transaksi tereksekusi");
      await muat();
      onSelesai?.();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menyetujui permohonan"));
      muat();
    } finally {
      setAksiId("");
    }
  };

  const kirimTolak = async () => {
    if (!tolak) return;
    if ((tolak.alasan || "").trim().length < 3) {
      toast.error("Alasan penolakan minimal 3 karakter"); return;
    }
    setAksiId(tolak.id);
    try {
      await axios.post(`${API}/persediaan/permohonan/${tolak.id}/tolak`,
        { alasan: tolak.alasan.trim() });
      toast.success("Permohonan ditolak");
      setTolak(null);
      muat();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menolak permohonan"));
    } finally {
      setAksiId("");
    }
  };

  const batal = async (p) => {
    setAksiId(p.id);
    try {
      await axios.post(`${API}/persediaan/permohonan/${p.id}/batal`);
      toast.success("Permohonan dibatalkan");
      muat();
    } catch (err) {
      toast.error(getApiError(err, "Gagal membatalkan permohonan"));
    } finally {
      setAksiId("");
    }
  };

  const unduhSurat = (p) => downloadFileWithProgress(
    `/api/persediaan/permohonan/${p.id}/dokumen`,
    `Persetujuan_Persediaan_${(p.nomor || p.id.slice(0, 8)).replace(/\//g, "-")}.pdf`,
    { label: "Surat Persetujuan Transaksi Persediaan" });

  const kirimTtd = async (p) => {
    setAksiId(p.id);
    try {
      await axios.post(`${API}/persediaan/permohonan/${p.id}/kirim-ttd`, {});
      toast.success("Surat Persetujuan dikirim ke KPB untuk ditandatangani");
      muat();
    } catch (err) {
      toast.error(getApiError(err, "Gagal mengirim tanda tangan"));
    } finally {
      setAksiId("");
    }
  };

  const ubahGerbang = async (aktif) => {
    try {
      const r = await axios.post(`${API}/persediaan/permohonan-pengaturan`,
        { aktif });
      setGerbang(!!r.data?.aktif);
      toast.success(r.data?.aktif
        ? "Wajib persetujuan DINYALAKAN — semua transaksi kini lewat permohonan"
        : "Wajib persetujuan dimatikan — transaksi kembali langsung");
      onSelesai?.();
    } catch (err) {
      toast.error(getApiError(err, "Gagal mengubah pengaturan"));
    }
  };

  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}
        data-testid="persediaan-permohonan-buka">
        <ClipboardList className="w-4 h-4 mr-2" />
        Permohonan
        {menunggu > 0 && (
          <span className="ml-2 min-w-5 h-5 px-1 rounded-full bg-amber-500 text-white text-[11px] leading-5 text-center"
            data-testid="persediaan-permohonan-badge">{menunggu}</span>
        )}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Permohonan Transaksi Persediaan</DialogTitle>
          </DialogHeader>

          {isAdmin && (
            <label className="flex items-center gap-2 text-xs rounded-lg border border-border p-2 cursor-pointer">
              <input type="checkbox" checked={gerbang}
                onChange={(e) => ubahGerbang(e.target.checked)}
                data-testid="persediaan-permohonan-gerbang" />
              <span>
                <b>Wajib persetujuan KPB</b> — semua transaksi persediaan
                diajukan sebagai permohonan dan baru tereksekusi setelah
                disetujui admin lain.
              </span>
            </label>
          )}

          <div className="flex gap-1.5 flex-wrap">
            {[["", "Semua"], ["diusulkan", "Menunggu"], ["disetujui", "Disetujui"],
              ["ditolak", "Ditolak"], ["dibatalkan", "Dibatalkan"]].map(([v, l]) => (
              <button key={v} type="button"
                onClick={() => { setStatusFilter(v); muat(v); }}
                className={`px-2.5 h-7 rounded-full text-xs border ${
                  statusFilter === v
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border text-muted-foreground"}`}>
                {l}
              </button>
            ))}
          </div>

          {loading ? (
            <p className="text-sm text-muted-foreground py-6 text-center">Memuat…</p>
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center"
              data-testid="persediaan-permohonan-kosong">
              Belum ada permohonan.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {rows.map((p) => {
                const milikku = p.diajukan_oleh === user?.username;
                const sibuk = aksiId === p.id;
                return (
                  <li key={p.id} className="py-2.5 flex flex-col gap-1.5"
                    data-testid={`permohonan-${p.id}`}>
                    <div className="flex items-start gap-2">
                      <span className={`px-2 py-0.5 rounded-full text-[11px] flex-shrink-0 ${WARNA_STATUS[p.status] || "bg-muted"}`}>
                        {p.status}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-foreground">{p.ringkasan}</p>
                        <p className="text-[11px] text-muted-foreground">
                          Diajukan {p.diajukan_oleh} · {(p.diajukan_pada || "").slice(0, 10)}
                          {p.nomor ? <> · No. <b>{p.nomor}</b></> : null}
                          {p.alasan_tolak ? <> · Alasan: {p.alasan_tolak}</> : null}
                          {p.galat_terakhir ? <> · Galat terakhir: {p.galat_terakhir}</> : null}
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-1.5 flex-wrap">
                      {p.status === "diusulkan" && isAdmin && !milikku && (
                        <>
                          <Button size="sm" disabled={sibuk} onClick={() => setujui(p)}
                            data-testid={`permohonan-setujui-${p.id}`}>
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1" />Setujui
                          </Button>
                          <Button size="sm" variant="outline" disabled={sibuk}
                            onClick={() => setTolak({ id: p.id, alasan: "" })}
                            data-testid={`permohonan-tolak-${p.id}`}>
                            <XCircle className="w-3.5 h-3.5 mr-1" />Tolak
                          </Button>
                        </>
                      )}
                      {p.status === "diusulkan" && milikku && (
                        <Button size="sm" variant="outline" disabled={sibuk}
                          onClick={() => batal(p)}
                          data-testid={`permohonan-batal-${p.id}`}>
                          Batalkan
                        </Button>
                      )}
                      {p.status === "disetujui" && (
                        <>
                          <Button size="sm" variant="outline" onClick={() => unduhSurat(p)}
                            data-testid={`permohonan-surat-${p.id}`}>
                            <FileDown className="w-3.5 h-3.5 mr-1" />Surat Persetujuan
                          </Button>
                          {!p.signature_request_id && user?.role !== "viewer" && (
                            <Button size="sm" variant="outline" disabled={sibuk}
                              onClick={() => kirimTtd(p)}
                              data-testid={`permohonan-kirim-ttd-${p.id}`}>
                              <PenLine className="w-3.5 h-3.5 mr-1" />Kirim TTD KPB
                            </Button>
                          )}
                        </>
                      )}
                    </div>
                    {tolak?.id === p.id && (
                      <div className="flex gap-1.5 items-center">
                        <input autoFocus value={tolak.alasan}
                          onChange={(e) => setTolak({ ...tolak, alasan: e.target.value })}
                          placeholder="Alasan penolakan (wajib)"
                          className="flex-1 h-8 px-2 rounded-lg border border-border bg-background text-xs"
                          data-testid="permohonan-alasan-tolak" />
                        <Button size="sm" disabled={sibuk} onClick={kirimTolak}>Kirim</Button>
                        <Button size="sm" variant="ghost" onClick={() => setTolak(null)}>Urungkan</Button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
