import React, { useState, useCallback } from "react";
import { ArrowLeft, Download, FileText, Presentation, ChevronDown, ChevronRight, Package, Shield, Users, Camera, Upload, BarChart3, FileSpreadsheet, Printer, RefreshCw, Globe, CheckCircle2, XCircle, Clock, Layers, Database, Server, Monitor, Wifi, Lock, Zap, BookOpen, DollarSign, Calendar, Target, AlertTriangle, MapPinned, GitBranch, Sparkles } from "lucide-react";
import { downloadFileWithProgress } from "../lib/downloadFile";

const API = process.env.REACT_APP_BACKEND_URL;

// ═══════════════════════════════════════════════════════════════
// INFOGRAPHIC COMPONENTS
// ═══════════════════════════════════════════════════════════════

function StatCard({ icon: Icon, value, label, color = "blue" }) {
  const colors = {
    blue: "from-blue-500/20 to-blue-600/10 border-blue-500/30 text-blue-400",
    green: "from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 text-emerald-400",
    orange: "from-orange-500/20 to-orange-600/10 border-orange-500/30 text-orange-400",
    purple: "from-purple-500/20 to-purple-600/10 border-purple-500/30 text-purple-400",
    red: "from-red-500/20 to-red-600/10 border-red-500/30 text-red-400",
    cyan: "from-cyan-500/20 to-cyan-600/10 border-cyan-500/30 text-cyan-400",
  };
  return (
    <div className={`bg-gradient-to-br ${colors[color]} border rounded-xl p-5 text-center`}>
      <Icon className="w-8 h-8 mx-auto mb-2 opacity-80" />
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-xs opacity-70 mt-1">{label}</div>
    </div>
  );
}

function FeatureCard({ icon: Icon, title, description, color = "blue", items = [] }) {
  const colors = {
    blue: "border-blue-500/30 hover:border-blue-400/50",
    green: "border-emerald-500/30 hover:border-emerald-400/50",
    orange: "border-orange-500/30 hover:border-orange-400/50",
    purple: "border-purple-500/30 hover:border-purple-400/50",
    red: "border-red-500/30 hover:border-red-400/50",
    cyan: "border-cyan-500/30 hover:border-cyan-400/50",
    pink: "border-pink-500/30 hover:border-pink-400/50",
    teal: "border-teal-500/30 hover:border-teal-400/50",
  };
  const iconColors = {
    blue: "text-blue-400 bg-blue-500/20",
    green: "text-emerald-400 bg-emerald-500/20",
    orange: "text-orange-400 bg-orange-500/20",
    purple: "text-purple-400 bg-purple-500/20",
    red: "text-red-400 bg-red-500/20",
    cyan: "text-cyan-400 bg-cyan-500/20",
    pink: "text-pink-400 bg-pink-500/20",
    teal: "text-teal-400 bg-teal-500/20",
  };
  return (
    <div className={`bg-slate-800/50 border ${colors[color]} rounded-xl p-5 transition-all duration-300 hover:bg-slate-800/80 hover:shadow-lg`}>
      <div className={`w-10 h-10 rounded-lg ${iconColors[color]} flex items-center justify-center mb-3`}>
        <Icon className="w-5 h-5" />
      </div>
      <h4 className="font-semibold text-white mb-2">{title}</h4>
      <p className="text-sm text-slate-400 leading-relaxed">{description}</p>
      {items.length > 0 && (
        <ul className="mt-3 space-y-1">
          {items.map((item, i) => (
            <li key={i} className="text-xs text-slate-500 flex items-start gap-1.5">
              <span className="text-blue-400 mt-0.5">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function WorkflowStep({ number, title, description, color, isLast }) {
  const colorMap = { blue: "bg-blue-500", green: "bg-emerald-500", orange: "bg-orange-500", red: "bg-red-500", purple: "bg-purple-500", cyan: "bg-cyan-500" };
  return (
    <div className="flex items-stretch gap-4">
      <div className="flex flex-col items-center">
        <div className={`w-10 h-10 rounded-full ${colorMap[color]} flex items-center justify-center text-white font-bold text-sm shadow-lg shrink-0`}>
          {number}
        </div>
        {/* Konektor mengikuti tinggi konten agar garis tak putus saat deskripsi membungkus */}
        {!isLast && <div className="w-0.5 flex-1 min-h-8 bg-slate-700 mt-2" />}
      </div>
      <div className="pb-8 min-w-0">
        <h4 className="font-semibold text-white">{title}</h4>
        <p className="text-sm text-slate-400 mt-1">{description}</p>
      </div>
    </div>
  );
}

function CollapsibleSection({ id, title, icon: Icon, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    // scroll-mt-20 memberi ruang untuk header sticky saat lompat via anchor
    <div id={id} className="border border-slate-700/50 rounded-xl overflow-hidden mb-4 scroll-mt-20">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center gap-3 px-6 py-4 bg-slate-800/50 hover:bg-slate-800/80 transition-colors text-left">
        {Icon && <Icon className="w-5 h-5 text-blue-400" />}
        <span className="font-semibold text-white flex-1">{title}</span>
        {open ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
      </button>
      {open && <div className="px-6 py-5 bg-slate-900/50">{children}</div>}
    </div>
  );
}

function ArchBlock({ icon: Icon, title, items, color }) {
  const colorMap = {
    blue: "border-blue-500/40 text-blue-400",
    green: "border-emerald-500/40 text-emerald-400",
    orange: "border-orange-500/40 text-orange-400",
    purple: "border-purple-500/40 text-purple-400",
  };
  return (
    <div className={`border-t-2 ${colorMap[color]} bg-slate-800/40 rounded-lg p-4`}>
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-5 h-5" />
        <h4 className="font-semibold text-white text-sm">{title}</h4>
      </div>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="text-xs text-slate-400 break-words">{item}</li>
        ))}
      </ul>
    </div>
  );
}

// Kartu catatan rilis — dipakai bagian "Apa yang Baru".
function ReleaseCard({ tag, date, title, points, color = "blue" }) {
  const chipColors = {
    blue: "bg-blue-500/15 text-blue-300 border-blue-500/30",
    teal: "bg-teal-500/15 text-teal-300 border-teal-500/30",
    orange: "bg-orange-500/15 text-orange-300 border-orange-500/30",
    green: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    purple: "bg-purple-500/15 text-purple-300 border-purple-500/30",
    cyan: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  };
  return (
    <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5 hover:border-slate-600/70 transition-colors">
      <div className="flex items-center gap-2 mb-2">
        <span className={`px-2 py-0.5 rounded-full border text-[10px] font-bold tracking-wide ${chipColors[color]}`}>{tag}</span>
        <span className="text-[11px] text-slate-500">{date}</span>
      </div>
      <h4 className="font-semibold text-white text-sm mb-2">{title}</h4>
      <ul className="space-y-1.5">
        {points.map((p, i) => (
          <li key={i} className="text-xs text-slate-400 flex items-start gap-1.5 leading-relaxed">
            <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0 mt-0.5" />
            <span>{p}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PriceTier({ name, price, unit, tagline, features, highlight = false }) {
  return (
    <div className={`rounded-xl p-5 border flex flex-col ${
      highlight
        ? "bg-blue-600/15 border-blue-500/50 shadow-lg shadow-blue-500/10"
        : "bg-slate-800/50 border-slate-700/50"
    }`}>
      {highlight && (
        <div className="self-start px-2 py-0.5 mb-2 rounded-full bg-blue-500/30 text-blue-300 text-[10px] font-bold uppercase tracking-wide">Rekomendasi</div>
      )}
      <h4 className="font-bold text-white">{name}</h4>
      <p className="text-xs text-slate-400 mt-1 mb-3">{tagline}</p>
      <div className="mb-4">
        <span className={`text-2xl font-bold ${highlight ? "text-blue-300" : "text-white"}`}>{price}</span>
        <span className="text-xs text-slate-400 ml-1">{unit}</span>
      </div>
      <ul className="space-y-1.5 mt-auto">
        {features.map((f, i) => (
          <li key={i} className="text-xs text-slate-300 flex items-start gap-1.5">
            <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0 mt-0.5" />
            <span>{f}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RABTable() {
  const data = [
    { cat: "A", label: "BIAYA PENGEMBANGAN", items: [
      { no: 1, name: "Full-stack Development", vol: 1, unit: "Paket", price: 85000000 },
      { no: 2, name: "UI/UX Design & Prototyping", vol: 1, unit: "Paket", price: 15000000 },
      { no: 3, name: "Quality Assurance & Testing", vol: 1, unit: "Paket", price: 10000000 },
      { no: 4, name: "Dokumentasi & User Manual", vol: 1, unit: "Paket", price: 5000000 },
      { no: 5, name: "Training Pengguna", vol: 2, unit: "Sesi", price: 5000000 },
    ]},
    { cat: "B", label: "BIAYA INFRASTRUKTUR (1 TAHUN)", items: [
      { no: 6, name: "Cloud Server (VPS/Kubernetes)", vol: 12, unit: "Bulan", price: 1500000 },
      { no: 7, name: "Domain & SSL Certificate", vol: 1, unit: "Tahun", price: 500000 },
      { no: 8, name: "MongoDB Atlas (M10)", vol: 12, unit: "Bulan", price: 800000 },
      { no: 9, name: "Backup Storage (100 GB)", vol: 12, unit: "Bulan", price: 200000 },
    ]},
    { cat: "C", label: "BIAYA OPERASIONAL (1 TAHUN)", items: [
      { no: 10, name: "Maintenance & Bug Fix", vol: 12, unit: "Bulan", price: 2000000 },
      { no: 11, name: "Technical Support", vol: 12, unit: "Bulan", price: 1000000 },
    ]},
  ];
  const fmt = (n) => n.toLocaleString("id-ID");
  const grandTotal = data.reduce((sum, cat) => sum + cat.items.reduce((s, i) => s + i.vol * i.price, 0), 0);

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="bg-blue-600/20 text-blue-300">
            <th className="px-3 py-2.5 text-left rounded-tl-lg">No</th>
            <th className="px-3 py-2.5 text-left">Komponen Biaya</th>
            <th className="px-3 py-2.5 text-center">Vol</th>
            <th className="px-3 py-2.5 text-center">Satuan</th>
            <th className="px-3 py-2.5 text-right">Harga Satuan</th>
            <th className="px-3 py-2.5 text-right rounded-tr-lg">Jumlah (Rp)</th>
          </tr>
        </thead>
        <tbody>
          {data.map((cat, ci) => {
            const subtotal = cat.items.reduce((s, i) => s + i.vol * i.price, 0);
            return (
              <React.Fragment key={ci}>
                <tr className="bg-slate-800/80">
                  <td className="px-3 py-2 font-bold text-blue-300" colSpan={6}>{cat.cat}. {cat.label}</td>
                </tr>
                {cat.items.map((item) => (
                  <tr key={item.no} className="border-b border-slate-800 hover:bg-slate-800/40">
                    <td className="px-3 py-2 text-slate-400">{item.no}</td>
                    <td className="px-3 py-2 text-slate-300">{item.name}</td>
                    <td className="px-3 py-2 text-center text-slate-400">{item.vol}</td>
                    <td className="px-3 py-2 text-center text-slate-400">{item.unit}</td>
                    <td className="px-3 py-2 text-right text-slate-400 whitespace-nowrap tabular-nums">{fmt(item.price)}</td>
                    <td className="px-3 py-2 text-right text-slate-300 font-medium whitespace-nowrap tabular-nums">{fmt(item.vol * item.price)}</td>
                  </tr>
                ))}
                <tr className="bg-slate-800/50">
                  <td colSpan={5} className="px-3 py-2 text-right text-slate-400 text-xs font-medium">Subtotal {cat.label}</td>
                  <td className="px-3 py-2 text-right text-white font-semibold whitespace-nowrap tabular-nums">{fmt(subtotal)}</td>
                </tr>
              </React.Fragment>
            );
          })}
          <tr className="bg-blue-600/30">
            <td colSpan={5} className="px-3 py-3 text-right text-white font-bold rounded-bl-lg">TOTAL KESELURUHAN</td>
            <td className="px-3 py-3 text-right text-blue-300 font-bold text-base rounded-br-lg whitespace-nowrap tabular-nums">Rp {fmt(grandTotal)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN INFO PAGE
// ═══════════════════════════════════════════════════════════════

export default function InfoPage({ onBack }) {
  const [downloading, setDownloading] = useState(null);

  const handleDownload = useCallback(async (type) => {
    setDownloading(type);
    try {
      const endpoint = type === "ppt" ? "/api/documents/ppt" : "/api/documents/proposal";
      const filename = type === "ppt" ? "InventoryMaster_PRD_Presentation.pptx" : "Proposal_InventoryMaster_Pro.docx";
      await downloadFileWithProgress(`${API}${endpoint}`, filename, {
        label: type === "ppt" ? "Presentasi PPT" : "Proposal DOCX",
        timeout: 60000,
      });
    } catch { /* toast error sudah ditangani helper */ } finally {
      setDownloading(null);
    }
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      {/* Header */}
      <div className="sticky top-0 z-50 bg-slate-950/95 backdrop-blur-xl border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 py-3 flex items-center justify-between gap-2">
          <button onClick={onBack} className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm">
            <ArrowLeft className="w-4 h-4" />
            <span>Kembali</span>
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 bg-blue-500 rounded-lg flex items-center justify-center shrink-0" title="AMAN — Manajemen Aset Negara">
              <Package className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-white text-sm hidden md:inline truncate">AMAN — Manajemen Aset Negara</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => handleDownload("ppt")}
              disabled={!!downloading}
              title="Unduh Slide Presentasi (PPTX)"
              aria-label="Unduh Slide Presentasi (PPTX)"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-orange-500/20 border border-orange-500/30 text-orange-300 rounded-lg text-xs hover:bg-orange-500/30 transition-colors disabled:opacity-50"
            >
              <Presentation className="w-3.5 h-3.5" />
              {downloading === "ppt" ? "..." : "PPT"}
            </button>
            <button
              onClick={() => handleDownload("proposal")}
              disabled={!!downloading}
              title="Unduh Proposal Lengkap (DOCX)"
              aria-label="Unduh Proposal Lengkap (DOCX)"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/20 border border-blue-500/30 text-blue-300 rounded-lg text-xs hover:bg-blue-500/30 transition-colors disabled:opacity-50"
            >
              <FileText className="w-3.5 h-3.5" />
              {downloading === "proposal" ? "..." : "Proposal"}
            </button>
          </div>
        </div>
      </div>

      <div className="relative max-w-7xl mx-auto px-6 py-10 overflow-x-clip">
        {/* Cahaya latar hero — dekoratif saja */}
        <div className="pointer-events-none absolute -top-28 left-1/2 -translate-x-1/2 w-[720px] h-[420px] bg-blue-600/15 blur-[120px] rounded-full" aria-hidden="true" />
        <div className="pointer-events-none absolute top-24 right-[-120px] w-[380px] h-[280px] bg-cyan-500/10 blur-[100px] rounded-full" aria-hidden="true" />

        {/* ── HERO ── */}
        <div className="relative text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-blue-500/10 border border-blue-500/20 rounded-full text-blue-400 text-xs mb-6">
            <Zap className="w-3.5 h-3.5" />
            Product Requirements Document — v2.3 · Juli 2026
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4 leading-tight">
            AMAN<br />
            <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">Aplikasi Manajemen Aset Negara</span>
          </h1>
          <p className="text-lg text-slate-400 max-w-2xl mx-auto mb-5">
            Satu aplikasi untuk seluruh siklus inventarisasi Barang Milik Negara: dari impor data SIMAN,
            pendataan lapangan dengan kamera dan scan QR, sampai laporan resmi siap tanda tangan dan
            pengesahan berkekuatan dokumen — tetap bekerja penuh saat sinyal hilang.
          </p>
          <div className="flex items-center justify-center gap-2 flex-wrap mb-8">
            {["Offline-first", "Real-time multi-user", "SE-17/MK.1/2024", "Peta GIS + KML/KMZ/SHP", "CI/CD otomatis"].map((chip) => (
              <span key={chip} className="px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-slate-300 text-[11px]">{chip}</span>
            ))}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 max-w-4xl mx-auto">
            <StatCard icon={Layers} value="20+" label="Modul Fitur" color="blue" />
            <StatCard icon={FileText} value="13+" label="Laporan Resmi PDF" color="green" />
            <StatCard icon={MapPinned} value="GIS" label="Peta + KML/KMZ/SHP" color="cyan" />
            <StatCard icon={FileSpreadsheet} value="46" label="Kolom Import/Export" color="orange" />
            <StatCard icon={Users} value="Multi" label="User Real-time + Offline" color="purple" />
          </div>
        </div>

        {/* ── NAVIGASI CEPAT ANTAR SEKSI ── */}
        <nav aria-label="Navigasi seksi" className="flex items-center justify-center gap-2 flex-wrap mb-12">
          {[
            { href: "#rilis", label: "Apa yang Baru" },
            { href: "#latar-belakang", label: "Latar Belakang" },
            { href: "#arsitektur", label: "Arsitektur" },
            { href: "#fitur", label: "Fitur (20+ Modul)" },
            { href: "#se17", label: "Klasifikasi SE-17" },
            { href: "#alur-kerja", label: "Alur Kerja" },
            { href: "#harga", label: "Harga & RAB" },
            { href: "#timeline", label: "Timeline" },
            { href: "#peran", label: "Peran Pengguna" },
          ].map((s) => (
            <a key={s.href} href={s.href} className="min-h-0 min-w-0 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-slate-300 text-[11px] hover:border-blue-500/50 hover:text-blue-300 transition-colors">{s.label}</a>
          ))}
        </nav>

        {/* ── DOWNLOAD SECTION ── */}
        <div className="grid md:grid-cols-2 gap-4 mb-12">
          <button
            onClick={() => handleDownload("ppt")}
            disabled={!!downloading}
            className="flex items-center gap-4 p-6 bg-gradient-to-r from-orange-500/10 to-orange-600/5 border border-orange-500/20 rounded-xl hover:border-orange-400/40 transition-all disabled:opacity-50"
          >
            <div className="w-14 h-14 bg-orange-500/20 rounded-xl flex items-center justify-center shrink-0">
              <Presentation className="w-7 h-7 text-orange-400" />
            </div>
            <div className="text-left">
              <div className="font-semibold text-white">Slide Presentasi (PPTX)</div>
              <div className="text-sm text-slate-400">9 slide profesional — cover, latar belakang, arsitektur, fitur, alur kerja, SE-17, RAB, timeline, penutup</div>
            </div>
            <Download className="w-5 h-5 text-orange-400 shrink-0" />
          </button>
          <button
            onClick={() => handleDownload("proposal")}
            disabled={!!downloading}
            className="flex items-center gap-4 p-6 bg-gradient-to-r from-blue-500/10 to-blue-600/5 border border-blue-500/20 rounded-xl hover:border-blue-400/40 transition-all disabled:opacity-50"
          >
            <div className="w-14 h-14 bg-blue-500/20 rounded-xl flex items-center justify-center shrink-0">
              <FileText className="w-7 h-7 text-blue-400" />
            </div>
            <div className="text-left">
              <div className="font-semibold text-white">Proposal Lengkap (DOCX)</div>
              <div className="text-sm text-slate-400">BAB I-VI — Pendahuluan, Gambaran Umum, Metodologi, Spesifikasi Teknis, RAB, Penutup</div>
            </div>
            <Download className="w-5 h-5 text-blue-400 shrink-0" />
          </button>
        </div>

        {/* ── SECTIONS ── */}
        <CollapsibleSection id="rilis" title="Apa yang Baru — Rilis v2.3" icon={Sparkles} defaultOpen={true}>
          <p className="text-sm text-slate-400 mb-5">
            Rangkaian pembaruan Juli 2026 berfokus pada pekerjaan lapangan: peta aset interaktif,
            alur kamera + scan QR beruntun, dan laporan dengan kop surat resmi. Detail lengkap per
            perubahan tercatat di CHANGELOG repositori.
          </p>
          <div className="grid md:grid-cols-2 gap-4">
            <ReleaseCard
              tag="PETA ASET" date="Juli 2026" color="teal"
              title="Peta interaktif menyatu di halaman utama"
              points={[
                "Lembar peta menggantikan baris data tanpa meninggalkan halaman — header, mode, dan filter tetap aktif",
                "Pencarian, filter lanjutan, dan Barang Serupa langsung menyaring pin di peta",
                "Geser pin untuk membetulkan koordinat — tersimpan otomatis dan aman dari konflik antar-pengguna",
                "Pin berlapis info: warna status, badge foto, border hijau saat pengguna + NIP + BAST lengkap",
              ]}
            />
            <ReleaseCard
              tag="EKSPOR GIS" date="Juli 2026" color="cyan"
              title="Unduh titik peta ke KML, KMZ, dan Shapefile"
              points={[
                "27 atribut per titik — identitas, kondisi, pengguna, sampai jumlah foto",
                "Mengikuti filter yang sedang aktif, jadi hasil unduhan = apa yang tampil",
                "Shapefile ZIP lengkap dengan proyeksi WGS84 (.prj) — siap dibuka di ArcGIS/QGIS",
              ]}
            />
            <ReleaseCard
              tag="KAMERA LAPANGAN" date="Juli 2026" color="orange"
              title="Alur pendataan beruntun tanpa keluar kamera"
              points={[
                "Flash, gestur kecerahan (tahan + geser), dan watermark jam/GPS otomatis",
                "Simpan & Baru instan — antrean simpan bekerja di belakang, petugas lanjut ke aset berikutnya",
                "Simpan & Scan: scan QR stiker → panel edit selengkap lembar edit cepat → scan berikutnya",
              ]}
            />
            <ReleaseCard
              tag="LAPORAN" date="Juli 2026" color="green"
              title="Kop surat resmi & penanda tangan yang benar"
              points={[
                "Kop 3 baris (instansi, unit, sub-unit) + alamat multi-baris yang dapat diatur sendiri",
                "Seluruh tanda tangan memakai jabatan \"Kuasa Pengguna Barang\"",
                "Blok identitas rata titik dua, tanggal gaya Indonesia di semua laporan",
              ]}
            />
            <ReleaseCard
              tag="FONDASI" date="Juli 2026" color="purple"
              title="Gerbang kualitas otomatis di setiap perubahan"
              points={[
                "GitHub Actions: test backend + lint & build frontend wajib hijau sebelum merge",
                "Auto-deploy ke server produksi begitu perubahan masuk ke main",
                "Registry field aset — satu sumber kebenaran, drift antar-modul tertangkap test",
              ]}
            />
            <ReleaseCard
              tag="MOBILE" date="Juli 2026" color="blue"
              title="Tata letak HP yang lebih lega"
              points={[
                "Padding & jarak antar blok dirapatkan khusus layar kecil — baris data dapat ruang lebih",
                "Bar peta dua baris di HP, popup pin dengan bingkai foto dan info padat",
                "Target sentuh tombol tetap ≥44px sesuai pedoman aksesibilitas",
              ]}
            />
          </div>
        </CollapsibleSection>

        <CollapsibleSection id="latar-belakang" title="Latar Belakang & Dasar Hukum" icon={BookOpen} defaultOpen={true}>
          <div className="grid md:grid-cols-2 gap-8">
            <div>
              <h4 className="font-semibold text-white mb-3">Mengapa Sistem Ini Dibutuhkan?</h4>
              <div className="space-y-3">
                {[
                  { icon: AlertTriangle, color: "text-red-400", title: "Pencatatan Manual", desc: "Spreadsheet rawan kesalahan, duplikasi data, dan sulit diaudit" },
                  { icon: XCircle, color: "text-orange-400", title: "Tidak Real-time", desc: "Perubahan tidak tersinkronisasi antar tim, data tidak konsisten" },
                  { icon: Wifi, color: "text-cyan-400", title: "Sinyal Lapangan Terbatas", desc: "Inventarisasi fisik sering di lokasi tanpa koneksi — butuh mode offline penuh" },
                  { icon: Shield, color: "text-blue-400", title: "Kepatuhan Regulasi", desc: "SE-17/MK.1/2024 memerlukan klasifikasi detail untuk aset tidak ditemukan" },
                  { icon: Camera, color: "text-purple-400", title: "Dokumentasi Terbatas", desc: "Foto aset & dokumen terpisah dari data utama" },
                ].map((item, i) => (
                  <div key={i} className="flex gap-3 items-start">
                    <item.icon className={`w-5 h-5 ${item.color} shrink-0 mt-0.5`} />
                    <div>
                      <div className="text-sm font-medium text-white">{item.title}</div>
                      <div className="text-xs text-slate-400">{item.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-3">Dasar Hukum</h4>
              <div className="space-y-2.5">
                {[
                  "SE-17/MK.1/2024 tentang Pelaksanaan Inventarisasi BMN",
                  "PP 27/2014 jo PP 28/2020 tentang Pengelolaan BMN/D",
                  "PMK 181/PMK.06/2016 tentang Penatausahaan BMN",
                  "Peraturan SPBE tentang Sistem Pemerintahan Berbasis Elektronik",
                ].map((reg, i) => (
                  <div key={i} className="flex gap-3 items-start">
                    <span className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold shrink-0">{i + 1}</span>
                    <span className="text-sm text-slate-300">{reg}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </CollapsibleSection>

        <CollapsibleSection id="arsitektur" title="Arsitektur & Teknologi" icon={Server} defaultOpen={true}>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <ArchBlock icon={Monitor} title="Frontend" items={["React 19 + Tailwind CSS", "Shadcn/UI + Leaflet (Peta Aset)", "Offline-first: IndexedDB + Service Worker", "Responsive & Dark Mode"]} color="blue" />
            <ArchBlock icon={Server} title="Backend" items={["Python FastAPI (Async), 19 modul route", "WebSocket + Event Bus lintas worker", "OCC (version/If-Match) + Idempotency-Key", "JWT + OTP Email Authentication"]} color="green" />
            <ArchBlock icon={Database} title="Database" items={["MongoDB 7.0 + Motor (async)", "GridFS: foto, dokumen, BAST", "Capped collection ws_events", "UUID-based Records"]} color="orange" />
            <ArchBlock icon={Globe} title="Infrastructure" items={["VPS: Nginx + Supervisor", "CI/CD GitHub Actions — test tiap PR, auto-deploy saat merge", "Multi-worker uvicorn + SSL (Let's Encrypt)", "WeasyPrint + ReportLab (PDF)"]} color="purple" />
          </div>
          <div className="flex items-center justify-center gap-2 flex-wrap py-4">
            {["User Browser", "React SPA (offline-ready)", "Nginx", "FastAPI (multi-worker)", "MongoDB + GridFS"].map((item, i, arr) => (
              // Chip + panah dibungkus satu span agar panah tak menggantung sendirian saat baris membungkus
              <span key={i} className="inline-flex items-center gap-2">
                <span className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300">{item}</span>
                {i < arr.length - 1 && <span className="text-blue-400 font-bold" aria-hidden="true">→</span>}
              </span>
            ))}
          </div>
        </CollapsibleSection>

        <CollapsibleSection id="fitur" title="Fitur & Fungsionalitas (20+ Modul)" icon={Layers}>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <FeatureCard icon={Package} title="Manajemen Aset Lengkap" description="CRUD aset dengan 45+ field: identitas, perolehan, organisasi, kondisi, GPS, stiker, dokumen" color="blue" items={["Partial update (PATCH diff) — hanya field berubah", "Validasi kode aset 10 digit & register 32 hex", "Barang Serupa: grup per kode + batch edit"]} />
            <FeatureCard icon={Target} title="Mode Inventarisasi Lapangan" description="Lembar input satu layar untuk petugas lapangan: cepat, minim ketik" color="green" items={["Status & kondisi sekali ketuk + progress bar", "Salin lokasi/pengguna dari aset sebelumnya", "GPS cache instan + kamera langsung"]} />
            <FeatureCard icon={Wifi} title="Mode Offline Penuh" description="Bekerja tanpa koneksi: data & simpanan aman sampai sinyal kembali" color="orange" items={["Snapshot kegiatan di IndexedDB (delta sync)", "Antrian simpan persisten + auto-sync", "Edit dari cache, foto terkompresi lokal"]} />
            <FeatureCard icon={Users} title="Kolaborasi Real-time" description="Multi-user aman: tanpa lost-update, tanpa duplikasi" color="purple" items={["OCC version + If-Match (409 aman)", "Row locking atomik + presence lintas worker", "WebSocket ber-JWT + Idempotency-Key"]} />
            <FeatureCard icon={Lock} title="Pengesahan & Kunci Kegiatan" description="Nomor tiket INV-{tahun}-{seq} + alur pengesahan berkekuatan dokumen" color="red" items={["Validasi kelayakan (foto, register, lokasi, pengguna)", "Unggah PDF bertanda tangan (GridFS)", "Kegiatan terkunci permanen (mutasi ditolak 423)"]} />
            <FeatureCard icon={BookOpen} title="Kartu Inventarisasi & QR" description="Riwayat pengesahan aset lintas kegiatan, terlingkup satker" color="cyan" items={["Per kode register / kode aset + NUP", "QR #kode_register di kartu cetak", "Scanner QR kamera di dashboard"]} />
            <FeatureCard icon={Camera} title="Foto & Media" description="Multi-foto per aset di GridFS dengan pemuatan progresif" color="pink" items={["Kompresi berlapis (client + server)", "Streaming URL cacheable (ETag/304)", "Checklist dokumen: foto bukti + PDF"]} />
            <FeatureCard icon={MapPinned} title="Peta Aset & Ekspor GIS" description="Lembar peta interaktif di halaman utama — mengikuti pencarian & filter aktif, jalan penuh saat offline" color="teal" items={["Pin status berwarna + badge foto + border hijau kelengkapan pengguna/BAST", "Geser pin = koordinat tersimpan otomatis (aman konflik)", "Filter Barang Serupa + unduh KML/KMZ/SHP (27 atribut, WGS84)"]} />
            <FeatureCard icon={Zap} title="Kamera Lapangan Penuh" description="Layar kamera ala Timemark: jam & GPS live, watermark otomatis, alur beruntun tanpa keluar kamera" color="orange" items={["Flash + gestur kecerahan (dibakar ke hasil foto)", "Simpan & Baru instan — tanpa menunggu jaringan", "Simpan & Scan: scan QR → edit → scan berikutnya"]} />
            <FeatureCard icon={GitBranch} title="CI/CD & Kualitas Kode" description="Setiap perubahan melewati gerbang otomatis sebelum sampai ke pengguna" color="cyan" items={["Test + lint + build di tiap PR (GitHub Actions)", "Auto-deploy ke VPS saat merge ke main", "Registry field aset + test anti-drift"]} />
            <FeatureCard icon={FileText} title="13+ Laporan Resmi" description="DBHI (6 tipe), RHI, BAHI, SP, BA, SPTJM, Surat Koreksi, Eksekutif, Satker, LHI" color="teal" items={["Kop surat resmi 3 baris + alamat multi-baris, tanda tangan Kuasa Pengguna Barang", "Eksekutif per Barang Serupa + kolom detail toggle", "Kartu BMN format KTP (satuan & massal) + tanggal gaya Indonesia"]} />
            <FeatureCard icon={Users} title="Pengguna Melekat-ke + BAST" description="Pengguna aset terstruktur: Individual / Jabatan / Operasional" color="blue" items={["Nama jabatan kondisional (Jabatan)", "Jenis operasional: Kegiatan/Acara/Kebutuhan atau Ruangan", "Nomor BAST + unggah & preview dokumen BAST"]} />
            <FeatureCard icon={Upload} title="Import & Export 46 Kolom" description="CSV/XLSX dua arah dengan template dropdown dan validasi per baris" color="green" items={["Deteksi duplikat + pilihan update", "XLSX 4 sheet dengan foto HD embedded", "Export PDF landscape + progres unduhan"]} />
            <FeatureCard icon={Shield} title="Keamanan & Audit" description="JWT + OTP email, role-based access, jejak audit menyeluruh" color="orange" items={["Audit trail semua perubahan per field", "Auto-logout: sesi 401 & idle 30 menit", "Rate limiting + heartbeat sesi"]} />
            <FeatureCard icon={RefreshCw} title="Backup & Restore Penuh" description="Backup semua koleksi + GridFS (foto, dokumen, BAST, pengesahan)" color="purple" items={["Termasuk riwayat pengesahan & counter tiket", "Restore membangun ulang index & counter", "Background job, format ZIP"]} />
          </div>
        </CollapsibleSection>

        <CollapsibleSection id="se17" title="Klasifikasi SE-17/MK.1/2024" icon={Shield}>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                <h4 className="font-bold text-emerald-400">Ditemukan</h4>
              </div>
              <p className="text-sm text-slate-400 mb-3">Aset terverifikasi keberadaannya di lokasi</p>
              <ul className="space-y-2 text-sm text-slate-300">
                <li>• Kondisi: Baik / Rusak Ringan / Rusak Berat</li>
                <li>• Foto aset wajib dilampirkan</li>
                <li>• Stiker inventaris dipasang</li>
              </ul>
            </div>
            <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <XCircle className="w-6 h-6 text-red-400" />
                <h4 className="font-bold text-red-400">Tidak Ditemukan</h4>
              </div>
              <p className="text-sm text-slate-400 mb-3">Klasifikasi + sub-klasifikasi detail:</p>
              <ul className="space-y-2 text-sm text-slate-300">
                <li>• Kesalahan Pencatatan (7 sub-klasifikasi)</li>
                <li>• Tidak Ditemukan Lainnya (3 sub-klasifikasi)</li>
                <li>• Uraian, kronologis & tindak lanjut</li>
              </ul>
            </div>
            <div className="bg-slate-500/5 border border-slate-500/20 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <Clock className="w-6 h-6 text-slate-400" />
                <h4 className="font-bold text-slate-400">Status Lainnya</h4>
              </div>
              <p className="text-sm text-slate-400 mb-3">Total 5 status inventarisasi didukung</p>
              <ul className="space-y-2 text-sm text-slate-300">
                <li>• Belum Diinventarisasi — default saat import, progress % di dashboard</li>
                <li>• Berlebih — keterangan & asal-usul</li>
                <li>• Sengketa — nomor perkara & pihak bersengketa</li>
              </ul>
            </div>
          </div>
        </CollapsibleSection>

        <CollapsibleSection id="alur-kerja" title="Alur Kerja Inventarisasi" icon={Target}>
          <div className="max-w-xl mx-auto">
            <WorkflowStep number="01" title="Buat Kegiatan Inventarisasi" description="Admin membuat kegiatan (nomor tiket INV-{tahun}-{seq} otomatis), mengatur satker, eselon, tim, dan kategori aset" color="blue" />
            <WorkflowStep number="02" title="Siapkan Data Aset" description="Import data BMN dari SIMAN/CSV/XLSX (46 kolom, template dengan dropdown) atau input manual per aset" color="green" />
            <WorkflowStep number="03" title="Pelaksanaan Inventarisasi" description="Tim lapangan memakai mode inventarisasi lapangan: status/kondisi sekali ketuk, foto, GPS, stiker, scan QR — tetap berjalan penuh saat offline" color="orange" />
            <WorkflowStep number="04" title="Verifikasi & Klasifikasi" description="Admin memverifikasi data, mengklasifikasikan aset tidak ditemukan/berlebih/sengketa, memantau lewat audit trail" color="red" />
            <WorkflowStep number="05" title="Rekapitulasi & Laporan" description="Generate 13+ laporan resmi berdesain seragam dengan kop surat instansi: DBHI, RHI, BAHI, Berita Acara, SPTJM, Surat Koreksi, Eksekutif" color="purple" />
            <WorkflowStep number="06" title="Pengesahan, Kunci & Backup" description="Unggah PDF laporan bertanda tangan lalu sahkan — kegiatan terkunci permanen, riwayat masuk Kartu Inventarisasi; cetak kartu BMN & backup penuh" color="cyan" isLast />
          </div>
        </CollapsibleSection>

        <CollapsibleSection id="harga" title="Harga, Lisensi & RAB" icon={DollarSign}>
          {/* ── Skema Lisensi ── */}
          <div className="grid md:grid-cols-3 gap-4 mb-6">
            <PriceTier
              name="Lisensi Satker Tunggal"
              price="Rp 55 juta"
              unit="/ tahun"
              tagline="Satu satuan kerja, pengguna tidak dibatasi"
              features={[
                "Semua fitur (offline, real-time, 13+ laporan, pengesahan)",
                "Update versi & perbaikan bug",
                "Dukungan teknis jam kerja",
                "Instalasi di server satker (on-premise) atau VPS sendiri",
              ]}
            />
            <PriceTier
              name="Multi-Satker / Instansi"
              price="Rp 175 juta"
              unit="/ tahun"
              tagline="Hingga 10 satker dalam satu instansi"
              highlight
              features={[
                "Semua benefit Satker Tunggal",
                "Kop surat & pengaturan laporan per satker",
                "Dukungan prioritas + pendampingan implementasi",
                "Pelatihan pengguna (2 sesi / tahun)",
              ]}
            />
            <PriceTier
              name="Perpetual + Source Code"
              price="Rp 500 juta"
              unit="sekali bayar"
              tagline="Hak pakai selamanya + kendali penuh"
              features={[
                "Lisensi permanen tanpa biaya tahunan wajib",
                "Serah terima source code lengkap + dokumentasi",
                "Transfer knowledge ke tim TI instansi",
                "Dukungan teknis 12 bulan pertama",
              ]}
            />
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5 mb-8">
            <h4 className="font-semibold text-white mb-3">Mengapa Harga Ini Wajar?</h4>
            <ul className="grid md:grid-cols-2 gap-x-6 gap-y-2 text-sm text-slate-300">
              {[
                "Fitur setara sistem enterprise: offline-first penuh (snapshot + antrian sinkron), kolaborasi real-time multi-user yang teruji (OCC, locking, WebSocket ber-JWT)",
                "13+ laporan resmi format Kemenkeu siap tanda tangan — menggantikan penyusunan manual berhari-hari tiap kegiatan",
                "Alur pengesahan berkekuatan dokumen + kunci permanen + audit trail per field — akuntabilitas pemeriksaan/audit BPK",
                "Pembanding: membangun sistem serupa dari nol ± Rp 191,5 juta di tahun pertama (lihat RAB di bawah) — belum termasuk risiko kegagalan proyek",
                "Biaya tahunan sudah mencakup pemeliharaan, update, dan dukungan teknis (komponen terbesar biaya operasional aplikasi pemerintah)",
                "Tanpa biaya per-user — seluruh tim inventarisasi dapat bekerja bersamaan",
              ].map((r, i) => (
                <li key={i} className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{r}</span>
                </li>
              ))}
            </ul>
            <p className="text-xs text-slate-500 mt-3 italic">
              Harga di atas adalah acuan penawaran; nilai final mengikuti negosiasi, lingkup kustomisasi, dan ketentuan pengadaan yang berlaku.
            </p>
          </div>

          {/* ── RAB referensi (biaya membangun & mengoperasikan sendiri) ── */}
          <h4 className="font-semibold text-white mb-3">Referensi RAB — Membangun & Mengoperasikan Sendiri</h4>
          <RABTable />
          <div className="mt-6 grid md:grid-cols-2 gap-4">
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
              <h4 className="font-semibold text-white mb-3">Biaya Operasional Tahunan (Tahun 2+)</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-slate-400">Cloud Server</span><span className="text-slate-300">Rp 18.000.000</span></div>
                <div className="flex justify-between"><span className="text-slate-400">MongoDB Atlas</span><span className="text-slate-300">Rp 9.600.000</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Domain & SSL</span><span className="text-slate-300">Rp 500.000</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Backup Storage</span><span className="text-slate-300">Rp 2.400.000</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Maintenance & Support</span><span className="text-slate-300">Rp 36.000.000</span></div>
                <div className="flex justify-between border-t border-slate-700 pt-2 mt-2"><span className="text-white font-semibold">Total per Tahun</span><span className="text-blue-400 font-bold">Rp 66.500.000</span></div>
              </div>
            </div>
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
              <h4 className="font-semibold text-white mb-3">Total Investasi 3 Tahun</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-slate-400">Tahun 1 (Dev + Infra + Ops)</span><span className="text-slate-300">Rp 191.500.000</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Tahun 2 (Infra + Ops)</span><span className="text-slate-300">Rp 66.500.000</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Tahun 3 (Infra + Ops)</span><span className="text-slate-300">Rp 66.500.000</span></div>
                <div className="flex justify-between border-t border-slate-700 pt-2 mt-2"><span className="text-white font-semibold">Grand Total</span><span className="text-blue-400 font-bold text-lg">Rp 324.500.000</span></div>
              </div>
            </div>
          </div>
        </CollapsibleSection>

        <CollapsibleSection id="timeline" title="Timeline Implementasi" icon={Calendar}>
          <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {[
              { period: "Bulan 1-2", title: "Analisis & Desain", items: ["Requirement gathering", "UI/UX prototyping", "Desain database"], color: "blue" },
              { period: "Bulan 3-5", title: "Pengembangan Core", items: ["Backend API", "Frontend UI", "Database setup"], color: "green" },
              { period: "Bulan 6-7", title: "Integrasi & Testing", items: ["Module integration", "UAT & bug fixing", "Performance tuning"], color: "orange" },
              { period: "Bulan 8", title: "Deployment", items: ["Production deploy", "Data migration", "User training"], color: "purple" },
              { period: "Bulan 9-12", title: "Maintenance", items: ["Bug fixes", "Feature updates", "Technical support"], color: "cyan" },
            ].map((phase, i) => (
              <div key={i} className="text-center">
                <div className={`text-xs font-bold mb-2 ${
                  phase.color === "blue" ? "text-blue-400" :
                  phase.color === "green" ? "text-emerald-400" :
                  phase.color === "orange" ? "text-orange-400" :
                  phase.color === "purple" ? "text-purple-400" : "text-cyan-400"
                }`}>{phase.period}</div>
                <div className={`h-2 rounded-full mb-3 ${
                  phase.color === "blue" ? "bg-blue-500" :
                  phase.color === "green" ? "bg-emerald-500" :
                  phase.color === "orange" ? "bg-orange-500" :
                  phase.color === "purple" ? "bg-purple-500" : "bg-cyan-500"
                }`} />
                <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3">
                  <div className="text-sm font-semibold text-white mb-2">{phase.title}</div>
                  {phase.items.map((item, j) => (
                    <div key={j} className="text-xs text-slate-400">{item}</div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>

        {/* ── PERAN PENGGUNA ── */}
        <CollapsibleSection id="peran" title="Peran Pengguna" icon={Users}>
          <div className="grid md:grid-cols-3 gap-4">
            {[
              { role: "Admin", color: "blue", icon: Lock, desc: "Full akses ke semua fitur", perms: ["Kelola kegiatan & kategori", "Manajemen user & role", "Pengesahan & kunci kegiatan", "Import/Export, Backup & Reset", "Semua fitur operator"] },
              { role: "Operator", color: "green", icon: FileText, desc: "Input dan edit data inventarisasi", perms: ["CRUD data aset (termasuk offline)", "Upload foto, dokumen & BAST", "Kelola stiker & scan QR", "Lihat dashboard & statistik"] },
              { role: "Viewer", color: "orange", icon: Monitor, desc: "Akses read-only untuk monitoring", perms: ["Lihat semua data aset", "Export laporan", "Cetak kartu BMN", "Lihat rekapitulasi & kartu inventarisasi"] },
            ].map((item, i) => (
              <div key={i} className={`border ${
                item.color === "blue" ? "border-blue-500/30" :
                item.color === "green" ? "border-emerald-500/30" : "border-orange-500/30"
              } bg-slate-800/30 rounded-xl p-5`}>
                <div className="flex items-center gap-2 mb-2">
                  <item.icon className={`w-5 h-5 ${
                    item.color === "blue" ? "text-blue-400" :
                    item.color === "green" ? "text-emerald-400" : "text-orange-400"
                  }`} />
                  <h4 className="font-bold text-white">{item.role}</h4>
                </div>
                <p className="text-sm text-slate-400 mb-3">{item.desc}</p>
                <ul className="space-y-1.5">
                  {item.perms.map((perm, j) => (
                    <li key={j} className="text-xs text-slate-300 flex items-center gap-1.5">
                      <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                      {perm}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </CollapsibleSection>

        {/* ── FOOTER ── */}
        <div className="text-center py-12 mt-8 border-t border-slate-800">
          <div className="flex items-center justify-center gap-2 mb-3">
            <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
              <Package className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-white">AMAN — Aplikasi Manajemen Aset Negara</span>
          </div>
          <p className="text-sm text-slate-500">
            Sistem Inventarisasi Barang Milik Negara (BMN) — sebelumnya InventoryMaster Pro
          </p>
          <p className="text-xs text-slate-600 mt-2">
            &copy; {new Date().getFullYear()} AMAN v2.3 | Product Requirements Document
          </p>
        </div>
      </div>
    </div>
  );
}
