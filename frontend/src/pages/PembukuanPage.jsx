import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, BookOpen, FileDown, Loader2, ScrollText, Search, Table2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function apiErr(e, fb) { return e?.response?.data?.detail || fb; }

const fmtRp = (v) => `Rp${Math.round(Number(v || 0)).toLocaleString("id-ID")}`;

const WARNA_EFEK = {
  tambah: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  kurang: "bg-red-500/15 text-red-600 dark:text-red-400",
  netral: "bg-muted text-muted-foreground",
};

/**
 * Pembukuan — DBKP (Daftar Barang Kuasa Pengguna) global per golongan
 * intra/ekstrakomptabel (ambang PMK 181 efektif — bisa dioverride di
 * Referensi Akun BAS) + Buku Barang (jurnal mutasi ber-kode SIMAK/SAKTI,
 * append-only). Sumber: seluruh aset aktif (ter-scope satker user).
 */
export default function PembukuanPage({ user, onBack }) {
  const [tab, setTab] = useState("dbkp"); // dbkp | jurnal
  const [dbkp, setDbkp] = useState(null);
  const [jurnal, setJurnal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  useEffect(() => {
    axios.get(`${API}/pembukuan/dbkp`)
      .then((r) => setDbkp(r.data))
      .catch((e) => toast.error(apiErr(e, "Gagal memuat DBKP")))
      .finally(() => setLoading(false));
  }, []);

  const muatJurnal = useCallback(async (p = 1) => {
    try {
      const params = new URLSearchParams({ page: String(p), page_size: "50" });
      if (q.trim()) params.append("asset_id", "");
      const r = await axios.get(`${API}/pembukuan/mutasi?${params}`);
      setJurnal(r.data);
      setPage(p);
    } catch (e) {
      toast.error(apiErr(e, "Gagal memuat jurnal Buku Barang"));
    }
  }, [q]);
  useEffect(() => { if (tab === "jurnal" && !jurnal) muatJurnal(1); }, [tab, jurnal, muatJurnal]);

  const rows = dbkp?.rows || [];
  const total = dbkp?.total || {};
  const posisi = dbkp?.posisi || {};

  return (
    <div className="min-h-screen bg-background" data-testid="pembukuan-page">
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-6xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pembukuan-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-indigo-700 flex items-center justify-center flex-shrink-0">
            <BookOpen className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Pembukuan</h1>
            <p className="text-[11px] text-muted-foreground leading-tight truncate">
              DBKP intra/ekstrakomptabel (PMK 181) · Buku Barang (jurnal mutasi)
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        <div className="flex bg-muted rounded-lg p-0.5 gap-0.5">
          {[["dbkp", "DBKP per Golongan", Table2], ["jurnal", "Buku Barang (Jurnal)", ScrollText]].map(([k, label, Icon]) => (
            <button key={k} type="button" onClick={() => setTab(k)}
              className={`flex-1 text-[11px] sm:text-xs font-semibold py-1.5 rounded-md transition-colors flex items-center justify-center gap-1.5 min-w-0 min-h-0 ${tab === k ? "bg-card text-indigo-700 dark:text-indigo-400 shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
              data-testid={`pembukuan-tab-${k}`}>
              <Icon className="w-3.5 h-3.5" />{label}
            </button>
          ))}
        </div>

        {tab === "dbkp" && (loading ? (
          <div className="py-16 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" /></div>
        ) : (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[["Intrakomptabel", total.jumlah_intra, total.nilai_intra],
                ["Ekstrakomptabel", total.jumlah_ekstra, total.nilai_ekstra],
                ["Persediaan", posisi?.persediaan?.jumlah, posisi?.persediaan?.nilai],
                ["Posisi BMN di Neraca", posisi?.total?.jumlah_total, posisi?.total?.nilai_total]].map(([label, n, v]) => (
                <div key={label} className="rounded-xl border border-border bg-card p-2.5">
                  <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide truncate">{label}</p>
                  <p className="text-sm font-extrabold mt-0.5">{fmtRp(v)}</p>
                  <p className="text-[10px] text-muted-foreground">{Number(n || 0).toLocaleString("id-ID")} unit/jenis</p>
                </div>
              ))}
            </div>
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              <div className="px-3 py-2 border-b border-border flex items-center justify-between gap-2 flex-wrap">
                <p className="text-xs font-bold">DBKP — rekap per golongan (aset aktif, nilai buku terkini)</p>
                <Button variant="outline" size="sm" className="h-8 text-[11px]"
                  onClick={() => downloadFileWithProgress(`${API}/pembukuan/posisi-bmn-pdf`, "Posisi_BMN_Neraca.pdf")
                    .catch(() => {})}
                  data-testid="pembukuan-unduh-posisi">
                  <FileDown className="w-3.5 h-3.5 mr-1" />Posisi BMN (PDF)
                </Button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm min-w-[680px]">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-left text-[11px] text-muted-foreground">
                      <th className="px-3 py-2 font-semibold">Gol</th>
                      <th className="px-3 py-2 font-semibold">Uraian</th>
                      <th className="px-3 py-2 font-semibold text-right">Intra (unit)</th>
                      <th className="px-3 py-2 font-semibold text-right">Nilai Intra</th>
                      <th className="px-3 py-2 font-semibold text-right">Ekstra (unit)</th>
                      <th className="px-3 py-2 font-semibold text-right">Nilai Ekstra</th>
                      <th className="px-3 py-2 font-semibold text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.golongan} className="border-b border-border/60 last:border-0 hover:bg-muted/40"
                        data-testid={`dbkp-row-${r.golongan}`}>
                        <td className="px-3 py-1.5 font-mono font-bold">{r.golongan}</td>
                        <td className="px-3 py-1.5 text-[12px]">{r.uraian}</td>
                        <td className="px-3 py-1.5 text-right">{r.jumlah_intra.toLocaleString("id-ID")}</td>
                        <td className="px-3 py-1.5 text-right font-mono text-[12px]">{fmtRp(r.nilai_intra)}</td>
                        <td className="px-3 py-1.5 text-right">{r.jumlah_ekstra.toLocaleString("id-ID")}</td>
                        <td className="px-3 py-1.5 text-right font-mono text-[12px]">{fmtRp(r.nilai_ekstra)}</td>
                        <td className="px-3 py-1.5 text-right font-mono text-[12px] font-bold">{fmtRp(r.nilai_total)}</td>
                      </tr>
                    ))}
                    {rows.length === 0 && (
                      <tr><td colSpan={7} className="text-center text-xs text-muted-foreground py-8">Belum ada aset dibukukan</td></tr>
                    )}
                  </tbody>
                  {rows.length > 0 && (
                    <tfoot>
                      <tr className="bg-muted/60 font-bold text-[12px]">
                        <td className="px-3 py-2" colSpan={2}>TOTAL</td>
                        <td className="px-3 py-2 text-right">{Number(total.jumlah_intra || 0).toLocaleString("id-ID")}</td>
                        <td className="px-3 py-2 text-right font-mono">{fmtRp(total.nilai_intra)}</td>
                        <td className="px-3 py-2 text-right">{Number(total.jumlah_ekstra || 0).toLocaleString("id-ID")}</td>
                        <td className="px-3 py-2 text-right font-mono">{fmtRp(total.nilai_ekstra)}</td>
                        <td className="px-3 py-2 text-right font-mono">{fmtRp(total.nilai_total)}</td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
              <p className="px-3 py-2 text-[10px] text-muted-foreground border-t border-border">
                Ambang kapitalisasi efektif: Peralatan &amp; Mesin ≥ {fmtRp(dbkp?.ambang?.["3"])} ·
                Gedung &amp; Bangunan ≥ {fmtRp(dbkp?.ambang?.["4"])} — dapat diubah admin di
                Referensi Akun BAS › Akun Aset. DBKP per kegiatan + LBKP/CaLBMN ada di modul
                Inventarisasi &amp; Pelaporan.
              </p>
            </div>
          </>
        ))}

        {tab === "jurnal" && (
          <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
            <div className="px-3 py-2 border-b border-border flex items-center gap-2">
              <ScrollText className="w-4 h-4 text-muted-foreground" />
              <p className="text-xs font-bold flex-1">Buku Barang — jurnal mutasi ber-kode (append-only, pola SIMAK/SAKTI)</p>
            </div>
            <div className="relative px-3 py-2 border-b border-border/60">
              <Search className="w-3.5 h-3.5 absolute left-6 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input value={q} onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && muatJurnal(1)}
                placeholder="Filter id aset… (Enter)" className="pl-8 h-9 text-xs" />
            </div>
            {!jurnal ? (
              <div className="py-12 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>
            ) : (jurnal.items || []).length === 0 ? (
              <p className="text-center text-xs text-muted-foreground py-10">
                Jurnal kosong — entri tercipta dari saldo awal (backfill), reklasifikasi, dan mutasi lain.
              </p>
            ) : (
              <div className="divide-y divide-border/60">
                {(jurnal.items || []).map((m) => (
                  <div key={m.id} className="px-3 py-2 flex items-center gap-2.5" data-testid={`jurnal-row-${m.id}`}>
                    <span className={`px-1.5 py-0.5 rounded font-mono text-[10px] font-bold flex-shrink-0 ${WARNA_EFEK[m.efek] || WARNA_EFEK.netral}`}>
                      {m.kode_transaksi}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[12px] font-semibold truncate">
                        {m.uraian_transaksi || m.kode_transaksi} — {m.nama_barang || m.asset_id}
                      </p>
                      <p className="text-[10px] text-muted-foreground truncate">
                        {m.tanggal_buku} · {m.kode_barang || "-"}{m.nup ? `/${m.nup}` : ""}
                        {m.nilai != null ? ` · ${fmtRp(m.nilai)}` : ""}{m.oleh ? ` · ${m.oleh}` : ""}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {jurnal && jurnal.total_pages > 1 && (
              <div className="flex items-center justify-between px-3 py-2 border-t border-border bg-muted/30">
                <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => muatJurnal(page - 1)}>Sebelumnya</Button>
                <span className="text-[11px] text-muted-foreground">Hal {jurnal.page}/{jurnal.total_pages} · {jurnal.total} entri</span>
                <Button size="sm" variant="ghost" disabled={page >= jurnal.total_pages} onClick={() => muatJurnal(page + 1)}>Berikutnya</Button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
