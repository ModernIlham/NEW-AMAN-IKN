import React, { useState, useEffect, useCallback, memo } from "react";
import { History, X, ChevronLeft, ChevronRight, ChevronDown, User, Clock, Plus, Edit3, Trash2, Layers, FileUp, Users, Package, ShieldCheck, ShieldAlert, RefreshCw, Server, Download } from "lucide-react";
import { Button } from "../ui/button";
import axios from "axios";

import { downloadFileWithProgress } from "../../lib/downloadFile";
import { barisTemuan, jalurDetail, jumlahDetail, MAKS_TEMUAN_TAMPIL } from "../../lib/integritasDetail";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Label manusiawi untuk jenis temuan integritas (§5A) — sinkron dengan nilai
// field `masalah` dari endpoint backend /integritas/*.
const MASALAH_LABEL = {
  snapshot_basi: "Identitas basi",
  aset_master_hilang: "Aset induk hilang",
  golongan_tak_terdaftar: "Golongan tak terdaftar",
  kode_spesifik_tak_terdaftar: "Kode tak terdaftar",
  panjang_kode_tak_valid: "Panjang kode tak valid",
};

const ACTION_MAP = {
  create: { label: "Tambah", color: "text-emerald-600", bg: "bg-emerald-500", dot: "bg-emerald-500" },
  update: { label: "Edit", color: "text-blue-600", bg: "bg-blue-500", dot: "bg-blue-500" },
  delete: { label: "Hapus", color: "text-red-600", bg: "bg-red-500", dot: "bg-red-500" },
  bulk_delete: { label: "Hapus Massal", color: "text-red-600", bg: "bg-red-500", dot: "bg-red-500" },
  import: { label: "Import", color: "text-purple-600", bg: "bg-purple-500", dot: "bg-purple-500" },
  sahkan: { label: "Pengesahan", color: "text-amber-600", bg: "bg-amber-500", dot: "bg-amber-500" },
  pengesahan_dokumen: { label: "Dokumen Pengesahan", color: "text-amber-600", bg: "bg-amber-500", dot: "bg-amber-500" },
  penghapusan: { label: "Penghapusan (SK)", color: "text-rose-600", bg: "bg-rose-500", dot: "bg-rose-500" },
  // Penempatan denah. Tanpa entri ini ketiganya jatuh ke label cadangan
  // "Edit" (lihat TimelineEntry) — sehingga penempatan lokasi otomatis yang
  // menyertai satu simpanan aset terbaca sebagai suntingan kedua.
  aset_lokasi_otomatis: { label: "Lokasi Otomatis", color: "text-cyan-600", bg: "bg-cyan-500", dot: "bg-cyan-500" },
  aset_lokasi_tandai: { label: "Tandai Lokasi", color: "text-cyan-600", bg: "bg-cyan-500", dot: "bg-cyan-500" },
  aset_lokasi_hapus: { label: "Cabut Lokasi", color: "text-amber-600", bg: "bg-amber-500", dot: "bg-amber-500" },
  // Log SISTEM (tanpa kegiatan): master pegawai & kartu pegawai UID.
  buat_pegawai: { label: "Pegawai Baru", color: "text-emerald-600", bg: "bg-emerald-500", dot: "bg-emerald-500" },
  ubah_pegawai: { label: "Ubah Pegawai", color: "text-blue-600", bg: "bg-blue-500", dot: "bg-blue-500" },
  hapus_pegawai: { label: "Hapus Pegawai", color: "text-red-600", bg: "bg-red-500", dot: "bg-red-500" },
  impor_pegawai: { label: "Impor Pegawai", color: "text-purple-600", bg: "bg-purple-500", dot: "bg-purple-500" },
  foto_pegawai: { label: "Foto Pegawai", color: "text-blue-600", bg: "bg-blue-500", dot: "bg-blue-500" },
  daftar_kartu: { label: "Daftar Kartu", color: "text-emerald-600", bg: "bg-emerald-500", dot: "bg-emerald-500" },
  lepas_kartu: { label: "Lepas Kartu", color: "text-amber-600", bg: "bg-amber-500", dot: "bg-amber-500" },
  kartu_tak_dikenal: { label: "Kartu Tak Dikenal", color: "text-rose-600", bg: "bg-rose-500", dot: "bg-rose-500" },
};

// Backend menulis ±150 jenis aksi; ACTION_MAP di atas hanya menamai sebagian.
// Sisanya dulu jatuh ke gaya `update` — sehingga panel MENGKLAIM "Edit" atas
// hal yang jelas bukan suntingan: penempatan denah otomatis, buka tiket TGR,
// booking nomor surat. Itulah yang membuat satu simpanan aset terbaca sebagai
// dua kali edit. Aksi tak dikenal kini dieja dari namanya sendiri dengan gaya
// netral — jujur, dan kebetulan jauh lebih informatif.
export const konfigAksi = (action) =>
  ACTION_MAP[action] || {
    label: String(action || "aktivitas").replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase()),
    color: "text-slate-600", bg: "bg-slate-400", dot: "bg-slate-400",
  };

const FIELD_LABELS = {
  asset_name: "Nama", category: "Kategori", brand: "Brand", model: "Model",
  kode_register: "Kode Register", serial_number: "Serial Number",
  purchase_date: "Tgl Beli", purchase_price: "Harga", location: "Lokasi",
  department: "Departemen (lama)", user: "Pengguna", condition: "Kondisi", status: "Status",
  NUP: "NUP", notes: "Catatan", stiker_status: "Stiker", stiker_ukuran: "Ukuran Stiker",
  inventory_status: "Status Inventarisasi", klasifikasi_tidak_ditemukan: "Klasifikasi Tidak Ditemukan",
  sub_klasifikasi: "Sub Klasifikasi", uraian_tidak_ditemukan: "Uraian Tidak Ditemukan", tindak_lanjut: "Tindak Lanjut",
  koordinat_latitude: "Latitude", koordinat_longitude: "Longitude", kronologis: "Kronologis",
  nomor_spm: "No. SPM", perolehan_dari_nama: "Perolehan Dari", nomor_kontrak: "No. Kontrak",
  cara_bayar_kontrak: "Cara Bayar Kontrak",
  nomor_bukti_perolehan: "No. Bukti", supplier: "Supplier",
  pengguna_melekat_ke: "Melekat Ke", pengguna_jabatan: "Jabatan Pengguna",
  operasional_jenis: "Jenis Operasional", nomor_bast: "No. BAST",
  keterangan_berlebih: "Keterangan Berlebih", asal_usul_berlebih: "Asal Usul Berlebih",
  nomor_perkara: "No. Perkara", pihak_bersengketa: "Pihak Bersengketa", keterangan_sengketa: "Keterangan Sengketa",
};

const timeAgo = (ts) => {
  if (!ts) return "-";
  const d = new Date(ts);
  const now = new Date();
  const s = (now - d) / 1000;
  if (s < 60) return "Baru saja";
  if (s < 3600) return `${Math.floor(s / 60)}m lalu`;
  if (s < 86400) return `${Math.floor(s / 3600)}j lalu`;
  if (s < 604800) return `${Math.floor(s / 86400)}h lalu`;
  return d.toLocaleDateString("id-ID", { day: "numeric", month: "short" });
};

const fullDate = (ts) => {
  if (!ts) return "-";
  const d = new Date(ts);
  return d.toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" });
};

// ============================================================================
// Timeline Entry - Clean design with timeline line
// ============================================================================
export const TimelineEntry = memo(({ log, showAssetInfo }) => {
  const config = konfigAksi(log.action);
  const [showDetail, setShowDetail] = useState(false);
  const hasChanges = log.changes && log.changes.length > 0;

  return (
    <div className="flex gap-2.5 group" data-testid={`audit-entry-${log.id}`}>
      {/* Timeline dot + line */}
      <div className="flex flex-col items-center pt-1">
        <div className={`w-2.5 h-2.5 rounded-full ${config.dot} ring-2 ring-background flex-shrink-0`} />
        <div className="w-px flex-1 bg-muted mt-1" />
      </div>
      
      {/* Content */}
      <div className="flex-1 pb-4 min-w-0">
        {/* Header line: action + time */}
        <div className="flex items-center justify-between gap-1">
          <span className={`text-[11px] font-bold ${config.color}`}>{config.label}</span>
          <span className="text-[10px] text-muted-foreground flex-shrink-0" title={fullDate(log.timestamp)}>{timeAgo(log.timestamp)}</span>
        </div>
        
        {/* Asset info (shown in global/user view) */}
        {showAssetInfo && log.asset_code && (
          <p className="text-[11px] text-foreground font-medium truncate mt-0.5">
            <span className="font-mono">{log.asset_code}</span>
            {log.nup && <span className="text-blue-600 font-semibold"> / {log.nup}</span>}
            {log.asset_name && <span className="text-muted-foreground font-normal"> - {log.asset_name}</span>}
          </p>
        )}
        
        {/* Keterangan. Dulu hanya tampil bila log TIDAK punya asset_code —
            akibatnya keterangan yang justru paling menjelaskan ("Gedung A /
            Lantai 2 / Ruang 305", "Putar foto #1 sebesar 90°", "Dokumen BAST
            diunggah") tak pernah terbaca, dan barisnya tampak kosong. */}
        {log.detail && (
          <p className="text-[11px] text-muted-foreground mt-0.5">{log.detail}</p>
        )}
        
        {/* User */}
        <p className="text-[10px] text-muted-foreground mt-0.5">oleh <span className="font-medium text-muted-foreground">{log.username || "unknown"}</span></p>
        
        {/* Changes toggle */}
        {hasChanges && (
          <>
            <button
              onClick={() => setShowDetail(!showDetail)}
              className="text-[10px] text-blue-500 hover:text-blue-700 mt-0.5 font-medium"
              data-testid="toggle-changes"
            >
              {showDetail ? "Sembunyikan detail" : `${log.changes.length} field diubah`}
            </button>
            {showDetail && (
              <div className="mt-1 rounded border border-border divide-y divide-border overflow-hidden">
                {log.changes.map((c, i) => (
                  <div key={i} className="px-2 py-1 text-[10px] bg-card">
                    <span className="font-medium text-muted-foreground">{FIELD_LABELS[c.field] || c.field}</span>
                    <div className="flex items-center gap-1 mt-0.5">
                      <span className="text-red-400 line-through truncate max-w-[100px]">{c.from || "(kosong)"}</span>
                      <span className="text-muted-foreground">&rarr;</span>
                      <span className="text-emerald-600 font-medium truncate max-w-[100px]">{c.to || "(kosong)"}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
});
TimelineEntry.displayName = "TimelineEntry";

// ============================================================================
// User Activity Summary - Groups logs by user
// ============================================================================
const UserSummary = memo(({ logs, onSelectUser, selectedUser }) => {
  // Group by username
  const grouped = {};
  logs.forEach(log => {
    const u = log.username || "unknown";
    if (!grouped[u]) grouped[u] = { create: 0, update: 0, delete: 0, total: 0, logs: [] };
    grouped[u][log.action] = (grouped[u][log.action] || 0) + 1;
    grouped[u].total++;
    grouped[u].logs.push(log);
  });

  const users = Object.entries(grouped).sort((a, b) => b[1].total - a[1].total);

  if (users.length === 0) return null;

  return (
    <div className="space-y-2" data-testid="audit-user-summary">
      <div className="flex items-center justify-between px-1">
        <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Aktivitas Per User</div>
        {selectedUser && (
          <button onClick={() => onSelectUser("")} className="text-[10px] text-blue-500 hover:text-blue-700 font-medium" data-testid="audit-clear-user-filter">Tampilkan semua</button>
        )}
      </div>
      {users.map(([username, data]) => {
        const isSelected = selectedUser === username;
        return (
          <div 
            key={username}
            onClick={() => onSelectUser(isSelected ? "" : username)}
            className={`rounded-lg p-2 border cursor-pointer transition-all ${isSelected ? 'bg-blue-50 dark:bg-blue-900/30 border-blue-300 dark:border-blue-700 ring-1 ring-blue-200 dark:ring-blue-800' : 'bg-muted/50 dark:bg-muted/30 border-border hover:border-foreground/30'}`}
            data-testid={`audit-user-card-${username}`}
          >
            <div className="flex items-center gap-1.5 mb-1.5">
              <div className={`w-5 h-5 rounded-full flex items-center justify-center ${isSelected ? 'bg-blue-200 dark:bg-blue-800' : 'bg-blue-100 dark:bg-blue-900/50'}`}>
                <User className="w-3 h-3 text-blue-600 dark:text-blue-400" />
              </div>
              <span className="text-xs font-semibold text-foreground">{username}</span>
              <span className="text-[10px] text-muted-foreground ml-auto">{data.total} aksi</span>
            </div>
            <div className="flex gap-2">
              {data.create > 0 && (
                <span className="text-[10px] bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400 px-1.5 py-0.5 rounded font-medium">+{data.create} tambah</span>
              )}
              {data.update > 0 && (
              <span className="text-[10px] bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400 px-1.5 py-0.5 rounded font-medium">{data.update} edit</span>
            )}
            {data.delete > 0 && (
              <span className="text-[10px] bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400 px-1.5 py-0.5 rounded font-medium">-{data.delete} hapus</span>
            )}
          </div>
        </div>
        );
      })}
    </div>
  );
});
UserSummary.displayName = "UserSummary";

// ============================================================================
// Integritas Data (§5A) — dasbor read-only gabungan dari /integritas/ringkasan
// ============================================================================

// Rincian temuan satu register: dimuat MALAS saat kartunya dibuka (tiap
// endpoint detail = scan lintas-koleksi; jangan tarik enam-enamnya sekaligus).
const RincianTemuan = memo(({ register, muat }) => {
  const status = muat?.status;
  if (status === "muat") {
    return (
      <div className="flex items-center gap-1.5 pt-2 pl-1 text-muted-foreground">
        <div className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-[10px]">Memuat rincian…</span>
      </div>
    );
  }
  if (status === "galat") {
    return <p className="text-[10px] text-rose-500 pt-2 pl-1">Gagal memuat rincian — ketuk lagi untuk mencoba.</p>;
  }
  if (status !== "siap") return null;

  const items = Array.isArray(muat.data?.items) ? muat.data.items : [];
  const total = jumlahDetail(register, muat.data);
  const tampil = items.slice(0, MAKS_TEMUAN_TAMPIL);
  // Sisa = yang tak dirender DAN yang sudah dipangkas server (kategori
  // kodefikasi membatasi `items` di 300). Tanpa ini daftar terlihat lengkap.
  const sisa = Math.max(0, total - tampil.length);

  if (!tampil.length) {
    return <p className="text-[10px] text-muted-foreground pt-2 pl-1">Rincian tak tersedia.</p>;
  }
  return (
    <div className="mt-2 space-y-1" data-testid={`integritas-rincian-${register}`}>
      {tampil.map((it, i) => {
        const b = barisTemuan(register, it);
        return (
          <div key={i} className="rounded border border-border bg-muted/30 px-2 py-1.5">
            <div className="flex items-start gap-1.5">
              <span className="text-[10px] font-mono font-semibold text-foreground break-all min-w-0">{b.judul}</span>
              {b.masalah && (
                <span className="text-[9px] bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400 px-1 py-0.5 rounded ml-auto flex-shrink-0">
                  {MASALAH_LABEL[b.masalah] || b.masalah}
                </span>
              )}
            </div>
            {b.subjudul && <p className="text-[9px] text-muted-foreground mt-0.5">{b.subjudul}</p>}
            {b.beda.map((d, j) => (
              <div key={j} className="flex items-center gap-1 mt-0.5 text-[9px]">
                <span className="text-muted-foreground flex-shrink-0">{d.label}</span>
                <span className="text-red-400 line-through truncate">{d.dari}</span>
                <span className="text-muted-foreground flex-shrink-0">&rarr;</span>
                <span className="text-emerald-600 font-medium truncate">{d.ke}</span>
              </div>
            ))}
          </div>
        );
      })}
      {sisa > 0 && (
        <p className="text-[9px] text-muted-foreground pl-1">
          +{sisa} temuan lain tak ditampilkan — unduh CSV untuk daftar penuh.
        </p>
      )}
    </div>
  );
});
RincianTemuan.displayName = "RincianTemuan";

const IntegritasSummary = memo(({ data, loading, error, onRefresh, detail, onMuatDetail, onEkspor }) => {
  const [buka, setBuka] = useState("");
  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="text-center py-12 text-muted-foreground px-4">
        <ShieldAlert className="w-10 h-10 mx-auto mb-3 opacity-20" />
        <p className="text-xs font-medium">Gagal memuat ringkasan integritas</p>
        <button onClick={onRefresh} className="text-[10px] text-blue-500 hover:text-blue-700 font-medium mt-2 inline-flex items-center gap-1">
          <RefreshCw className="w-3 h-3" />Coba lagi
        </button>
      </div>
    );
  }
  if (!data) return null;
  const total = data.total_temuan || 0;
  const bagian = data.bagian || [];
  const bersih = total === 0;
  return (
    <div className="p-3 space-y-2.5" data-testid="integritas-summary">
      {/* Headline */}
      <div className={`rounded-lg p-3 border flex items-center gap-3 ${bersih ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800' : 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800'}`}>
        {bersih ? <ShieldCheck className="w-6 h-6 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
                : <ShieldAlert className="w-6 h-6 text-amber-600 dark:text-amber-400 flex-shrink-0" />}
        <div className="min-w-0">
          <p className={`text-sm font-bold ${bersih ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300'}`}>
            {bersih ? 'Data konsisten' : `${total} temuan`}
          </p>
          <p className="text-[10px] text-muted-foreground">
            {bersih ? 'Tidak ada masalah integritas terdeteksi' : `${data.jumlah_cek_bermasalah || 0} dari ${data.jumlah_cek || bagian.length} pemeriksaan bermasalah`}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2 flex-shrink-0">
          <button onClick={onEkspor} className="text-muted-foreground hover:text-foreground" title="Unduh ringkasan (CSV)" data-testid="integritas-ekspor">
            <Download className="w-3.5 h-3.5" />
          </button>
          <button onClick={onRefresh} className="text-muted-foreground hover:text-foreground" title="Muat ulang" data-testid="integritas-refresh">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Per register — kartu bertemuan bisa dibuka untuk melihat rinciannya */}
      {bagian.map((b) => {
        const jml = b.jumlah || 0;
        const perMasalah = b.per_masalah || {};
        const bisaBuka = jml > 0 && !!jalurDetail(b.register);
        const terbuka = buka === b.register;
        const bukaTutup = () => {
          if (!bisaBuka) return;
          const lanjut = terbuka ? "" : b.register;
          setBuka(lanjut);
          // Muat sekali; kegagalan sebelumnya boleh dicoba lagi saat dibuka.
          if (lanjut && detail?.[lanjut]?.status !== "siap") onMuatDetail(lanjut);
        };
        return (
          <div key={b.register} className={`rounded-lg p-2 border ${jml > 0 ? 'bg-card border-amber-200 dark:border-amber-900/50' : 'bg-muted/40 border-border'}`} data-testid={`integritas-register-${b.register}`}>
            <div
              className={`flex items-center gap-1.5 ${bisaBuka ? 'cursor-pointer' : ''}`}
              onClick={bukaTutup}
              role={bisaBuka ? "button" : undefined}
              tabIndex={bisaBuka ? 0 : undefined}
              onKeyDown={bisaBuka ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); bukaTutup(); } } : undefined}
              data-testid={bisaBuka ? `integritas-buka-${b.register}` : undefined}
            >
              {jml > 0 ? <ShieldAlert className="w-3 h-3 text-amber-500 flex-shrink-0" />
                       : <ShieldCheck className="w-3 h-3 text-emerald-500 flex-shrink-0" />}
              <span className="text-[11px] font-semibold text-foreground truncate">{b.label || b.register}</span>
              <span className={`text-[10px] ml-auto font-bold px-1.5 py-0.5 rounded ${jml > 0 ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400' : 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400'}`}>{jml}</span>
              {bisaBuka && (
                <ChevronDown className={`w-3 h-3 text-muted-foreground flex-shrink-0 transition-transform ${terbuka ? 'rotate-180' : ''}`} />
              )}
            </div>
            {jml > 0 && (
              <div className="flex flex-wrap gap-1 mt-1.5">
                {Object.entries(perMasalah).map(([m, c]) => (
                  <span key={m} className="text-[9px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded">
                    {(MASALAH_LABEL[m] || m)}: <span className="font-semibold text-foreground">{c}</span>
                  </span>
                ))}
              </div>
            )}
            {terbuka && <RincianTemuan register={b.register} muat={detail?.[b.register]} />}
          </div>
        );
      })}

      <p className="text-[9px] text-muted-foreground px-1 pt-1 leading-relaxed">
        Read-only (§5A): identitas snapshot basi di register hilir + kodefikasi FK aset.
        Ketuk kartu bertemuan untuk melihat rincian per temuan, atau unduh CSV lewat ikon panah.
        Tak mengubah data.
      </p>
    </div>
  );
});
IntegritasSummary.displayName = "IntegritasSummary";

// ============================================================================
// MAIN AUDIT LOG PANEL
// ============================================================================
const AuditLogPanel = memo(({ activityId, isOpen, onToggle, selectedAssetId, selectedAssetCode, onClearAssetFilter }) => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [viewMode, setViewMode] = useState("timeline"); // "timeline" | "user" | "integritas" | "sistem"
  const [filterUser, setFilterUser] = useState("");
  const [integritas, setIntegritas] = useState(null);
  const [integritasLoading, setIntegritasLoading] = useState(false);
  const [integritasError, setIntegritasError] = useState(false);
  // Rincian per register: {register: {status: "muat"|"siap"|"galat", data}}.
  const [detailIntegritas, setDetailIntegritas] = useState({});

  const fetchIntegritas = useCallback(async () => {
    setIntegritasLoading(true);
    setIntegritasError(false);
    setDetailIntegritas({});  // rincian lama basi terhadap ringkasan baru
    try {
      const r = await axios.get(`${API}/integritas/ringkasan`);
      setIntegritas(r.data);
    } catch (err) {
      console.error("Integritas fetch error:", err);
      setIntegritasError(true);
    } finally {
      setIntegritasLoading(false);
    }
  }, []);

  const muatDetailIntegritas = useCallback(async (register) => {
    const jalur = jalurDetail(register);
    if (!jalur) return;
    setDetailIntegritas((s) => ({ ...s, [register]: { status: "muat" } }));
    try {
      const r = await axios.get(`${API}${jalur}`);
      setDetailIntegritas((s) => ({ ...s, [register]: { status: "siap", data: r.data } }));
    } catch (err) {
      console.error("Integritas detail fetch error:", register, err);
      setDetailIntegritas((s) => ({ ...s, [register]: { status: "galat" } }));
    }
  }, []);

  const eksporIntegritas = useCallback(() => {
    downloadFileWithProgress(`${API}/integritas/ekspor-ringkasan`,
      "ringkasan_integritas.csv", { label: "ringkasan integritas" })
      .catch(() => { /* toast galat sudah ditampilkan helper */ });
  }, []);

  // Tab "Sistem": log tanpa kegiatan (master/kartu pegawai) — server yang
  // membatasi per satker user; filter kegiatan/aset tidak berlaku di sini.
  const sistemMode = viewMode === "sistem" && !selectedAssetId;

  const fetchLogs = useCallback(async (p = 1) => {
    setLoading(true);
    setLoadError(false);
    try {
      const params = new URLSearchParams({ page: String(p), page_size: "30" });
      if (sistemMode) {
        params.append("sistem", "true");
      } else {
        if (activityId) params.append("activity_id", activityId);
        if (selectedAssetId) params.append("asset_id", selectedAssetId);
      }
      const r = await axios.get(`${API}/audit-logs?${params}`);
      setLogs(r.data.logs || []);
      setTotalPages(r.data.total_pages || 1);
      setTotal(r.data.total || 0);
      setPage(p);
    } catch (err) {
      console.error("Audit log fetch error:", err);
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [activityId, selectedAssetId, sistemMode]);

  useEffect(() => {
    if (isOpen) {
      fetchLogs(1);
      // Auto-switch to timeline when viewing specific asset
      if (selectedAssetId) setViewMode("timeline");
    }
  }, [isOpen, fetchLogs, selectedAssetId]);

  // Muat ringkasan integritas saat tab-nya dibuka (sekali; tombol muat ulang
  // untuk menyegarkan). Scan lintas-register — jangan panggil kecuali diminta.
  useEffect(() => {
    if (isOpen && viewMode === "integritas" && !integritas && !integritasLoading && !integritasError) {
      fetchIntegritas();
    }
  }, [isOpen, viewMode, integritas, integritasLoading, integritasError, fetchIntegritas]);

  return (
    <>
      {/* Mobile: drawer geser masuk dari kanan + backdrop redup (tap untuk
          tutup) — persis seperti form edit. Desktop (lg): tetap panel flex
          yang menggeser konten seperti sebelumnya. */}
      {isOpen && <div className="fixed inset-0 bg-black/40 z-30 lg:hidden" onClick={onToggle} data-testid="audit-backdrop" />}
      <div
        className={`bg-card border-l border-border flex flex-col overflow-hidden h-full shadow-2xl lg:shadow-none transition-all duration-300 ease-in-out fixed lg:relative inset-y-0 right-0 z-40 lg:z-auto w-[85vw] sm:w-80 ${isOpen ? 'translate-x-0 lg:w-[340px] lg:min-w-[340px]' : 'translate-x-full lg:translate-x-0 lg:w-0 lg:min-w-0 lg:border-l-0'}`}
        data-testid="audit-log-panel"
      >
        {isOpen && (
        <>
          {/* Header */}
          <div className="px-3 pt-3 pb-2 border-b border-border flex-shrink-0">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <History className="w-4 h-4 text-blue-600" />
                <h3 className="text-xs font-bold text-foreground">Riwayat</h3>
                <span className="text-[10px] bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 px-1.5 py-0.5 rounded-full font-bold">{total}</span>
              </div>
              <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={onToggle} data-testid="audit-close-btn">
                <X className="w-3.5 h-3.5" />
              </Button>
            </div>
            
            {/* View mode tabs */}
            {!selectedAssetId && (
              <div className="flex bg-muted rounded-lg p-0.5 gap-0.5" data-testid="audit-view-tabs">
                <button
                  onClick={() => setViewMode("timeline")}
                  className={`flex-1 flex items-center justify-center gap-1 text-[10px] font-semibold py-1 rounded-md transition-colors ${viewMode === "timeline" ? 'bg-card text-blue-600 shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                  data-testid="audit-tab-timeline"
                >
                  <Package className="w-3 h-3" />Timeline
                </button>
                <button
                  onClick={() => setViewMode("user")}
                  className={`flex-1 flex items-center justify-center gap-1 text-[10px] font-semibold py-1 rounded-md transition-colors ${viewMode === "user" ? 'bg-card text-blue-600 shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                  data-testid="audit-tab-user"
                >
                  <Users className="w-3 h-3" />Per User
                </button>
                <button
                  onClick={() => setViewMode("integritas")}
                  className={`flex-1 flex items-center justify-center gap-1 text-[10px] font-semibold py-1 rounded-md transition-colors ${viewMode === "integritas" ? 'bg-card text-blue-600 shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                  data-testid="audit-tab-integritas"
                >
                  <ShieldCheck className="w-3 h-3" />Integritas
                </button>
                <button
                  onClick={() => setViewMode("sistem")}
                  className={`flex-1 flex items-center justify-center gap-1 text-[10px] font-semibold py-1 rounded-md transition-colors ${viewMode === "sistem" ? 'bg-card text-blue-600 shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                  data-testid="audit-tab-sistem"
                  title="Log sistem tanpa kegiatan — master pegawai & kartu pegawai"
                >
                  <Server className="w-3 h-3" />Sistem
                </button>
              </div>
            )}
          </div>

          {/* Asset filter indicator */}
          {selectedAssetId && (
            <div className="px-3 py-1.5 bg-blue-50 dark:bg-blue-900/30 border-b border-blue-100 dark:border-blue-800 flex items-center justify-between flex-shrink-0" data-testid="audit-asset-filter">
              <div className="flex items-center gap-1.5 min-w-0">
                <Package className="w-3 h-3 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                <span className="text-[10px] text-blue-700 dark:text-blue-300 truncate font-medium">{selectedAssetCode}</span>
              </div>
              <button onClick={onClearAssetFilter} className="text-[10px] text-blue-500 hover:text-blue-700 font-medium flex-shrink-0 ml-2" data-testid="audit-clear-filter">
                Lihat semua
              </button>
            </div>
          )}

          {/* Content */}
          <div className="flex-1 overflow-y-auto" data-testid="audit-log-list">
            {viewMode === "integritas" && !selectedAssetId ? (
              <IntegritasSummary
                data={integritas} loading={integritasLoading} error={integritasError}
                onRefresh={fetchIntegritas} detail={detailIntegritas}
                onMuatDetail={muatDetailIntegritas} onEkspor={eksporIntegritas} />
            ) : loading && logs.length === 0 ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : loadError && logs.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground px-4" data-testid="audit-load-error">
                <History className="w-10 h-10 mx-auto mb-3 opacity-20" />
                <p className="text-xs font-medium">Gagal memuat riwayat</p>
                <p className="text-[10px] mt-1">Periksa koneksi Anda, lalu coba lagi</p>
                <Button variant="outline" size="sm" className="mt-3 h-7 text-xs"
                  onClick={() => fetchLogs(page)} data-testid="audit-retry-btn">
                  Coba lagi
                </Button>
              </div>
            ) : logs.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground px-4">
                <History className="w-10 h-10 mx-auto mb-3 opacity-20" />
                <p className="text-xs font-medium">{sistemMode ? "Belum ada log sistem" : "Belum ada riwayat"}</p>
                <p className="text-[10px] mt-1">
                  {sistemMode
                    ? "Kejadian master pegawai & kartu pegawai akan tercatat di sini"
                    : "Perubahan pada aset akan tercatat di sini"}
                </p>
              </div>
            ) : viewMode === "user" && !selectedAssetId ? (
              <div className="p-3">
                <UserSummary logs={logs} onSelectUser={setFilterUser} selectedUser={filterUser} />
                <div className="mt-3 pt-3 border-t border-border">
                  <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider px-1 mb-2">
                    {filterUser ? `Aktivitas ${filterUser}` : 'Aktivitas Terbaru'}
                  </div>
                  {(filterUser ? logs.filter(l => l.username === filterUser) : logs.slice(0, 10)).map(log => (
                    <TimelineEntry key={log.id} log={log} showAssetInfo />
                  ))}
                  {filterUser && logs.filter(l => l.username === filterUser).length === 0 && (
                    <p className="text-[10px] text-muted-foreground text-center py-4">Tidak ada aktivitas dari user ini</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-3">
                {sistemMode && (
                  <p className="text-[9px] text-muted-foreground px-1 pb-2 leading-relaxed" data-testid="audit-sistem-keterangan">
                    Log sistem (tanpa kegiatan): master pegawai &amp; kartu pegawai UID.
                    Admin satker hanya melihat log satuan kerjanya.
                  </p>
                )}
                {logs.map(log => (
                  <TimelineEntry key={log.id} log={log} showAssetInfo={!selectedAssetId} />
                ))}
              </div>
            )}
          </div>

          {/* Pagination */}
          {viewMode !== "integritas" && totalPages > 1 && (
            <div className="px-3 py-2 border-t border-border flex items-center justify-between flex-shrink-0 bg-muted">
              <Button
                variant="outline" size="sm" className="h-6 text-[10px] px-2"
                disabled={page <= 1} onClick={() => fetchLogs(page - 1)}
              >
                <ChevronLeft className="w-3 h-3" />
              </Button>
              <span className="text-[10px] text-muted-foreground font-medium">{page} / {totalPages}</span>
              <Button
                variant="outline" size="sm" className="h-6 text-[10px] px-2"
                disabled={page >= totalPages} onClick={() => fetchLogs(page + 1)}
              >
                <ChevronRight className="w-3 h-3" />
              </Button>
            </div>
          )}
        </>
      )}
      </div>
    </>
  );
});

AuditLogPanel.displayName = "AuditLogPanel";

export default AuditLogPanel;
