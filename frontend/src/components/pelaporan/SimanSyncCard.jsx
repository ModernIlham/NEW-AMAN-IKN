import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ChevronDown, ChevronRight, Loader2, RefreshCcw, Upload,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

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
  const [tandaiHilang, setTandaiHilang] = useState(false);
  const [terbuka, setTerbuka] = useState(false);
  const [selisih, setSelisih] = useState(null); // {items,total,page,total_pages}
  const [muatSelisih, setMuatSelisih] = useState(false);
  const [bukaAset, setBukaAset] = useState(null); // id aset yang rinciannya terbuka
  const [menerapkan, setMenerapkan] = useState(null); // id aset yang sedang diterapkan
  const fileRef = useRef(null);

  const muatRingkasan = useCallback(() => {
    axios.get(`${API}/siman/ringkasan`)
      .then((r) => setRingkasan(r.data))
      .catch(() => {});
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
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await axios.post(
        `${API}/siman/import?tandai_tidak_ditemukan=${tandaiHilang}`, fd,
        { headers: { "Content-Type": "multipart/form-data" } });
      const rk = r.data?.ringkasan || {};
      toast.success(
        `Impor SIMAN selesai: ${rk.aset_dicek || 0} aset dicek — ` +
        `${rk.cocok || 0} cocok, ${rk.selisih || 0} selisih` +
        (rk.siman_tanpa_aset ? `, ${rk.siman_tanpa_aset} baris SIMAN belum tercatat di AMAN` : ""),
        { duration: 8000 });
      muatRingkasan();
      setSelisih(null);
      if (terbuka) ambilSelisih(1);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengimpor file SIMAN");
    } finally {
      setMengunggah(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const terapkan = async (aset) => {
    setMenerapkan(aset.id);
    try {
      const r = await axios.post(`${API}/siman/terapkan/${aset.id}`, {});
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
        {ringkasan && (
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
              onClick={() => fileRef.current?.click()} data-testid="siman-import-btn">
              {mengunggah ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
              Impor Ekspor SIMAN
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
                        {a.siman?.referensi && (a.siman.referensi.nilai_penyusutan || a.siman.referensi.nilai_buku) ? (
                          <p className="text-[10px] text-muted-foreground">
                            Referensi SIMAN: penyusutan {fmtRp(a.siman.referensi.nilai_penyusutan)} · nilai buku {fmtRp(a.siman.referensi.nilai_buku)}
                          </p>
                        ) : null}
                        <Button size="sm" variant="outline"
                          className="h-7 text-[11px] gap-1 text-emerald-700 dark:text-emerald-400 hover:text-emerald-800 dark:hover:text-emerald-300 hover:bg-emerald-500/10"
                          disabled={menerapkan === a.id}
                          onClick={() => terapkan(a)}
                          data-testid={`siman-terapkan-${a.id}`}>
                          {menerapkan === a.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCcw className="w-3 h-3" />}
                          Terapkan nilai SIMAN
                        </Button>
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

        {impor?.ringkasan?.siman_tanpa_aset > 0 && (
          <p className="text-[10px] text-muted-foreground">
            💡 {impor.ringkasan.siman_tanpa_aset} baris SIMAN belum tercatat di AMAN — tambahkan lewat
            impor aset (menu Inventarisasi) atau draft aset dari Pengadaan agar daftar AMAN selengkap SIMAN.
          </p>
        )}
      </div>
    </div>
  );
}
