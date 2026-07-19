import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  AlertTriangle, ChevronDown, ChevronRight, FileDown, Loader2, PackagePlus,
  RefreshCcw, Shuffle, Upload,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { downloadFileWithProgress } from "@/lib/downloadFile";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Jeda antar percobaan ulang unggah saat koneksi putus (ms).
const JEDA_RETRY = [2000, 5000];

function fmtRp(v) {
  const n = Number(v || 0);
  try { return `Rp${Math.round(n).toLocaleString("id-ID")}`; } catch { return `Rp${n}`; }
}

/**
 * Sinkronisasi SIMAN V2 — kanal pembaruan berkala via impor manual ekspor
 * "Master Aset" (SIMAN = data valid; belum ada API untuk satker).
 *
 * Alur pakai: unduh ekspor Master Aset dari SIMAN V2 → unggah di sini →
 * aset yang datanya berbeda tertanda "≠ SIMAN" (di kartu & form aset) →
 * tinjau selisih per aset di panel ini → "Terapkan nilai SIMAN".
 */
export default function SimanSyncCard({ isAdmin }) {
  const [ringkasan, setRingkasan] = useState(null);
  const [mengunggah, setMengunggah] = useState(false);
  const [persenUnggah, setPersenUnggah] = useState(0);
  const [tandaiHilang, setTandaiHilang] = useState(false);
  const [terbuka, setTerbuka] = useState(false);
  const [selisih, setSelisih] = useState(null); // {items,total,page,total_pages}
  const [muatSelisih, setMuatSelisih] = useState(false);
  const [bukaAset, setBukaAset] = useState(null); // id aset yang rinciannya terbuka
  const [menerapkan, setMenerapkan] = useState(null); // id aset yang sedang diterapkan
  const [mereklas, setMereklas] = useState(null);     // id aset yang sedang direklasifikasi
  const { confirm, confirmDialog } = useConfirm();
  // Panel buat draft aset dari baris SIMAN belum tercatat:
  // {importId, activities, activityId, sibuk, hasil}
  const [draft, setDraft] = useState(null);
  const fileRef = useRef(null);

  const muatRingkasan = useCallback(() => {
    axios.get(`${API}/siman/ringkasan`)
      .then((r) => setRingkasan(r.data))
      .catch(() => setRingkasan({ gagal: true }));
  }, []);

  useEffect(() => { muatRingkasan(); }, [muatRingkasan]);

  const ambilSelisih = useCallback(async (page = 1) => {
    setMuatSelisih(true);
    try {
      const r = await axios.get(`${API}/siman/selisih?page=${page}&page_size=50`);
      setSelisih(r.data);
    } catch {
      toast.error("Gagal memuat daftar selisih SIMAN");
    } finally {
      setMuatSelisih(false);
    }
  }, []);

  useEffect(() => {
    if (terbuka && !selisih) ambilSelisih(1);
  }, [terbuka, selisih, ambilSelisih]);

  const unggah = async (file) => {
    if (!file) return;
    setMengunggah(true);
    setPersenUnggah(0);
    const fd = new FormData();
    fd.append("file", file);
    // Andal di koneksi lapangan: timeout longgar + coba ulang otomatis saat
    // gagal JARINGAN (tanpa respons server). Error 4xx/5xx TIDAK diulang.
    let r = null;
    for (let percobaan = 0; ; percobaan++) {
      try {
        r = await axios.post(
          `${API}/siman/import?tandai_tidak_ditemukan=${tandaiHilang}`, fd, {
            headers: { "Content-Type": "multipart/form-data" },
            timeout: 180000,
            onUploadProgress: (ev) => {
              if (ev.total) setPersenUnggah(Math.round((ev.loaded / ev.total) * 100));
            },
          });
        break;
      } catch (e) {
        const putus = !e?.response; // network error / timeout — layak diulang
        if (putus && percobaan < JEDA_RETRY.length) {
          toast.info(`Koneksi terputus saat mengunggah — mencoba ulang (${percobaan + 2}/${JEDA_RETRY.length + 1})…`);
          await new Promise((res) => setTimeout(res, JEDA_RETRY[percobaan]));
          setPersenUnggah(0);
          continue;
        }
        const status = e?.response?.status;
        toast.error(
          status === 429
            ? "Terlalu sering mengimpor — tunggu ±1 menit lalu coba lagi"
            : e?.response?.data?.detail
              || "Gagal mengimpor — koneksi terputus; periksa jaringan lalu coba lagi",
          { duration: 9000 });
        setMengunggah(false);
        if (fileRef.current) fileRef.current.value = "";
        return;
      }
    }
    const rk = r.data?.ringkasan || {};
    toast.success(
      `Impor SIMAN selesai: ${rk.aset_dicek || 0} aset dicek — ` +
      `${rk.cocok || 0} cocok, ${rk.selisih || 0} selisih` +
      (rk.siman_tanpa_aset ? `, ${rk.siman_tanpa_aset} baris SIMAN belum tercatat di AMAN` : ""),
      { duration: 8000 });
    (r.data?.peringatan || []).forEach((p) => toast.warning(p, { duration: 12000 }));
    muatRingkasan();
    setSelisih(null);
    if (terbuka) ambilSelisih(1);
    setMengunggah(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const bukaBuatDraft = async (importId) => {
    setDraft({ importId, activities: null, activityId: "", sibuk: false, hasil: null });
    try {
      const r = await axios.get(`${API}/inventory-activities`);
      const items = Array.isArray(r.data) ? r.data : (r.data?.items || []);
      setDraft((d) => d && { ...d, activities: items });
    } catch {
      toast.error("Gagal memuat daftar kegiatan");
      setDraft(null);
    }
  };

  const jalankanBuatDraft = async () => {
    if (!draft?.activityId) { toast.error("Pilih kegiatan tujuan dulu"); return; }
    setDraft((d) => ({ ...d, sibuk: true }));
    try {
      const r = await axios.post(
        `${API}/siman/import/${draft.importId}/buat-draft`,
        { activity_id: draft.activityId });
      const d = r.data || {};
      toast.success(
        `${d.dibuat} aset draft dibuat di kegiatan "${d.kegiatan}"` +
        (d.dilewati_sudah_ada ? ` · ${d.dilewati_sudah_ada} sudah tercatat` : "") +
        (d.sisa ? ` · ${d.sisa} tersisa (jalankan lagi)` : ""),
        { duration: 10000 });
      if ((d.gagal || []).length) toast.warning(`Gagal: ${d.gagal.slice(0, 3).join("; ")}${d.gagal.length > 3 ? "…" : ""}`, { duration: 12000 });
      setDraft((prev) => prev && { ...prev, sibuk: false, hasil: d });
      muatRingkasan();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat draft aset");
      setDraft((prev) => prev && { ...prev, sibuk: false });
    }
  };

  const terapkan = async (aset) => {
    setMenerapkan(aset.id);
    try {
      // Kode barang DIKECUALIKAN dari jalur timpa — reklasifikasi punya
      // jalurnya sendiri (jurnal 304/107 + riwayat); backend menolak bila
      // disertakan (integrasi audit #5).
      const fields = (aset.siman?.selisih || [])
        .map((s) => s.field).filter((f) => f !== "asset_code");
      const r = await axios.post(`${API}/siman/terapkan/${aset.id}`, { fields });
      toast.success(
        `Aset ${aset.asset_code} NUP ${aset.NUP}: ${r.data.diterapkan.length} field disinkronkan ke nilai SIMAN`);
      muatRingkasan();
      ambilSelisih(selisih?.page || 1);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menerapkan nilai SIMAN");
    } finally {
      setMenerapkan(null);
    }
  };

  // Integrasi audit #5: reklasifikasi terdeteksi SIMAN dirutekan ke mesin
  // Reklasifikasi resmi (kode+NUP in-place, jurnal 304/107, riwayat) —
  // bukan sekadar menimpa kode via sinkron.
  const reklasSiman = async (aset, kodeBaru) => {
    const ok = await confirm({
      title: `Reklasifikasi ${aset.asset_code} → ${kodeBaru}?`,
      description:
        "Kode & NUP diperbarui pada aset yang sama (nilai & tanggal perolehan " +
        "tetap); jurnal 304/107 dan riwayat reklasifikasi tercatat di Buku " +
        "Barang. Sumber: kode barang SIMAN berbeda dengan AMAN.",
      confirmLabel: "Reklasifikasi",
    });
    if (!ok) return;
    setMereklas(aset.id);
    try {
      const r = await axios.post(`${API}/pembukuan/reklasifikasi`, {
        asset_id: aset.id, kode_baru: kodeBaru,
        alasan: "Reklasifikasi terdeteksi dari sinkron SIMAN V2" });
      toast.success(`Reklasifikasi tercatat — kode baru ${r.data.kode_baru} · NUP ${r.data.nup_baru}`);
      muatRingkasan();
      ambilSelisih(selisih?.page || 1);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal reklasifikasi");
    } finally {
      setMereklas(null);
    }
  };

  const impor = ringkasan?.import_terakhir;

  return (
    <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="siman-sync-card">
      <div className="px-3 py-2.5 border-b border-border flex items-center gap-2 flex-wrap">
        <span className="w-8 h-8 rounded-lg bg-teal-600 flex items-center justify-center flex-shrink-0">
          <RefreshCcw className="w-4 h-4 text-white" />
        </span>
        <div className="flex-1 min-w-[160px]">
          <p className="text-xs font-semibold text-foreground">Sinkronisasi SIMAN V2</p>
          <p className="text-[10px] text-muted-foreground">
            Impor ekspor &quot;Master Aset&quot; SIMAN (data valid) → aset berbeda ditandai &quot;≠ SIMAN&quot; untuk disinkronkan
          </p>
        </div>
        {ringkasan?.gagal && (
          <button type="button" onClick={muatRingkasan}
            className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-500/15 text-red-600 dark:text-red-400 min-w-0 min-h-0"
            data-testid="siman-ringkas-gagal">
            Status sinkron gagal dimuat — coba lagi
          </button>
        )}
        {ringkasan && !ringkasan.gagal && (
          <div className="flex items-center gap-1.5 flex-wrap" data-testid="siman-ringkas-badge">
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
              {ringkasan.cocok} cocok
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${ringkasan.selisih ? "bg-amber-500/15 text-amber-600 dark:text-amber-400" : "bg-muted text-muted-foreground"}`}>
              {ringkasan.selisih} selisih
            </span>
            {ringkasan.tidak_di_siman > 0 && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-500/15 text-red-600 dark:text-red-400">
                {ringkasan.tidak_di_siman} tak ada di SIMAN
              </span>
            )}
          </div>
        )}
        {isAdmin && (
          <>
            <input ref={fileRef} type="file" accept=".xlsx,.xls" className="hidden"
              onChange={(e) => unggah(e.target.files?.[0])} data-testid="siman-file-input" />
            <Button variant="outline" size="sm" className="gap-1.5" disabled={mengunggah}
              title="Unggah file .xlsx hasil ekspor Master Aset dari SIMAN V2"
              onClick={() => fileRef.current?.click()} data-testid="siman-import-btn">
              {mengunggah ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
              {mengunggah
                ? (persenUnggah > 0 && persenUnggah < 100 ? `Mengunggah ${persenUnggah}%` : "Memproses…")
                : "Impor Ekspor SIMAN"}
            </Button>
          </>
        )}
      </div>

      <div className="px-3 py-2 space-y-2">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <p className="text-[10px] text-muted-foreground">
            {impor
              ? <>Impor terakhir: <b>{String(impor.waktu).slice(0, 10)}</b> · {impor.filename} · {impor.total_baris} baris SIMAN{impor.ringkasan?.siman_tanpa_aset ? <> · <span className="text-amber-600 dark:text-amber-400">{impor.ringkasan.siman_tanpa_aset} baris belum tercatat di AMAN</span></> : null}{impor.register_diadopsi ? <> · {impor.register_diadopsi} kode register diadopsi</> : null}</>
              : "Belum pernah impor — unduh ekspor Master Aset dari SIMAN V2 lalu unggah di sini secara berkala (mis. tiap akhir bulan/semester)."}
          </p>
          {isAdmin && (
            <label className="flex items-center gap-1.5 text-[10px] text-muted-foreground cursor-pointer">
              <input type="checkbox" checked={tandaiHilang}
                onChange={(e) => setTandaiHilang(e.target.checked)}
                className="w-3.5 h-3.5" data-testid="siman-tandai-hilang" />
              Tandai juga aset AMAN yang tidak ada di file (khusus ekspor penuh satker)
            </label>
          )}
        </div>

        {(ringkasan?.selisih || 0) > 0 && (
          <button type="button" onClick={() => setTerbuka((t) => !t)}
            className="w-full flex items-center gap-1.5 text-left text-[11px] font-semibold text-amber-700 dark:text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded-lg px-2.5 py-1.5 min-w-0 min-h-0"
            data-testid="siman-toggle-selisih">
            {terbuka ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            Tinjau {ringkasan.selisih} aset yang berbeda dengan SIMAN
          </button>
        )}

        {terbuka && (
          <div className="border border-border rounded-lg overflow-hidden" data-testid="siman-selisih-list">
            {muatSelisih && !selisih ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="w-5 h-5 animate-spin text-teal-600" />
              </div>
            ) : (selisih?.items || []).length === 0 ? (
              <p className="text-center text-[11px] text-muted-foreground py-4">Tidak ada selisih 🎉</p>
            ) : (
              <div className="divide-y divide-border/60">
                {selisih.items.map((a) => (
                  <div key={a.id} className="px-2.5 py-1.5">
                    <button type="button"
                      onClick={() => setBukaAset(bukaAset === a.id ? null : a.id)}
                      className="w-full flex items-center gap-2 text-left min-w-0 min-h-0"
                      data-testid={`siman-selisih-row-${a.id}`}>
                      {bukaAset === a.id ? <ChevronDown className="w-3 h-3 flex-shrink-0" /> : <ChevronRight className="w-3 h-3 flex-shrink-0" />}
                      <span className="font-mono text-[11px] text-foreground flex-shrink-0">{a.asset_code}·{a.NUP}</span>
                      <span className="text-[11px] text-foreground/80 truncate flex-1">{a.asset_name}</span>
                      <span className="text-[10px] text-amber-600 dark:text-amber-400 font-semibold flex-shrink-0">
                        {(a.siman?.selisih || []).length} field
                      </span>
                    </button>
                    {bukaAset === a.id && (
                      <div className="mt-1.5 ml-5 space-y-1.5">
                        <div className="overflow-x-auto">
                          <table className="text-[10px] w-full min-w-[360px]">
                            <thead>
                              <tr className="text-muted-foreground text-left">
                                <th className="pr-2 py-0.5 font-semibold">Field</th>
                                <th className="pr-2 py-0.5 font-semibold">AMAN (sekarang)</th>
                                <th className="py-0.5 font-semibold">SIMAN (valid)</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(a.siman?.selisih || []).map((s) => (
                                <tr key={s.field} className="border-t border-border/40">
                                  <td className="pr-2 py-0.5 text-foreground/80">{s.label}</td>
                                  <td className="pr-2 py-0.5 text-red-600 dark:text-red-400">{s.aman || "(kosong)"}</td>
                                  <td className="py-0.5 text-emerald-700 dark:text-emerald-400 font-medium">{s.siman || "(kosong)"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        {(() => {
                          const ref = a.siman?.referensi;
                          if (!ref) return null;
                          // Nilai referensi SIMAN (tak dibandingkan, hanya info):
                          // penyusutan & nilai buku dari Penilaian, umur aset dari
                          // kolom "Umur Aset" SIMAN V2 (kini ditampilkan).
                          const bagian = [];
                          if (ref.nilai_penyusutan || ref.nilai_buku) {
                            bagian.push(`penyusutan ${fmtRp(ref.nilai_penyusutan)} · nilai buku ${fmtRp(ref.nilai_buku)}`);
                          }
                          if (ref.umur_aset) bagian.push(`umur aset ${ref.umur_aset}`);
                          return bagian.length ? (
                            <p className="text-[10px] text-muted-foreground">
                              Referensi SIMAN: {bagian.join(" · ")}
                            </p>
                          ) : null;
                        })()}
                        {(() => {
                          const sAC = (a.siman?.selisih || []).find((s) => s.field === "asset_code");
                          const kodeBaru = a.siman?.reklasifikasi?.kode_baru || sAC?.siman || "";
                          const adaLain = (a.siman?.selisih || []).some((s) => s.field !== "asset_code");
                          return (
                            <div className="flex items-center gap-1.5 flex-wrap">
                              {adaLain && (
                                <Button size="sm" variant="outline"
                                  className="h-7 text-[11px] gap-1 text-emerald-700 dark:text-emerald-400 hover:text-emerald-800 dark:hover:text-emerald-300 hover:bg-emerald-500/10"
                                  disabled={menerapkan === a.id}
                                  onClick={() => terapkan(a)}
                                  data-testid={`siman-terapkan-${a.id}`}>
                                  {menerapkan === a.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCcw className="w-3 h-3" />}
                                  Terapkan nilai SIMAN{sAC ? " (selain kode)" : ""}
                                </Button>
                              )}
                              {sAC && kodeBaru && (
                                <Button size="sm" variant="outline"
                                  className="h-7 text-[11px] gap-1 text-fuchsia-700 dark:text-fuchsia-400 hover:bg-fuchsia-500/10"
                                  title="Kode barang SIMAN berbeda — jalankan reklasifikasi resmi (jurnal 304/107 + riwayat), bukan menimpa kode"
                                  disabled={mereklas === a.id}
                                  onClick={() => reklasSiman(a, kodeBaru)}
                                  data-testid={`siman-reklas-${a.id}`}>
                                  {mereklas === a.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Shuffle className="w-3 h-3" />}
                                  Reklasifikasi → {kodeBaru}
                                </Button>
                              )}
                            </div>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
            {selisih && selisih.total_pages > 1 && (
              <div className="flex items-center justify-between px-2.5 py-1.5 border-t border-border bg-muted/30">
                <Button size="sm" variant="ghost" className="h-6 text-[10px]" disabled={selisih.page <= 1 || muatSelisih}
                  onClick={() => ambilSelisih(selisih.page - 1)}>Sebelumnya</Button>
                <span className="text-[10px] text-muted-foreground">Hal {selisih.page}/{selisih.total_pages} · {selisih.total} aset</span>
                <Button size="sm" variant="ghost" className="h-6 text-[10px]" disabled={selisih.page >= selisih.total_pages || muatSelisih}
                  onClick={() => ambilSelisih(selisih.page + 1)}>Berikutnya</Button>
              </div>
            )}
          </div>
        )}

        {(impor?.peringatan || []).map((p, i) => (
          <p key={i} className="flex items-start gap-1.5 text-[10px] text-amber-700 dark:text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded-lg px-2.5 py-1.5"
            data-testid="siman-peringatan">
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-px" />{p}
          </p>
        ))}

        {impor?.ringkasan?.siman_tanpa_aset > 0 && (
          <div className="rounded-lg border border-border bg-muted/30 px-2.5 py-2 space-y-1.5" data-testid="siman-belum-tercatat">
            <p className="text-[10px] text-muted-foreground">
              <b className="text-foreground">{impor.ringkasan.siman_tanpa_aset} baris SIMAN belum tercatat di AMAN</b> —
              datanya (kode, NUP, nama, merk, nilai, register) bisa langsung dijadikan aset draft
              untuk dilengkapi foto &amp; lokasi di lapangan, atau diunduh sebagai CSV.
            </p>
            <div className="flex items-center gap-1.5 flex-wrap">
              <Button size="sm" variant="outline" className="h-7 text-[11px] gap-1 min-h-0"
                title="Unduh daftar baris SIMAN yang belum tercatat (CSV)"
                onClick={() => downloadFileWithProgress(
                  `${API}/siman/import/${impor.id}/belum-tercatat.csv`,
                  "siman_belum_tercatat.csv",
                  { label: "CSV baris SIMAN belum tercatat" }).catch(() => {})}
                data-testid="siman-csv-belum">
                <FileDown className="w-3 h-3" />CSV
              </Button>
              {isAdmin && !draft && (
                <Button size="sm" className="h-7 text-[11px] gap-1 min-h-0 bg-teal-600 hover:bg-teal-700 text-white"
                  title="Buat aset draft massal dari baris SIMAN yang belum tercatat"
                  onClick={() => bukaBuatDraft(impor.id)} data-testid="siman-buat-draft-btn">
                  <PackagePlus className="w-3 h-3" />Buat Draft Aset
                </Button>
              )}
            </div>
            {draft && (
              <div className="flex items-center gap-1.5 flex-wrap pt-1 border-t border-border/60">
                {draft.activities === null ? (
                  <Loader2 className="w-4 h-4 animate-spin text-teal-600" />
                ) : (
                  <>
                    <select value={draft.activityId}
                      onChange={(e) => setDraft((d) => ({ ...d, activityId: e.target.value }))}
                      className="h-8 rounded-md border border-input bg-background px-2 text-[11px] min-w-[160px] flex-1"
                      data-testid="siman-draft-kegiatan">
                      <option value="">— Pilih kegiatan tujuan —</option>
                      {draft.activities.map((a) => (
                        <option key={a.id} value={a.id}>{a.nama_kegiatan || a.id}</option>
                      ))}
                    </select>
                    <Button size="sm" className="h-8 text-[11px] gap-1 min-h-0 bg-teal-600 hover:bg-teal-700 text-white"
                      disabled={draft.sibuk || !draft.activityId} onClick={jalankanBuatDraft}
                      data-testid="siman-draft-jalankan">
                      {draft.sibuk ? <Loader2 className="w-3 h-3 animate-spin" /> : <PackagePlus className="w-3 h-3" />}
                      Buat
                    </Button>
                    <Button size="sm" variant="outline" className="h-8 text-[11px] min-h-0"
                      disabled={draft.sibuk} onClick={() => setDraft(null)}>Tutup</Button>
                  </>
                )}
                {draft.hasil && (
                  <p className="basis-full text-[10px] text-emerald-700 dark:text-emerald-400">
                    {draft.hasil.dibuat} draft dibuat{draft.hasil.sisa ? ` — ${draft.hasil.sisa} tersisa, klik Buat lagi` : " — selesai"}
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
      {confirmDialog}
    </div>
  );
}
