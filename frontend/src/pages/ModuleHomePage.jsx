import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  Package, Moon, Sun, LogOut, ChevronRight, Lock, Sparkles,
  ClipboardList, ShoppingCart, UserCheck, Handshake, ShieldCheck, Scale,
  ArrowLeftRight, Flame, FileX, Eye, BookOpen, Boxes, FileText, ClipboardCheck,
  CheckCircle2, Link2, CalendarClock, Banknote, Wrench, Landmark, ListTree,
  Users, DoorOpen, IdCard, Mail, FileSignature, Building2, Settings,
} from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useTripleClick } from "@/hooks/useTripleClick";
import {
  SIKLUS_MODULES, PENATAUSAHAAN_SUBMODULES, FASE_ROADMAP, STATUS_LABELS,
  ASAS_PENGELOLAAN, DASAR_HUKUM_UMUM, PENATAUSAHAAN_DASAR_HUKUM,
} from "@/lib/bmnModules";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

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

// Aksen warna ikon per modul — PALET DINGIN PROFESIONAL & KOHESIF:
// keluarga biru–indigo–sky–cyan–teal–slate saja (analog, selaras warna
// merek biru/indigo), tanpa warna hangat/mencolok agar tidak seperti
// pelangi. Perbedaan halus per fase menjaga modul tetap mudah dikenali;
// tahap "pelepasan" (pemindahtanganan/pemusnahan/penghapusan) memakai
// slate netral. Aman di light & dark.
const MODULE_TILE = {
  "perencanaan": "from-sky-500 to-blue-600",
  "penganggaran": "from-blue-500 to-indigo-600",
  "pengadaan": "from-cyan-600 to-blue-600",
  "penggunaan": "from-teal-600 to-cyan-700",
  "pemanfaatan": "from-cyan-600 to-teal-700",
  "penilaian": "from-indigo-500 to-blue-700",
  "pengamanan": "from-blue-600 to-indigo-700",
  "pemeliharaan": "from-sky-600 to-cyan-700",
  "pemindahtanganan": "from-slate-500 to-slate-700",
  "pemusnahan": "from-slate-600 to-slate-800",
  "penghapusan": "from-slate-500 to-slate-600",
  "wasdal": "from-indigo-600 to-blue-700",
  "pembukuan": "from-blue-600 to-indigo-700",
  "inventarisasi-aset": "from-blue-700 to-indigo-700",
  "inventarisasi-persediaan": "from-sky-600 to-blue-700",
  "pelaporan": "from-indigo-600 to-blue-700",
};

// Animasi idle HALUS per ikon Peta Siklus — dipilih sesuai MAKNA ikon
// (timbangan bergoyang, perisai/mata berdenyut, kunci-inggris berputar,
// panah pindah & keranjang bergeser, api berkobar; sisanya mengapung
// lembut). Kelas didefinisikan di index.css (.ikon-*). Default: mengapung.
const MODULE_ANIM = {
  "perencanaan": "ikon-apung",
  "penganggaran": "ikon-apung",
  "pengadaan": "ikon-geser",
  "penggunaan": "ikon-apung",
  "pemanfaatan": "ikon-apung",
  "penilaian": "ikon-ayun",
  "pengamanan": "ikon-denyut",
  "pemeliharaan": "ikon-putar",
  "pemindahtanganan": "ikon-geser",
  "pemusnahan": "ikon-kobar",
  "penghapusan": "ikon-apung",
  "wasdal": "ikon-denyut",
  "pembukuan": "ikon-apung",
  "inventarisasi-aset": "ikon-apung",
  "inventarisasi-persediaan": "ikon-apung",
  "pelaporan": "ikon-apung",
};

// Kelas animasi + delay STAGGER stabil dari id (agar ikon tak serempak,
// terkesan bergelombang). Dipakai di semua titik render ikon modul.
function ikonAnim(id) {
  const kelas = MODULE_ANIM[id] || "ikon-apung";
  let h = 0;
  for (let i = 0; i < (id || "").length; i++) h = (h + id.charCodeAt(i)) % 13;
  return { className: kelas, style: { animationDelay: `${(h * 0.16).toFixed(2)}s` } };
}

// Tiga fase alur siklus (urutan modul mengikuti registry) — Wasdal terpisah
// sebagai pita pengawasan yang MELINGKUPI seluruh siklus.
const FASE_ALUR = [
  { id: "perolehan", judul: "Perolehan", sub: "dari rencana menjadi barang",
    aksen: "text-sky-600 dark:text-sky-400", garis: "border-sky-500/40",
    ids: ["perencanaan", "penganggaran", "pengadaan"] },
  { id: "pengelolaan", judul: "Penggunaan & Pengelolaan", sub: "barang bekerja & terjaga",
    aksen: "text-emerald-600 dark:text-emerald-400", garis: "border-emerald-500/40",
    ids: ["penggunaan", "pemanfaatan", "penilaian", "pengamanan", "pemeliharaan"] },
  { id: "pengakhiran", judul: "Pengakhiran", sub: "keluar daftar secara sah",
    aksen: "text-rose-600 dark:text-rose-400", garis: "border-rose-500/40",
    ids: ["pemindahtanganan", "pemusnahan", "penghapusan"] },
];

const STATUS_BADGE_CLS = {
  aktif: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
  segera: "bg-slate-500/10 text-muted-foreground border-border",
};

function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-semibold ${STATUS_BADGE_CLS[status] || STATUS_BADGE_CLS.aktif}`}>
      {status === "segera" ? <Lock className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
      {STATUS_LABELS[status] || "Aktif"}
    </span>
  );
}

function fmtRpSingkat(v) {
  const n = Number(v || 0);
  if (n >= 1e12) return `Rp${(n / 1e12).toFixed(1)} T`;
  if (n >= 1e9) return `Rp${(n / 1e9).toFixed(1)} M`;
  if (n >= 1e6) return `Rp${(n / 1e6).toFixed(1)} jt`;
  try { return `Rp${Math.round(n).toLocaleString("id-ID")}`; } catch { return `Rp${n}`; }
}

/**
 * Beranda Modul — "Peta Perjalanan Siklus BMN" (PP 27/2014 jo. PP 28/2020).
 *
 * Desain: hero ber-gradien + statistik hidup dari master, tiga FASE alur
 * ber-timeline bernomor (Perolehan → Penggunaan & Pengelolaan → Pengakhiran),
 * pita Wasdal yang melingkupi siklus, dan POROS Penatausahaan di tengah.
 * Seluruh warna memakai token tema + varian dark: (aman light/dark mode).
 */
export default function ModuleHomePage({ user, onLogout, dark, toggleDark, onShowInfo, onEnterInventarisasi, onOpenKodefikasi, onOpenPejabat, onOpenRuangan, onOpenReferensiAkun, onOpenPegawai, onOpenPersuratan, onOpenPersediaan, onOpenPelaporan, onOpenPenggunaan, onOpenPengamanan, onOpenPemeliharaan, onOpenPerencanaan, onOpenPenilaian, onOpenPenghapusan, onOpenPemanfaatan, onOpenPemusnahan, onOpenPemindahtanganan, onOpenWasdal, onOpenPenganggaran, onOpenPengadaan, onOpenTtd, onOpenSatker, onOpenPengaturan, onOpenPembukuan }) {
  const [detail, setDetail] = useState(null); // modul yang dibuka konsepnya
  const [stat, setStat] = useState(null);     // statistik hidup dari master
  const activateInfo = useTripleClick(onShowInfo);
  const DetailIcon = detail ? (MODULE_ICONS[detail.id] || Package) : null;

  // Statistik hidup: total aset & nilai per satker dari referensi akun BAS
  // (endpoint ringan yang sudah menautkan master) — gagal senyap, hero tetap
  // tampil tanpa angka.
  useEffect(() => {
    axios.get(`${API}/akun-bas`).then((r) => {
      const items = r.data?.items || [];
      setStat({
        aset: r.data?.total_aset || 0,
        nilai: items.reduce((a, i) => a + (Number(i.nilai_aset) || 0), 0),
      });
    }).catch(() => {});
  }, []);

  const petaModul = useMemo(() => {
    const m = {};
    for (const mod of SIKLUS_MODULES) m[mod.id] = mod;
    return m;
  }, []);

  const openModule = (mod) => {
    if (mod.id === "inventarisasi-aset") onEnterInventarisasi();
    else if (mod.id === "inventarisasi-persediaan" && onOpenPersediaan) onOpenPersediaan();
    else if (mod.id === "pelaporan" && onOpenPelaporan) onOpenPelaporan();
    else if (mod.id === "pembukuan" && onOpenPembukuan) onOpenPembukuan();
    else if (mod.id === "penggunaan" && onOpenPenggunaan) onOpenPenggunaan();
    else if (mod.id === "pengamanan" && onOpenPengamanan) onOpenPengamanan();
    else if (mod.id === "pemeliharaan" && onOpenPemeliharaan) onOpenPemeliharaan();
    else if (mod.id === "perencanaan" && onOpenPerencanaan) onOpenPerencanaan();
    else if (mod.id === "penilaian" && onOpenPenilaian) onOpenPenilaian();
    else if (mod.id === "penghapusan" && onOpenPenghapusan) onOpenPenghapusan();
    else if (mod.id === "pemanfaatan" && onOpenPemanfaatan) onOpenPemanfaatan();
    else if (mod.id === "pemusnahan" && onOpenPemusnahan) onOpenPemusnahan();
    else if (mod.id === "pemindahtanganan" && onOpenPemindahtanganan) onOpenPemindahtanganan();
    else if (mod.id === "wasdal" && onOpenWasdal) onOpenWasdal();
    else if (mod.id === "penganggaran" && onOpenPenganggaran) onOpenPenganggaran();
    else if (mod.id === "pengadaan" && onOpenPengadaan) onOpenPengadaan();
    else setDetail(mod);
  };

  // Baris modul di timeline fase — ringkas, informatif, satu klik langsung.
  const BarisModul = ({ mod }) => {
    const Icon = MODULE_ICONS[mod.id] || Package;
    const anim = ikonAnim(mod.id);
    return (
      <button
        type="button"
        onClick={() => openModule(mod)}
        data-testid={`module-card-${mod.id}`}
        className="relative w-full text-left pl-9 pr-2 py-2 rounded-xl hover:bg-muted/70 transition-colors group min-w-0 min-h-0"
      >
        {/* Nomor tahap di atas garis timeline */}
        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-card border-2 border-border text-[10px] font-bold text-foreground/70 flex items-center justify-center group-hover:border-blue-500/60 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
          {mod.urutan}
        </span>
        <span className="flex items-center gap-2.5 min-w-0">
          <span className={`w-9 h-9 rounded-xl bg-gradient-to-br ${MODULE_TILE[mod.id] || "from-slate-500 to-slate-600"} flex items-center justify-center flex-shrink-0 shadow-sm group-hover:scale-105 transition-transform`}>
            <Icon className={`w-4 h-4 text-white ${anim.className}`} style={anim.style} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-semibold text-foreground text-[13px] leading-tight truncate">{mod.nama}</span>
            <span className="block text-[10px] text-muted-foreground leading-snug line-clamp-1">{mod.ringkas}</span>
          </span>
          <ChevronRight className="w-4 h-4 text-muted-foreground/50 group-hover:text-blue-500 group-hover:translate-x-0.5 transition-all flex-shrink-0" />
        </span>
      </button>
    );
  };

  // Pintasan referensi/alat — satu komponen agar seragam & ringkas.
  const Pintasan = ({ onClick, testid, icon: Icon, warna, label }) => (
    <button
      type="button"
      onClick={onClick}
      className="w-full inline-flex items-center gap-1.5 px-3 h-8 rounded-full border border-border bg-muted/40 text-foreground text-[11px] font-semibold hover:bg-muted hover:border-blue-500/40 transition-colors min-w-0 min-h-0"
      data-testid={testid}
    >
      <span className="flex items-center gap-1.5 min-w-0 flex-1">
        <Icon className={`w-3.5 h-3.5 ${warna} flex-shrink-0`} />
        <span className="truncate">{label}</span>
      </span>
      <ChevronRight className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
    </button>
  );

  const wasdal = petaModul["wasdal"];

  return (
    <div className="min-h-screen bg-background" data-testid="module-home">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center gap-2 sm:gap-3 gap-y-2">
          <div
            className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-sm cursor-pointer flex-shrink-0"
            {...(onShowInfo ? { onClick: activateInfo, title: "" } : {})}
          >
            <Package className="w-5 h-5 text-white" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight truncate">AMAN — Manajemen Aset Negara</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Siklus Pengelolaan BMN · {user?.full_name || user?.username}
            </p>
          </div>
          <button
            type="button"
            onClick={toggleDark}
            aria-label={dark ? "Mode terang" : "Mode gelap"}
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="module-home-theme"
          >
            {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
          {/* Akses halaman Info/PRD sengaja TERSEMBUNYI: 3x klik beruntun pada
              logo (useTripleClick) — tanpa tombol yang terlihat langsung. */}
          <button
            type="button"
            onClick={onLogout}
            className="h-9 px-3 rounded-lg border border-border text-foreground/80 text-xs font-medium flex items-center gap-1.5 hover:bg-muted flex-shrink-0"
            data-testid="module-home-logout"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Keluar</span>
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-3 sm:px-6 py-5 sm:py-7 space-y-5">
        {/* ── HERO: identitas siklus + statistik hidup ── */}
        <section className="relative overflow-hidden rounded-3xl border border-blue-500/25 bg-gradient-to-br from-blue-600/10 via-indigo-500/5 to-transparent dark:from-blue-500/15 dark:via-indigo-500/10 p-4 sm:p-6">
          {/* Ornamen lingkar siklus (dekoratif, aman dua mode) */}
          <div aria-hidden className="absolute -right-14 -top-14 w-56 h-56 rounded-full border-[10px] border-blue-500/10 dark:border-blue-400/10" />
          <div aria-hidden className="absolute -right-4 -top-4 w-28 h-28 rounded-full border-[6px] border-indigo-500/10 dark:border-indigo-400/10" />
          <div className="relative">
            <h2 className="text-lg sm:text-2xl font-extrabold text-foreground tracking-tight">
              Peta Perjalanan Siklus BMN
            </h2>
            <p className="text-[11px] sm:text-sm text-muted-foreground max-w-2xl mt-1">
              12 tahap pengelolaan Barang Milik Negara dalam satu rumah — {DASAR_HUKUM_UMUM.join(" · ")}.
              Ikuti alurnya dari perolehan sampai pengakhiran; semua tercatat di poros Penatausahaan.
            </p>
            <div className="flex items-center gap-2 flex-wrap mt-3">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-600 text-white text-[11px] font-bold shadow-sm">
                <CheckCircle2 className="w-3.5 h-3.5" />16 modul aktif penuh
              </span>
              {stat && stat.aset > 0 && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-card border border-border text-[11px] font-semibold text-foreground" data-testid="hero-stat-aset">
                  <Package className="w-3.5 h-3.5 text-blue-500" />{stat.aset.toLocaleString("id-ID")} aset · {fmtRpSingkat(stat.nilai)}
                </span>
              )}
              <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-card border border-border text-[11px] text-muted-foreground">
                {ASAS_PENGELOLAAN.join(" · ")}
              </span>
            </div>
          </div>
        </section>

        {/* ── PETA ALUR: tiga fase ber-timeline (kolom di layar lebar) ── */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {FASE_ALUR.map((fase, fi) => (
            <div key={fase.id} className="bg-card rounded-2xl border border-border shadow-sm p-3 sm:p-4" data-testid={`fase-${fase.id}`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`text-[22px] font-black leading-none ${fase.aksen} opacity-40`}>{fi + 1}</span>
                <div className="min-w-0">
                  <h3 className={`font-bold text-sm leading-tight ${fase.aksen}`}>{fase.judul}</h3>
                  <p className="text-[10px] text-muted-foreground">{fase.sub}</p>
                </div>
              </div>
              {/* Timeline: garis vertikal + simpul nomor per modul */}
              <div className={`relative ml-3 border-l-2 border-dashed ${fase.garis} space-y-0.5 py-0.5 -translate-x-[13px] pl-[13px]`}>
                {fase.ids.map((id) => petaModul[id] && <BarisModul key={id} mod={petaModul[id]} />)}
              </div>
            </div>
          ))}
        </section>

        {/* ── Pita WASDAL: melingkupi seluruh siklus ── */}
        {wasdal && (
          <button
            type="button"
            onClick={() => openModule(wasdal)}
            data-testid="module-card-wasdal"
            className="w-full text-left rounded-2xl border border-indigo-500/40 bg-gradient-to-r from-indigo-500/10 via-violet-500/5 to-indigo-500/10 hover:from-indigo-500/15 hover:to-indigo-500/15 transition-colors p-3 sm:p-4 flex items-center gap-3 group min-w-0 min-h-0"
          >
            <span className={`w-10 h-10 rounded-xl bg-gradient-to-br ${MODULE_TILE.wasdal} flex items-center justify-center flex-shrink-0 shadow-sm`}>
              <Eye className="w-5 h-5 text-white ikon-denyut" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-bold text-foreground text-sm leading-tight">
                {wasdal.nama} <span className="text-[10px] font-semibold text-indigo-600 dark:text-indigo-400">· melingkupi seluruh siklus</span>
              </span>
              <span className="block text-[11px] text-muted-foreground leading-snug line-clamp-1">{wasdal.ringkas}</span>
            </span>
            <ChevronRight className="w-4 h-4 text-indigo-500 group-hover:translate-x-0.5 transition-transform flex-shrink-0" />
          </button>
        )}

        {/* ── POROS PENATAUSAHAAN: pusat pencatatan seluruh siklus ── */}
        <section className="relative bg-card rounded-3xl border-2 border-blue-500/40 shadow-sm p-3 sm:p-5 overflow-hidden" data-testid="module-penatausahaan">
          <div aria-hidden className="absolute -left-10 -bottom-10 w-40 h-40 rounded-full border-[8px] border-blue-500/10 dark:border-blue-400/10" />
          <div className="relative">
            <div className="flex items-center gap-2.5 mb-1">
              <span className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center flex-shrink-0 shadow-sm">
                <BookOpen className="w-5 h-5 text-white" />
              </span>
              <div className="min-w-0">
                <h3 className="font-extrabold text-foreground text-sm sm:text-base leading-tight">
                  Penatausahaan <span className="text-[10px] font-bold text-blue-600 dark:text-blue-400 align-middle">POROS</span>
                </h3>
                <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
                  Pembukuan · Inventarisasi · Pelaporan — semua tahap bermuara di sini
                  <span className="hidden sm:inline"> · {PENATAUSAHAAN_DASAR_HUKUM.split(" — ")[0]}</span>
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 mt-3">
              {PENATAUSAHAAN_SUBMODULES.map((mod) => {
                const Icon = MODULE_ICONS[mod.id] || Package;
    const anim = ikonAnim(mod.id);
                return (
                  <button
                    key={mod.id}
                    type="button"
                    onClick={() => openModule(mod)}
                    data-testid={`module-card-${mod.id}`}
                    className="text-left rounded-2xl border border-border bg-background p-3 hover:shadow-md hover:border-blue-500/50 hover:-translate-y-0.5 transition-all group"
                  >
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className={`w-9 h-9 rounded-xl bg-gradient-to-br ${MODULE_TILE[mod.id] || "from-slate-500 to-slate-600"} flex items-center justify-center flex-shrink-0 shadow-sm group-hover:scale-105 transition-transform`}>
                        <Icon className={`w-4 h-4 text-white ${anim.className}`} style={anim.style} />
                      </span>
                      <StatusBadge status={mod.status} />
                    </div>
                    <p className="font-semibold text-foreground text-xs sm:text-sm leading-tight">{mod.nama}</p>
                    <p className="text-[11px] text-muted-foreground mt-1 leading-snug line-clamp-2">{mod.ringkas}</p>
                    <span className="mt-2 inline-flex items-center gap-1 text-[11px] font-bold text-blue-600 dark:text-blue-400 group-hover:gap-1.5 transition-all">
                      Buka Modul <ChevronRight className="w-3.5 h-3.5" />
                    </span>
                  </button>
                );
              })}
            </div>

            <p className="mt-4 mb-1.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Referensi &amp; Master Data</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1.5">
              {onOpenKodefikasi && <Pintasan onClick={onOpenKodefikasi} testid="module-open-kodefikasi" icon={ListTree} warna="text-blue-500" label="Referensi Kodefikasi Barang" />}
              {onOpenPejabat && <Pintasan onClick={onOpenPejabat} testid="module-open-pejabat" icon={Users} warna="text-indigo-500" label="Referensi Pejabat" />}
              {onOpenRuangan && <Pintasan onClick={onOpenRuangan} testid="module-open-ruangan" icon={DoorOpen} warna="text-teal-500" label="Referensi Ruangan" />}
              {onOpenReferensiAkun && <Pintasan onClick={onOpenReferensiAkun} testid="module-open-referensi-akun" icon={Landmark} warna="text-amber-500" label="Referensi Akun BAS" />}
              {onOpenPegawai && <Pintasan onClick={onOpenPegawai} testid="module-open-pegawai" icon={IdCard} warna="text-sky-500" label="Master Pegawai" />}
              {onOpenSatker && <Pintasan onClick={onOpenSatker} testid="module-open-satker" icon={Building2} warna="text-emerald-500" label="Master Satker" />}
            </div>
            {(onOpenPersuratan || onOpenTtd || onOpenPengaturan) && (
              <>
                <p className="mt-3 mb-1.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Administrasi &amp; Alat</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1.5">
                  {onOpenPersuratan && <Pintasan onClick={onOpenPersuratan} testid="module-open-persuratan" icon={Mail} warna="text-cyan-500" label="Registrasi Persuratan" />}
                  {onOpenTtd && <Pintasan onClick={onOpenTtd} testid="module-open-ttd" icon={FileSignature} warna="text-violet-500" label="Tanda Tangan Elektronik" />}
                  {onOpenPengaturan && <Pintasan onClick={onOpenPengaturan} testid="module-open-pengaturan" icon={Settings} warna="text-slate-500" label="Pengaturan" />}
                </div>
              </>
            )}
          </div>
        </section>

        <p className="text-center text-[11px] text-muted-foreground pb-4">
          Klik tahap mana pun untuk langsung bekerja — seluruh 16 modul aktif dan saling terhubung.
        </p>
      </main>

      {/* ── Dialog konsep modul ── */}
      <Dialog open={!!detail} onOpenChange={(o) => { if (!o) setDetail(null); }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          {detail && (
            <>
              <DialogHeader>
                <div className="flex items-center gap-2.5">
                  <span className={`w-10 h-10 rounded-xl bg-gradient-to-br ${MODULE_TILE[detail.id] || "from-slate-500 to-slate-600"} flex items-center justify-center flex-shrink-0`}>
                    {DetailIcon && (() => { const da = ikonAnim(detail.id); return <DetailIcon className={`w-5 h-5 text-white ${da.className}`} style={da.style} />; })()}
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
