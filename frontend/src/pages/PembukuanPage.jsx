import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, BookOpen, FileDown, IdCard, Loader2, Save, ScrollText,
  Search, Table2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useBackGuard } from "@/hooks/useBackGuard";
import { useConfirm } from "@/components/ui/ConfirmDialog";
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
  const [tab, setTab] = useState("dbkp"); // dbkp | jurnal | kib
  const [dbkp, setDbkp] = useState(null);
  const [jurnal, setJurnal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  // KIB: pencarian aset → info jenis + form field khusus
  const [qKib, setQKib] = useState("");
  const [hasilKib, setHasilKib] = useState([]);   // hasil pencarian aset
  const [cariKib, setCariKib] = useState(false);
  const [kib, setKib] = useState(null);           // {jenis,label,fields,data,aset}
  const [formKib, setFormKib] = useState({});
  const [simpanKib, setSimpanKib] = useState(false);
  const [backfilling, setBackfilling] = useState(false);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  useEffect(() => {
    axios.get(`${API}/pembukuan/dbkp`)
      .then((r) => setDbkp(r.data))
      .catch((e) => toast.error(apiErr(e, "Gagal memuat DBKP")))
      .finally(() => setLoading(false));
  }, []);

  const muatJurnal = useCallback(async (p = 1, qBaru) => {
    try {
      const filter = (qBaru !== undefined ? qBaru : q).trim();
      const params = new URLSearchParams({ page: String(p), page_size: "50" });
      if (filter) params.append("asset_id", filter);
      const r = await axios.get(`${API}/pembukuan/mutasi?${params}`);
      setJurnal(r.data);
      setPage(p);
    } catch (e) {
      toast.error(apiErr(e, "Gagal memuat jurnal Buku Barang"));
    }
  }, [q]);
  useEffect(() => { if (tab === "jurnal" && !jurnal) muatJurnal(1); }, [tab, jurnal, muatJurnal]);

  // Backfill saldo awal (admin) — pemicu UI untuk endpoint idempoten yang
  // sebelumnya hanya bisa dipanggil via API manual (temuan audit klaim-aktif).
  const jalankanBackfill = useCallback(async () => {
    const ok = await confirm({
      title: "Backfill saldo awal Buku Barang?",
      description:
        "Aset aktif yang BELUM punya entri jurnal diberi satu entri sintetis " +
        "100 Saldo Awal (tanggal buku = tanggal perolehan). Idempoten — aman " +
        "diulang; aset yang sudah berjurnal tidak disentuh.",
      confirmLabel: "Jalankan",
    });
    if (!ok) return;
    setBackfilling(true);
    try {
      const r = await axios.post(`${API}/pembukuan/mutasi/backfill`);
      toast.success(
        `Saldo awal dibuat untuk ${r.data?.dibuat ?? 0} aset ` +
        `(${r.data?.sudah_berjurnal ?? 0} sudah berjurnal)`);
      muatJurnal(1);
    } catch (e) {
      toast.error(apiErr(e, "Gagal menjalankan backfill"));
    } finally {
      setBackfilling(false);
    }
  }, [confirm, muatJurnal]);

  const cariAsetKib = useCallback(async () => {
    if (!qKib.trim()) return;
    setCariKib(true);
    try {
      const r = await axios.get(`${API}/assets`, {
        params: { search: qKib.trim(), page_size: 10 } });
      setHasilKib(r.data?.items || []);
    } catch (e) {
      toast.error(apiErr(e, "Gagal mencari aset"));
    } finally { setCariKib(false); }
  }, [qKib]);

  const bukaKib = useCallback(async (aset) => {
    setKib(null);
    try {
      const r = await axios.get(`${API}/pembukuan/kib/${aset.id}`);
      setKib(r.data);
      setFormKib(r.data?.data || {});
    } catch (e) {
      toast.error(apiErr(e, "Aset ini tidak ber-KIB"));
    }
  }, []);

  const simpanDataKib = async () => {
    if (!kib) return;
    setSimpanKib(true);
    try {
      const r = await axios.put(`${API}/pembukuan/kib/${kib.aset.id}`, { data: formKib });
      setFormKib(r.data?.data || formKib);
      toast.success("Data KIB tersimpan — siap dicetak");
    } catch (e) {
      toast.error(apiErr(e, "Gagal menyimpan KIB"));
    } finally { setSimpanKib(false); }
  };

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
          {[["dbkp", "DBKP", "DBKP per Golongan", Table2],
            ["jurnal", "Jurnal", "Buku Barang (Jurnal)", ScrollText],
            ["kib", "KIB", "KIB (Kartu Identitas)", IdCard]].map(([k, pendek, panjang, Icon]) => (
            <button key={k} type="button" onClick={() => setTab(k)} title={panjang}
              className={`flex-1 text-[11px] sm:text-xs font-semibold py-1.5 rounded-md transition-colors flex items-center justify-center gap-1.5 min-w-0 min-h-0 whitespace-nowrap ${tab === k ? "bg-card text-indigo-700 dark:text-indigo-400 shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
              data-testid={`pembukuan-tab-${k}`}>
              <Icon className="w-3.5 h-3.5 flex-shrink-0" />
              <span className="sm:hidden">{pendek}</span>
              <span className="hidden sm:inline">{panjang}</span>
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
                  <p className="text-sm font-extrabold mt-0.5 truncate whitespace-nowrap tabular-nums" title={fmtRp(v)}>{fmtRp(v)}</p>
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
                      <tr>
                        <td colSpan={7} className="text-center py-10">
                          <BookOpen className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
                          <p className="text-xs font-semibold text-muted-foreground">Belum ada aset dibukukan</p>
                          <p className="text-[11px] text-muted-foreground mt-1">
                            Aset aktif dari modul Inventarisasi otomatis terbukukan di sini.
                          </p>
                        </td>
                      </tr>
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
              <div className="px-3 py-2 border-t border-border space-y-0.5">
                <p className="text-[11px] text-muted-foreground">
                  Ambang kapitalisasi efektif: Peralatan &amp; Mesin ≥ {fmtRp(dbkp?.ambang?.["3"])} ·
                  Gedung &amp; Bangunan ≥ {fmtRp(dbkp?.ambang?.["4"])} — dapat diubah admin di
                  Referensi Akun BAS › Akun Aset.
                </p>
                <p className="text-[11px] text-muted-foreground">
                  DBKP per kegiatan serta LBKP/CaLBMN tersedia di modul Inventarisasi &amp; Pelaporan.
                </p>
              </div>
            </div>
          </>
        ))}

        {tab === "jurnal" && (
          <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
            <div className="px-3 py-2 border-b border-border flex items-center gap-2 flex-wrap">
              <ScrollText className="w-4 h-4 text-muted-foreground" />
              <p className="text-xs font-bold flex-1 min-w-[180px]">Buku Barang — jurnal mutasi ber-kode (append-only, pola SIMAK/SAKTI)</p>
              {user?.role === "admin" && (
                <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 min-w-0 gap-1"
                  disabled={backfilling}
                  title="Beri entri saldo awal (kode 100) untuk aset lama yang belum punya jurnal — idempoten, aman diulang"
                  onClick={jalankanBackfill}
                  data-testid="jurnal-backfill-btn">
                  {backfilling ? <Loader2 className="w-3 h-3 animate-spin" /> : <ScrollText className="w-3 h-3" />}
                  Backfill Saldo Awal
                </Button>
              )}
            </div>
            <div className="px-3 py-2 border-b border-border/60">
              {/* Ikon cari HARUS di wrapper relatif khusus input — kalau tidak,
                  top-1/2 ikut menghitung tinggi teks bantuan di bawah lalu
                  ikonnya melorot ke bawah (temuan HP: berantakan kebawah). */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input value={q} onChange={(e) => setQ(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && muatJurnal(1)}
                  placeholder="Filter berdasarkan ID aset (bukan nama/kode) — Enter" className="pl-8 h-9 text-xs" />
              </div>
              <p className="text-[10px] text-muted-foreground mt-1">
                Filter ini memakai ID aset internal. Cari kode/nama barang di tab <b>KIB</b> atau daftar aset, lalu salin ID-nya ke sini.
              </p>
            </div>
            {!jurnal ? (
              <div className="py-12 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>
            ) : (jurnal.items || []).length === 0 ? (
              <div className="text-center py-10 px-4">
                <ScrollText className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
                {q.trim() ? (
                  <>
                    <p className="text-xs font-semibold text-muted-foreground">Tidak ada entri yang cocok dengan filter ID aset</p>
                    <Button size="sm" variant="outline" className="mt-3 h-8 text-xs min-h-0 min-w-0"
                      onClick={() => { setQ(""); muatJurnal(1, ""); }} data-testid="jurnal-reset-filter">
                      Hapus filter
                    </Button>
                  </>
                ) : (
                  <>
                    <p className="text-xs font-semibold text-muted-foreground">Jurnal masih kosong</p>
                    <p className="text-[11px] text-muted-foreground mt-1">
                      Entri tercipta otomatis dari saldo awal (backfill), reklasifikasi, dan mutasi lain.
                    </p>
                  </>
                )}
              </div>
            ) : (
              <div className="divide-y divide-border/60">
                {(jurnal.items || []).map((m) => (
                  <div key={m.id} className="px-3 py-2 flex items-center gap-2.5" data-testid={`jurnal-row-${m.id}`}>
                    <span className={`px-1.5 py-0.5 rounded font-mono text-[10px] font-bold flex-shrink-0 ${WARNA_EFEK[m.efek] || WARNA_EFEK.netral}`}>
                      {m.kode_transaksi}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[12px] font-semibold truncate">
                        {m.uraian_transaksi || m.kode_transaksi} — {m.nama_barang || m.kode_barang || m.asset_id}
                      </p>
                      <p className="text-[10px] text-muted-foreground truncate"
                        title={`${m.tanggal_buku} · ${m.kode_barang || "-"}${m.nup ? `/${m.nup}` : ""}${m.oleh ? ` · ${m.oleh}` : ""}`}>
                        {m.tanggal_buku} · {m.kode_barang || "-"}{m.nup ? `/${m.nup}` : ""}
                        {m.oleh ? ` · ${m.oleh}` : ""}
                      </p>
                    </div>
                    {m.nilai != null && (
                      <span className="ml-auto flex-shrink-0 font-mono text-[11px] font-semibold" title={fmtRp(m.nilai)}>
                        {fmtRp(m.nilai)}
                      </span>
                    )}
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

        {tab === "kib" && (
          <div className="space-y-3">
            <div className="bg-card rounded-xl border border-border shadow-sm p-3 space-y-2">
              <p className="text-xs font-bold flex items-center gap-1.5">
                <IdCard className="w-4 h-4" />Kartu Identitas Barang — PMK 181 (pola SAKTI)
              </p>
              <p className="text-[10px] text-muted-foreground">
                KIB per-unit untuk <b>tanah</b> (gol 2), <b>bangunan gedung</b> (gol 4), <b>alat angkutan</b> (302),
                <b> alat besar</b> (301), dan <b>alat persenjataan</b> (307). Cari aset → lengkapi data khusus → cetak kartu.
              </p>
              <div className="flex items-center gap-1.5">
                <div className="relative flex-1">
                  <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <Input value={qKib} onChange={(e) => setQKib(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && cariAsetKib()}
                    placeholder="Cari kode/nama aset… (Enter)" className="pl-8 h-9 text-xs" data-testid="kib-cari" />
                </div>
                <Button size="sm" variant="outline" className="h-9 text-xs" disabled={cariKib} onClick={cariAsetKib}>
                  {cariKib ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Cari"}
                </Button>
              </div>
              {hasilKib.length > 0 && (
                <div className="divide-y divide-border/60 rounded-lg border border-border max-h-48 overflow-y-auto">
                  {hasilKib.map((a) => (
                    <button key={a.id} type="button" onClick={() => bukaKib(a)}
                      className="w-full text-left px-2.5 py-1.5 hover:bg-muted/60 min-w-0 min-h-0"
                      data-testid={`kib-pilih-${a.id}`}>
                      <p className="text-[12px] font-semibold truncate">{a.asset_name}</p>
                      <p className="text-[10px] text-muted-foreground truncate">
                        {a.asset_code}{a.NUP ? `/${a.NUP}` : ""} · {a.location || "-"}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {kib && (
              <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="kib-panel">
                <div className="px-3 py-2.5 border-b border-border flex items-center gap-2 flex-wrap">
                  <IdCard className="w-4 h-4 text-indigo-700 dark:text-indigo-400 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-bold">{kib.label}</p>
                    <p className="text-[10px] text-muted-foreground truncate">
                      {kib.aset?.asset_name} · {kib.aset?.asset_code}{kib.aset?.NUP ? `/${kib.aset.NUP}` : ""}
                    </p>
                  </div>
                </div>
                <div className="p-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {(kib.fields || []).map((f) => (
                    <div key={f.key}>
                      <label className="text-[11px] text-muted-foreground">{f.label}</label>
                      <Input value={formKib[f.key] || ""}
                        onChange={(e) => setFormKib((p) => ({ ...p, [f.key]: e.target.value }))}
                        className="h-9 mt-0.5 text-sm" data-testid={`kib-field-${f.key}`} />
                    </div>
                  ))}
                </div>
                <div className="px-3 pb-3 flex items-center justify-end gap-2 flex-wrap gap-y-1.5">
                  <p className="text-[10px] text-muted-foreground mr-auto self-center">
                    Simpan dahulu sebelum mencetak agar PDF memuat data terbaru.
                  </p>
                  <Button size="sm" variant="outline" className="h-9 text-xs"
                    onClick={() => downloadFileWithProgress(
                      `${API}/pembukuan/kib-pdf/${kib.aset.id}`,
                      `KIB_${kib.aset.asset_code || "aset"}.pdf`).catch(() => {})}
                    data-testid="kib-unduh">
                    <FileDown className="w-3.5 h-3.5 mr-1.5" />Cetak KIB (PDF)
                  </Button>
                  <Button size="sm" className="h-9 text-xs bg-indigo-700 hover:bg-indigo-800 text-white"
                    disabled={simpanKib} onClick={simpanDataKib} data-testid="kib-simpan">
                    {simpanKib ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Save className="w-3.5 h-3.5 mr-1.5" />}
                    Simpan Data KIB
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
      {confirmDialog}
    </div>
  );
}
