import React, { useState, useCallback } from "react";
import { ArrowLeft, Download, FileText, Presentation, ChevronDown, ChevronRight, Package, Shield, Users, Camera, Upload, BarChart3, FileSpreadsheet, Printer, RefreshCw, Globe, CheckCircle2, XCircle, Clock, Layers, Database, Server, Monitor, Wifi, Lock, Zap, BookOpen, DollarSign, Calendar, Target, AlertTriangle } from "lucide-react";
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
    <div className="flex items-start gap-4">
      <div className="flex flex-col items-center">
        <div className={`w-10 h-10 rounded-full ${colorMap[color]} flex items-center justify-center text-white font-bold text-sm shadow-lg`}>
          {number}
        </div>
        {!isLast && <div className="w-0.5 h-16 bg-slate-700 mt-2" />}
      </div>
      <div className="pb-8">
        <h4 className="font-semibold text-white">{title}</h4>
        <p className="text-sm text-slate-400 mt-1">{description}</p>
      </div>
    </div>
  );
}

function CollapsibleSection({ title, icon: Icon, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-700/50 rounded-xl overflow-hidden mb-4">
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
          <li key={i} className="text-xs text-slate-400">{item}</li>
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
      <table className="w-full text-sm">
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
                    <td className="px-3 py-2 text-right text-slate-400">{fmt(item.price)}</td>
                    <td className="px-3 py-2 text-right text-slate-300 font-medium">{fmt(item.vol * item.price)}</td>
                  </tr>
                ))}
                <tr className="bg-slate-800/50">
                  <td colSpan={5} className="px-3 py-2 text-right text-slate-400 text-xs font-medium">Subtotal {cat.label}</td>
                  <td className="px-3 py-2 text-right text-white font-semibold">{fmt(subtotal)}</td>
                </tr>
              </React.Fragment>
            );
          })}
          <tr className="bg-blue-600/30">
            <td colSpan={5} className="px-3 py-3 text-right text-white font-bold rounded-bl-lg">TOTAL KESELURUHAN</td>
            <td className="px-3 py-3 text-right text-blue-300 font-bold text-base rounded-br-lg">Rp {fmt(grandTotal)}</td>
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
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <button onClick={onBack} className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm">
            <ArrowLeft className="w-4 h-4" />
            <span>Kembali</span>
          </button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-blue-500 rounded-lg flex items-center justify-center">
              <Package className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-white text-sm">InventoryMaster Pro</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => handleDownload("ppt")}
              disabled={!!downloading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-orange-500/20 border border-orange-500/30 text-orange-300 rounded-lg text-xs hover:bg-orange-500/30 transition-colors disabled:opacity-50"
            >
              <Presentation className="w-3.5 h-3.5" />
              {downloading === "ppt" ? "..." : "PPT"}
            </button>
            <button
              onClick={() => handleDownload("proposal")}
              disabled={!!downloading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/20 border border-blue-500/30 text-blue-300 rounded-lg text-xs hover:bg-blue-500/30 transition-colors disabled:opacity-50"
            >
              <FileText className="w-3.5 h-3.5" />
              {downloading === "proposal" ? "..." : "Proposal"}
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-10">
        {/* ── HERO ── */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-blue-500/10 border border-blue-500/20 rounded-full text-blue-400 text-xs mb-6">
            <Zap className="w-3.5 h-3.5" />
            Product Requirements Document
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4 leading-tight">
            Sistem Inventarisasi<br />
            <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">Aset Terpadu</span>
          </h1>
          <p className="text-lg text-slate-400 max-w-2xl mx-auto mb-8">
            Solusi digital komprehensif untuk pengelolaan inventarisasi Barang Milik Negara (BMN) sesuai SE-17/MK.1/2024 Kementerian Keuangan RI
          </p>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto">
            <StatCard icon={Layers} value="18+" label="Modul Fitur" color="blue" />
            <StatCard icon={Database} value="1,475+" label="Aset Terdata" color="green" />
            <StatCard icon={FileSpreadsheet} value="5" label="Format Export" color="orange" />
            <StatCard icon={Users} value="Multi" label="User Real-time" color="purple" />
          </div>
        </div>

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
        <CollapsibleSection title="Latar Belakang & Dasar Hukum" icon={BookOpen} defaultOpen={true}>
          <div className="grid md:grid-cols-2 gap-8">
            <div>
              <h4 className="font-semibold text-white mb-3">Mengapa Sistem Ini Dibutuhkan?</h4>
              <div className="space-y-3">
                {[
                  { icon: AlertTriangle, color: "text-red-400", title: "Pencatatan Manual", desc: "Spreadsheet rawan kesalahan, duplikasi data, dan sulit diaudit" },
                  { icon: XCircle, color: "text-orange-400", title: "Tidak Real-time", desc: "Perubahan tidak tersinkronisasi antar tim, data tidak konsisten" },
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

        <CollapsibleSection title="Arsitektur & Teknologi" icon={Server} defaultOpen={true}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <ArchBlock icon={Monitor} title="Frontend" items={["React 18 + Tailwind CSS", "Shadcn/UI Components", "Virtualized Table (1000+ rows)", "Responsive & Dark Mode"]} color="blue" />
            <ArchBlock icon={Server} title="Backend" items={["Python FastAPI (Async)", "WebSocket Real-time", "RESTful API + CORS", "JWT Authentication"]} color="green" />
            <ArchBlock icon={Database} title="Database" items={["MongoDB 7.0", "GridFS Photo Storage", "Compound Indexes", "UUID-based Records"]} color="orange" />
            <ArchBlock icon={Globe} title="Infrastructure" items={["Docker + Kubernetes", "Nginx Reverse Proxy", "Supervisor Process Mgr", "SSL/TLS Encryption"]} color="purple" />
          </div>
          <div className="flex items-center justify-center gap-2 flex-wrap py-4">
            {["User Browser", "React SPA", "K8s Ingress", "FastAPI", "MongoDB + GridFS"].map((item, i, arr) => (
              <React.Fragment key={i}>
                <span className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-300">{item}</span>
                {i < arr.length - 1 && <span className="text-blue-400 font-bold">→</span>}
              </React.Fragment>
            ))}
          </div>
        </CollapsibleSection>

        <CollapsibleSection title="Fitur & Fungsionalitas (18+ Modul)" icon={Layers}>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <FeatureCard icon={Package} title="CRUD Aset" description="Tambah, edit, hapus aset dengan validasi lengkap dan 30+ field data" color="blue" items={["Inline editing dengan auto-save", "Validasi kode aset 10 digit", "Multi-criteria search & filter"]} />
            <FeatureCard icon={Camera} title="Multi-Photo" description="Upload hingga 10 foto per aset dengan kompresi otomatis" color="green" items={["Thumbnail generation otomatis", "Cover photo selection", "Gallery view mode"]} />
            <FeatureCard icon={BarChart3} title="Dashboard Analytics" description="Statistik real-time dengan grafik kondisi & status aset" color="orange" items={["Pie chart kondisi aset", "Progress inventarisasi", "Breakdown per kategori"]} />
            <FeatureCard icon={Upload} title="Import CSV Massal" description="Import ribuan data sekaligus dengan validasi per baris" color="purple" items={["Preview sebelum import", "Error indicator per baris", "Template CSV tersedia"]} />
            <FeatureCard icon={FileSpreadsheet} title="Export Multi-Format" description="PDF, Excel, CSV dengan foto dan layout profesional" color="red" items={["PDF dengan foto aset", "XLSX lengkap semua field", "CSV untuk integrasi"]} />
            <FeatureCard icon={CheckCircle2} title="Stiker Inventaris" description="Kelola status & foto stiker yang terpasang pada aset" color="cyan" items={["Status: Terpasang/Tidak", "Ukuran: Kecil/Sedang/Besar", "Upload foto stiker"]} />
            <FeatureCard icon={FileText} title="Dokumen Checklist" description="Checklist kelengkapan dokumen dengan upload file" color="pink" items={["Status centang per item", "Upload PDF & foto", "Catatan tambahan"]} />
            <FeatureCard icon={Users} title="Multi-User" description="Role admin/pencatat/viewer dengan audit trail" color="teal" items={["Role-based access control", "Row locking saat edit", "Online indicator"]} />
            <FeatureCard icon={Wifi} title="Real-time Sync" description="WebSocket untuk update langsung antar pengguna" color="blue" items={["Live notification", "Conflict prevention", "Auto-refresh data"]} />
            <FeatureCard icon={FileText} title="Rekapitulasi SE-17" description="Laporan otomatis sesuai format SE-17/MK.1/2024" color="green" items={["Berita Acara PDF", "SPTJM otomatis", "Surat Koreksi"]} />
            <FeatureCard icon={Printer} title="Kartu BMN" description="Cetak kartu inventaris format KTP per aset" color="orange" items={["Foto aset otomatis", "Kode aset & NUP", "Bulk print support"]} />
            <FeatureCard icon={RefreshCw} title="Backup & Restore" description="Backup dan restore seluruh data per kegiatan" color="purple" items={["Full data backup", "One-click restore", "Export JSON format"]} />
          </div>
        </CollapsibleSection>

        <CollapsibleSection title="Klasifikasi SE-17/MK.1/2024" icon={Shield}>
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
              <p className="text-sm text-slate-400 mb-3">Sub-klasifikasi detail:</p>
              <ul className="space-y-2 text-sm text-slate-300">
                <li>• Kesalahan Pencatatan → Koreksi data</li>
                <li>• Dipindahtangankan → Proses transfer</li>
                <li>• Penghapusan/BMN Hilang → Proses hapus</li>
                <li>• Tidak Ditemukan Lainnya → Investigasi</li>
              </ul>
            </div>
            <div className="bg-slate-500/5 border border-slate-500/20 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <Clock className="w-6 h-6 text-slate-400" />
                <h4 className="font-bold text-slate-400">Belum Diinventarisasi</h4>
              </div>
              <p className="text-sm text-slate-400 mb-3">Status default untuk aset yang belum dicek</p>
              <ul className="space-y-2 text-sm text-slate-300">
                <li>• Default saat data di-import</li>
                <li>• Menunggu pengecekan fisik</li>
                <li>• Dashboard menampilkan progress %</li>
              </ul>
            </div>
          </div>
        </CollapsibleSection>

        <CollapsibleSection title="Alur Kerja Inventarisasi" icon={Target}>
          <div className="max-w-xl mx-auto">
            <WorkflowStep number="01" title="Buat Kegiatan Inventarisasi" description="Admin membuat kegiatan baru, mengatur parameter, dan menambahkan kategori aset" color="blue" />
            <WorkflowStep number="02" title="Siapkan Data Aset" description="Import data BMN dari SIMAN/CSV atau input manual per aset" color="green" />
            <WorkflowStep number="03" title="Pelaksanaan Inventarisasi" description="Tim lapangan mencatat kondisi, foto, stiker, dan dokumen pendukung" color="orange" />
            <WorkflowStep number="04" title="Verifikasi & Klasifikasi" description="Admin memverifikasi data dan mengklasifikasikan aset tidak ditemukan" color="red" />
            <WorkflowStep number="05" title="Rekapitulasi & Laporan" description="Generate laporan otomatis: Berita Acara, SPTJM, Surat Koreksi" color="purple" />
            <WorkflowStep number="06" title="Selesai & Backup" description="Export final, cetak kartu BMN, backup data kegiatan" color="cyan" isLast />
          </div>
        </CollapsibleSection>

        <CollapsibleSection title="Rencana Anggaran Biaya (RAB)" icon={DollarSign}>
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

        <CollapsibleSection title="Timeline Implementasi" icon={Calendar}>
          <div className="grid grid-cols-5 gap-3">
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
        <CollapsibleSection title="Peran Pengguna" icon={Users}>
          <div className="grid md:grid-cols-3 gap-4">
            {[
              { role: "Admin", color: "blue", icon: Lock, desc: "Full akses ke semua fitur", perms: ["Kelola kegiatan & kategori", "Manajemen user & role", "Import/Export data", "Reset & Backup system", "Semua fitur pencatat"] },
              { role: "Pencatat", color: "green", icon: FileText, desc: "Input dan edit data inventarisasi", perms: ["CRUD data aset", "Upload foto & dokumen", "Kelola stiker inventaris", "Lihat dashboard & statistik"] },
              { role: "Viewer", color: "orange", icon: Monitor, desc: "Akses read-only untuk monitoring", perms: ["Lihat semua data aset", "Export laporan", "Cetak kartu BMN", "Lihat rekapitulasi"] },
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
            <span className="font-bold text-white">InventoryMaster Pro</span>
          </div>
          <p className="text-sm text-slate-500">
            Sistem Inventarisasi Aset Terpadu — Barang Milik Negara (BMN)
          </p>
          <p className="text-xs text-slate-600 mt-2">
            &copy; {new Date().getFullYear()} InventoryMaster Pro | Product Requirements Document
          </p>
        </div>
      </div>
    </div>
  );
}
