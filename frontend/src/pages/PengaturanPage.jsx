import React, { useCallback, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Building2, ChevronRight, DatabaseBackup, Globe2, Landmark,
  Loader2, Mail, CalendarClock, Settings as SettingsIcon, ShieldAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useBackGuard } from "@/hooks/useBackGuard";
import { getApiError } from "../lib/utils";
import ReportSettingsEditor from "@/components/assets/ReportSettingsEditor";
import { SatkerPanel } from "./SatkerPage";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Pengaturan Terpadu — SATU pintu seluruh setelan aplikasi (Mandat-2):
 *  - Universal : kop/logo/judul laporan global (report_settings) — berlaku
 *    untuk semua satker KECUALI di-override per satker.
 *  - Per-Satker: master satker + kop per-satker (menimpa universal).
 *  - Lainnya   : pintasan setelan yang hidup di modulnya (persuratan,
 *    akuntansi/ambang, periode pelaporan) supaya tetap satu pintu.
 *  - Sistem    : backup data (job background); restore/reset di halaman
 *    pemilihan kegiatan (aksi berbahaya sengaja tidak dipindah).
 */
export default function PengaturanPage({ user, onBack, onOpenSatker,
  onOpenReferensiAkun, onOpenPersuratan, onOpenPelaporan }) {
  const isAdmin = user?.role === "admin";
  const [tab, setTab] = useState("universal"); // universal | satker | sistem
  const [backupLoading, setBackupLoading] = useState(false);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const mulaiBackup = async () => {
    setBackupLoading(true);
    try {
      await axios.post(`${API}/backup/start`, {}, { timeout: 30000 });
      toast.success("Backup dimulai di background — progres di panel kanan bawah, hasil ZIP siap diunduh setelah selesai.");
    } catch (e) {
      toast.error(getApiError(e, "Gagal memulai backup"));
    } finally {
      setBackupLoading(false);
    }
  };

  const TABS = [
    ["universal", "Universal", Globe2],
    ["satker", "Per-Satker", Building2],
    ["sistem", "Sistem", DatabaseBackup],
  ];

  const pintasan = [
    onOpenPersuratan && {
      label: "Persuratan — format nomor & kode klasifikasi",
      desc: "Template nomor naskah dinas, kode unit, peta klasifikasi otomatis.",
      Icon: Mail, onClick: onOpenPersuratan,
    },
    onOpenReferensiAkun && {
      label: "Akuntansi BMN — akun BAS, pemetaan & ambang kapitalisasi",
      desc: "Master segmen akun, akun aset/persediaan, ambang intra/ekstra PMK 181.",
      Icon: Landmark, onClick: onOpenReferensiAkun,
    },
    onOpenPelaporan && {
      label: "Pelaporan — periode & tenggat",
      desc: "Daftar periode, kunci/final, tenggat penyampaian laporan.",
      Icon: CalendarClock, onClick: onOpenPelaporan,
    },
  ].filter(Boolean);

  return (
    <div className="min-h-screen bg-background" data-testid="pengaturan-page">
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pengaturan-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-slate-700 flex items-center justify-center flex-shrink-0">
            <SettingsIcon className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Pengaturan</h1>
            <p className="text-[11px] text-muted-foreground leading-tight truncate">
              Satu pintu: universal → dapat di-override per-satker → sistem
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        <div className="flex bg-muted rounded-lg p-0.5 gap-0.5">
          {TABS.map(([k, label, Icon]) => (
            <button key={k} type="button" onClick={() => setTab(k)}
              className={`flex-1 text-[11px] sm:text-xs font-semibold py-1.5 rounded-md transition-colors flex items-center justify-center gap-1.5 min-w-0 min-h-0 ${tab === k ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
              data-testid={`pengaturan-tab-${k}`}>
              <Icon className="w-3.5 h-3.5" />{label}
            </button>
          ))}
        </div>

        {tab === "universal" && (
          <div className="space-y-3">
            <p className="text-[11px] text-muted-foreground px-1">
              Setelan <b>universal</b> berlaku untuk seluruh aplikasi & semua satker.
              Field kop yang diisi pada tab <b>Per-Satker</b> menimpa nilai di sini untuk laporan satker ybs.
            </p>
            <ReportSettingsEditor onClose={onBack} />
            {pintasan.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wide px-1">Setelan universal lainnya</p>
                {pintasan.map(({ label, desc, Icon, onClick }) => (
                  <button key={label} type="button" onClick={onClick}
                    className="w-full text-left rounded-xl border border-border bg-card p-3 hover:bg-muted/60 transition-colors flex items-center gap-3 min-w-0 min-h-0">
                    <Icon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs font-semibold text-foreground">{label}</span>
                      <span className="block text-[10px] text-muted-foreground">{desc}</span>
                    </span>
                    <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "satker" && (
          <div className="space-y-2">
            <p className="text-[11px] text-muted-foreground px-1">
              Kop per-satker <b>menimpa</b> setelan universal untuk laporan kegiatan satker ybs.
              Resolusi: kegiatan → satker → universal.
              {onOpenSatker && (
                <> {" "}Halaman penuh: <button type="button" className="underline font-semibold min-w-0 min-h-0" onClick={onOpenSatker}>Master Satker</button>.</>
              )}
            </p>
            <SatkerPanel user={user} />
          </div>
        )}

        {tab === "sistem" && (
          <div className="space-y-2.5">
            <div className="rounded-xl border border-border bg-card p-3.5 space-y-2">
              <p className="text-xs font-bold flex items-center gap-1.5">
                <DatabaseBackup className="w-4 h-4" />Backup seluruh data
              </p>
              <p className="text-[11px] text-muted-foreground">
                Mencadangkan SEMUA koleksi data + berkas (GridFS/unggahan) menjadi satu ZIP —
                daftar koleksi dinamis, modul baru otomatis ikut. Proses berjalan di background.
              </p>
              <Button size="sm" className="h-9 text-xs" disabled={!isAdmin || backupLoading}
                onClick={mulaiBackup} data-testid="pengaturan-backup">
                {backupLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <DatabaseBackup className="w-3.5 h-3.5 mr-1.5" />}
                Mulai Backup Sekarang
              </Button>
              {!isAdmin && <p className="text-[10px] text-amber-600 dark:text-amber-400">Hanya admin yang dapat menjalankan backup.</p>}
            </div>
            <div className="rounded-xl border border-border bg-card p-3.5 space-y-1.5">
              <p className="text-xs font-bold flex items-center gap-1.5">
                <ShieldAlert className="w-4 h-4 text-amber-500" />Pulihkan (restore) & Reset data
              </p>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Kedua aksi ini <b>mengganti/menghapus data secara permanen</b>, sehingga sengaja
                tetap berada di halaman pemilihan kegiatan (modul Inventarisasi) dengan konfirmasi
                berlapis. Reset TIDAK menghapus akun & seluruh setelan/pemetaan (kop, satker,
                akun BAS, masa manfaat, ambang, persuratan) — semuanya selamat.
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
