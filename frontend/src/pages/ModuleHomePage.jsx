import React, { useMemo, useState } from "react";
import {
  Package, Moon, Sun, LogOut, ChevronRight, Lock, Sparkles,
  ClipboardList, ShoppingCart, UserCheck, Handshake, ShieldCheck, Scale,
  ArrowLeftRight, Flame, FileX, Eye, BookOpen, Boxes, FileText, ClipboardCheck,
  CheckCircle2, Link2, CalendarClock, Banknote, Wrench, Landmark,
} from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useTripleClick } from "@/hooks/useTripleClick";
import {
  SIKLUS_MODULES, PENATAUSAHAAN_SUBMODULES, FASE_ROADMAP, STATUS_LABELS,
  ASAS_PENGELOLAAN, DASAR_HUKUM_UMUM, PENATAUSAHAAN_DASAR_HUKUM,
} from "@/lib/bmnModules";

// Ikon per modul — dipetakan di sini supaya registry (lib) bebas dependensi UI.
const MODULE_ICONS = {
  "perencanaan": ClipboardList,
  "penganggaran": Banknote,
  "pengadaan": ShoppingCart,
  "penggunaan": UserCheck,
  "pemanfaatan": Handshake,
  "penilaian": Scale,
  "pengamanan": ShieldCheck,
  "pemeliharaan": Wrench,
  "pemindahtanganan": ArrowLeftRight,
  "pemusnahan": Flame,
  "penghapusan": FileX,
  "wasdal": Eye,
  "pembukuan": BookOpen,
  "inventarisasi-aset": ClipboardCheck,
  "inventarisasi-persediaan": Boxes,
  "pelaporan": FileText,
};

const STATUS_BADGE_CLS = {
  aktif: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
  sebagian: "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30",
  segera: "bg-slate-500/10 text-muted-foreground border-border",
};

function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-semibold ${STATUS_BADGE_CLS[status]}`}>
      {status === "aktif" ? <CheckCircle2 className="w-3 h-3" /> : status === "segera" ? <Lock className="w-3 h-3" /> : <Sparkles className="w-3 h-3" />}
      {STATUS_LABELS[status]}
    </span>
  );
}

/**
 * Beranda Modul — "rumah" Siklus Pengelolaan BMN (PP 27/2014).
 *
 * Penatausahaan › Inventarisasi Aset adalah modul AKTIF (aplikasi saat ini);
 * tahap siklus lain sudah punya kamarnya masing-masing dengan status Segera
 * Hadir — klik kartunya menampilkan konsep, rencana fitur, dan fase roadmap.
 */
export default function ModuleHomePage({ user, onLogout, dark, toggleDark, onShowInfo, onEnterInventarisasi }) {
  const [detail, setDetail] = useState(null); // modul yang dibuka konsepnya
  const activateInfo = useTripleClick(onShowInfo);
  const DetailIcon = detail ? (MODULE_ICONS[detail.id] || Package) : null;

  const siklusSorted = useMemo(
    () => [...SIKLUS_MODULES].sort((a, b) => a.urutan - b.urutan),
    [],
  );

  const openModule = (mod) => {
    if (mod.id === "inventarisasi-aset") onEnterInventarisasi();
    else setDetail(mod);
  };

  return (
    <div className="min-h-screen bg-background" data-testid="module-home">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-6xl mx-auto flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-blue-500 flex items-center justify-center shadow-sm cursor-pointer flex-shrink-0"
            {...(onShowInfo ? { onClick: activateInfo, title: "" } : {})}
          >
            <Package className="w-5 h-5 text-white" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">AMAN — Manajemen Aset Negara</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Siklus Pengelolaan BMN · {user?.full_name || user?.username}
            </p>
          </div>
          <button
            type="button"
            onClick={toggleDark}
            aria-label={dark ? "Mode terang" : "Mode gelap"}
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-accent flex-shrink-0"
            data-testid="module-home-theme"
          >
            {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
          <button
            type="button"
            onClick={onLogout}
            className="h-9 px-3 rounded-lg border border-border text-foreground/80 text-xs font-medium flex items-center gap-1.5 hover:bg-accent flex-shrink-0"
            data-testid="module-home-logout"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Keluar</span>
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-3 sm:px-6 py-5 sm:py-8 space-y-6">
        {/* ── Sambutan + posisi ── */}
        <div className="text-center space-y-2">
          <h2 className="text-xl sm:text-2xl font-bold text-foreground">Siklus Pengelolaan BMN</h2>
          <p className="text-xs sm:text-sm text-muted-foreground max-w-2xl mx-auto">
            Satu rumah untuk 12 tahap pengelolaan Barang Milik Negara sesuai siklus resmi
            Kemenkeu ({DASAR_HUKUM_UMUM.join(" · ")}). Modul dibangun bertahap — mulai dari
            poros penatausahaan.
          </p>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-600/10 border border-blue-500/30 text-blue-600 dark:text-blue-400 text-[11px] font-semibold">
            Posisi Anda: Penatausahaan › Inventarisasi Aset
          </span>
          {/* Asas pengelolaan — legenda diagram resmi */}
          <div className="flex items-center justify-center gap-1.5 flex-wrap pt-1">
            {ASAS_PENGELOLAAN.map((asas) => (
              <span key={asas} className="px-2 py-0.5 rounded-full bg-muted/70 border border-border text-[10px] text-muted-foreground">
                {asas}
              </span>
            ))}
          </div>
        </div>

        {/* ── Penatausahaan — poros (posisi kita) ── */}
        <section className="bg-card rounded-2xl border-2 border-blue-500/40 shadow-sm p-3 sm:p-5" data-testid="module-penatausahaan">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
              <BookOpen className="w-4 h-4 text-white" />
            </span>
            <div>
              <h3 className="font-bold text-foreground text-sm sm:text-base leading-tight">Penatausahaan</h3>
              <p className="text-[11px] sm:text-xs text-muted-foreground">
                Pembukuan · Inventarisasi · Pelaporan — poros pencatatan seluruh siklus
                <span className="hidden sm:inline"> · {PENATAUSAHAAN_DASAR_HUKUM.split(" — ")[0]}</span>
              </p>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 mt-3">
            {PENATAUSAHAAN_SUBMODULES.map((mod) => {
              const Icon = MODULE_ICONS[mod.id] || Package;
              const aktif = mod.id === "inventarisasi-aset";
              return (
                <button
                  key={mod.id}
                  type="button"
                  onClick={() => openModule(mod)}
                  data-testid={`module-card-${mod.id}`}
                  className={`text-left rounded-xl border p-3 transition-all group ${
                    aktif
                      ? "border-emerald-500/50 bg-emerald-500/5 hover:bg-emerald-500/10 hover:shadow-md"
                      : "border-border bg-background hover:bg-accent hover:shadow-sm"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${aktif ? "bg-emerald-600" : "bg-muted"}`}>
                      <Icon className={`w-4 h-4 ${aktif ? "text-white" : "text-muted-foreground"}`} />
                    </span>
                    <StatusBadge status={mod.status} />
                  </div>
                  <p className="font-semibold text-foreground text-xs sm:text-sm leading-tight">{mod.nama}</p>
                  <p className="text-[11px] text-muted-foreground mt-1 leading-snug">{mod.ringkas}</p>
                  {aktif && (
                    <span className="mt-2 inline-flex items-center gap-1 text-[11px] font-bold text-emerald-600 dark:text-emerald-400 group-hover:gap-1.5 transition-all">
                      Masuk Modul <ChevronRight className="w-3.5 h-3.5" />
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </section>

        {/* ── Tahap siklus lainnya ── */}
        <section>
          <div className="flex items-center gap-2 mb-3 px-1">
            <h3 className="font-bold text-foreground text-sm sm:text-base">Tahap Siklus Lainnya</h3>
            <span className="text-[11px] text-muted-foreground">— kamar sudah disiapkan, modul menyusul bertahap</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
            {siklusSorted.map((mod) => {
              const Icon = MODULE_ICONS[mod.id] || Package;
              return (
                <button
                  key={mod.id}
                  type="button"
                  onClick={() => openModule(mod)}
                  data-testid={`module-card-${mod.id}`}
                  className="text-left rounded-xl border border-border bg-card p-3 hover:bg-accent hover:shadow-sm transition-all"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="w-9 h-9 rounded-lg bg-muted flex items-center justify-center flex-shrink-0 relative">
                      <Icon className="w-4 h-4 text-muted-foreground" />
                      <span className="absolute -top-1.5 -left-1.5 w-4 h-4 rounded-full bg-blue-600 text-white text-[9px] font-bold flex items-center justify-center">
                        {mod.urutan}
                      </span>
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-semibold text-foreground text-xs sm:text-sm leading-tight truncate">{mod.nama}</p>
                        <StatusBadge status={mod.status} />
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug line-clamp-2">{mod.ringkas}</p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        <p className="text-center text-[11px] text-muted-foreground pb-4">
          Klik modul mana pun untuk melihat konsep & rencana fiturnya. Roadmap lengkap: docs/MASTERPLAN-SIKLUS-BMN.md
        </p>
      </main>

      {/* ── Dialog konsep modul (Segera Hadir) ── */}
      <Dialog open={!!detail} onOpenChange={(o) => { if (!o) setDetail(null); }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          {detail && (
            <>
              <DialogHeader>
                <div className="flex items-center gap-2.5">
                  <span className="w-10 h-10 rounded-xl bg-muted flex items-center justify-center flex-shrink-0">
                    {DetailIcon && <DetailIcon className="w-5 h-5 text-muted-foreground" />}
                  </span>
                  <div className="min-w-0 text-left">
                    <DialogTitle className="text-base leading-tight">{detail.nama}</DialogTitle>
                    <div className="mt-1"><StatusBadge status={detail.status} /></div>
                  </div>
                </div>
                <DialogDescription className="text-left pt-2 text-xs leading-relaxed">
                  {detail.deskripsi}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-3 text-left">
                <div>
                  <p className="text-xs font-bold text-foreground mb-1.5 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-blue-500" />Fitur yang direncanakan
                  </p>
                  <ul className="space-y-1">
                    {detail.fitur.map((f, i) => (
                      <li key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0 mt-0.5" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                {detail.integrasi?.length > 0 && (
                  <div>
                    <p className="text-xs font-bold text-foreground mb-1.5 flex items-center gap-1.5">
                      <Link2 className="w-3.5 h-3.5 text-violet-500" />Terintegrasi dengan modul lain
                    </p>
                    <ul className="space-y-1">
                      {detail.integrasi.map((f, i) => (
                        <li key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
                          <span className="text-violet-500 mt-0.5">•</span>
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {detail.dasarHukum?.length > 0 && (
                  <div>
                    <p className="text-xs font-bold text-foreground mb-1.5 flex items-center gap-1.5">
                      <Landmark className="w-3.5 h-3.5 text-amber-500" />Dasar hukum
                    </p>
                    <ul className="space-y-1">
                      {detail.dasarHukum.map((f, i) => (
                        <li key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
                          <span className="text-amber-500 mt-0.5">•</span>
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="rounded-lg bg-muted/60 border border-border px-3 py-2 flex items-start gap-2">
                  <CalendarClock className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
                  <p className="text-[11px] text-muted-foreground leading-snug">{FASE_ROADMAP[detail.fase]}</p>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
