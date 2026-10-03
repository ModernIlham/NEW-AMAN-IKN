import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { Box, ClipboardCheck, ExternalLink, FileCheck2, MapPin, RefreshCw, Search, ShieldCheck, UserPlus, Users } from "lucide-react";
import { kunciPortal, LABEL_LAPORAN, LABEL_STATUS, STATUS_PENUGASAN } from "@/lib/portalPemegang";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;
const ROOT = `${API}/portal-pemegang/admin`;
const input = "min-h-[44px] w-full min-w-0 rounded-lg border border-input bg-background px-3 py-2 text-sm";
const button = "inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium disabled:opacity-50";
const primary = `${button} border-primary bg-primary text-primary-foreground`;
const when = value => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString("id-ID") : "—";
const badge = "inline-flex rounded-full border bg-muted/50 px-2.5 py-1 text-xs font-medium";
const notice = "text-amber-800 dark:text-amber-300";
const readError = (e, fallback) => typeof e?.response?.data?.detail === "string" ? e.response.data.detail : fallback;

/** Kantor daring: memantau amanah dan laporan, bukan memindahkan pemegang/master. */
export default function PortalPemegangPanel({ user }) {
  const admin = user?.role === "admin";
  const writer = ["admin", "operator"].includes(user?.role);
  const [pegawai, setPegawai] = useState([]);
  const [pilih, setPilih] = useState("");
  const [cariPegawai, setCariPegawai] = useState("");
  const [akses, setAkses] = useState(null);
  const [penugasan, setPenugasan] = useState([]);
  const [laporan, setLaporan] = useState([]);
  const [search, setSearch] = useState("");
  const [hasil, setHasil] = useState([]);
  const [asset, setAsset] = useState(null);
  const [dasar, setDasar] = useState("");
  const [catatan, setCatatan] = useState("");
  const [emailBenar, setEmailBenar] = useState(false);
  const [aksesCatatan, setAksesCatatan] = useState("");
  const [review, setReview] = useState(null);
  const [cabut, setCabut] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [pesan, setPesan] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [monitoring, setMonitoring] = useState(null);
  const [monitoringLoading, setMonitoringLoading] = useState(false);
  const [monitoringError, setMonitoringError] = useState("");
  const [laporanError, setLaporanError] = useState("");
  const [penugasanError, setPenugasanError] = useState("");
  const [cariLaporan, setCariLaporan] = useState("");
  const [queryLaporan, setQueryLaporan] = useState("");
  const [cariAsetPantau, setCariAsetPantau] = useState("");
  const [statusAsetPantau, setStatusAsetPantau] = useState("");
  const loadSeq = useRef(0);
  const searchSeq = useRef(0);
  const previewSeq = useRef(0);
  const writeKeys = useRef(new Map());
  const selected = pegawai.find(p => p.id === pilih);

  const muat = useCallback(async () => {
    const seq = ++loadSeq.current;
    setLoading(true); setError(""); setLaporanError(""); setPenugasanError("");
    setMonitoring(null); setMonitoringLoading(true); setMonitoringError("");
    // Ringkasan bukan angka dari halaman laporan. Kegagalannya tidak menahan baca lain.
    axios.get(`${ROOT}/monitoring`, { params: pilih ? { pegawai_id: pilih } : {} }).then(r => {
      if (seq === loadSeq.current) setMonitoring(r.data);
    }).catch(() => {
      if (seq === loadSeq.current) setMonitoringError("Ringkasan belum tersedia. Daftar dan pemeriksaan laporan tetap dapat digunakan; coba muat ulang.");
    }).finally(() => { if (seq === loadSeq.current) setMonitoringLoading(false); });
    await Promise.allSettled([
      axios.get(`${ROOT}/laporan`, { params: { page, page_size: 30, status: filterStatus, ...(pilih ? { pegawai_id: pilih } : {}), ...(queryLaporan ? { search: queryLaporan } : {}) } }).then(r => {
        if (seq === loadSeq.current) { setLaporan(r.data.items || []); setTotal(r.data.total || 0); }
      }).catch(e => {
        if (seq === loadSeq.current) { setLaporan([]); setTotal(0); setLaporanError(readError(e, "Laporan gagal dimuat. Coba muat ulang.")); }
      }),
      (pilih ? axios.get(`${ROOT}/penugasan`, { params: { pegawai_id: pilih } }) : Promise.resolve({ data: { items: [] } })).then(r => {
        if (seq === loadSeq.current) setPenugasan(r.data.items || []);
      }).catch(e => {
        if (seq === loadSeq.current) { setPenugasan([]); setPenugasanError(readError(e, "Amanah pegawai gagal dimuat. Coba muat ulang.")); }
      }),
      (pilih && admin ? axios.get(`${ROOT}/akses`, { params: { pegawai_id: pilih } }) : Promise.resolve({ data: null })).then(r => {
        if (seq === loadSeq.current) setAkses(r.data);
      }).catch(e => {
        if (seq === loadSeq.current) { setAkses(null); setError(readError(e, "Informasi akses gagal dimuat. Monitoring tetap dapat digunakan.")); }
      }),
    ]);
    if (seq === loadSeq.current) setLoading(false);
  }, [pilih, admin, page, filterStatus, queryLaporan]);
  useEffect(() => {
    let current = true;
    axios.get(`${API}/pegawai`).then(r => { if (current) setPegawai(r.data.items || []); }).catch(() => { if (current) setError("Daftar pegawai gagal dimuat. Buka ulang panel atau periksa koneksi."); });
    return () => { current = false; };
  }, []);
  useEffect(() => {
    setAkses(null); setPenugasan([]); setLaporan([]); setTotal(0); setAsset(null); setHasil([]); setEmailBenar(false); setAksesCatatan(""); setReview(null); setCabut(null); setPreview(null);
    previewSeq.current += 1;
    muat();
    return () => { loadSeq.current += 1; previewSeq.current += 1; };
  }, [muat]);
  useEffect(() => {
    if (cariLaporan.trim() === queryLaporan) return undefined;
    const timer = setTimeout(() => { setQueryLaporan(cariLaporan.trim()); setPage(1); }, 300);
    return () => clearTimeout(timer);
  }, [cariLaporan, queryLaporan]);
  useEffect(() => {
    const seq = ++searchSeq.current;
    if (!pilih || search.trim().length < 2) { setHasil([]); return undefined; }
    const timer = setTimeout(() => {
      axios.get(`${API}/assets`, { params: { search: search.trim(), page_size: 20 } }).then(r => {
        if (seq === searchSeq.current) setHasil(r.data.items || []);
      }).catch(() => { if (seq === searchSeq.current) { setHasil([]); setError("Pencarian aset gagal. Coba kembali."); } });
    }, 300);
    return () => { clearTimeout(timer); searchSeq.current += 1; };
  }, [search, pilih]);
  useEffect(() => () => { if (preview?.url) URL.revokeObjectURL(preview.url); }, [preview]);

  const kerja = async fn => {
    if (busy) return;
    setBusy(true); setError(""); setPesan("");
    try { await fn(); } catch (e) { setError(typeof e.response?.data?.detail === "string" ? e.response.data.detail : e.message || "Permintaan gagal. Muat ulang dan periksa data sebelum mencoba kembali."); }
    finally { setBusy(false); }
  };
  const post = async (path, body, version) => {
    const signature = JSON.stringify([path, body, version]);
    if (!writeKeys.current.has(signature)) writeKeys.current.set(signature, kunciPortal());
    const result = await axios.post(`${ROOT}${path}`, body, {
      headers: { "If-Match": String(version), "Idempotency-Key": writeKeys.current.get(signature) }, timeout: 30000,
    });
    writeKeys.current.delete(signature);
    return result;
  };
  const ubahAkses = async aktif => {
    if (aksesCatatan.trim().length < 5) throw new Error("Tuliskan alasan/pemeriksaan minimal 5 karakter.");
    if (aktif && !emailBenar) throw new Error("Konfirmasikan bahwa email benar milik pegawai ini, bukan alamat bersama.");
    const version = akses?.version ?? 0;
    await post("/akses", { pegawai_id: pilih, aktif, version, email: akses?.email || "",
      konfirmasi_email: emailBenar, catatan: aksesCatatan.trim() }, version);
    setAksesCatatan(""); setEmailBenar(false); await muat(); setPesan(aktif ? "Akses email portal diaktifkan setelah pemeriksaan. Pegawai dapat meminta tautan masuk sendiri." : "Akses portal dicabut; sesi/token terkait tidak lagi dapat dipakai. Tanggung jawab barang tidak otomatis berakhir.");
  };
  const tambah = async () => {
    if (!asset || !pilih) throw new Error("Pilih pegawai dan barang yang sesuai terlebih dahulu.");
    if (dasar.trim().length < 10) throw new Error("Tuliskan dasar penugasan yang dapat ditelusuri (minimal 10 karakter).");
    await post("/penugasan", { pegawai_id: pilih, asset_id: asset.id, dasar_penugasan: dasar.trim(), catatan: catatan.trim() }, 0);
    setAsset(null); setSearch(""); setDasar(""); setCatatan(""); await muat(); setPesan("Penugasan portal dicatat dan menunggu konfirmasi pemegang. Pemegang resmi/data induk belum diubah.");
  };
  const lihat = async (r, i) => {
    const seq = ++previewSeq.current;
    const scope = loadSeq.current;
    const response = await axios.get(`${ROOT}/laporan/${encodeURIComponent(r.id)}/bukti/${i}`, { responseType: "blob" });
    if (seq !== previewSeq.current || scope !== loadSeq.current) return;
    setPreview({ url: URL.createObjectURL(response.data), nama: r.bukti[i].nama });
  };
  const pegawaiTampak = pegawai.filter(p => `${p.nama} ${p.email} ${p.kode_satker}`.toLowerCase().includes(cariPegawai.toLowerCase()));
  const laporanTampak = laporan;
  const penugasanTampak = penugasan.filter(a => (!statusAsetPantau || a.status === statusAsetPantau)
    && `${a.asset_name || ""} ${a.asset_code || ""} ${a.NUP || ""} ${a.location || ""} ${a.sumber_bast?.nomor || ""}`.toLowerCase().includes(cariAsetPantau.trim().toLowerCase()));
  const totalPages = Math.max(1, Math.ceil(total / 30));

  return <section className="min-w-0 space-y-5 text-foreground" data-testid="penggunaan-portal-panel">
    <header className="rounded-2xl border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><p className="mb-1 text-xs font-semibold uppercase tracking-wider text-primary">Portal Pemegang BMN</p><h3 className="flex items-center gap-2 text-xl font-semibold"><ShieldCheck size={22} className="shrink-0" />Monitoring amanah aset</h3><p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">Pantau barang yang dijaga setiap pemegang, baca pembaruan keadaannya, dan berikan arahan yang jelas dalam satu tempat.</p></div><div className="flex flex-wrap gap-2"><a href="/bmn-saya" target="_blank" rel="noopener noreferrer" className={button} data-testid="portal-buka-publik"><ExternalLink size={16} />Buka BMN Saya</a><button type="button" className={button} disabled={busy || loading} data-testid="portal-admin-muat" onClick={() => kerja(muat)}><RefreshCw size={16} className={loading ? "animate-spin" : ""} />Muat ulang</button></div></div>
      <p className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-3 text-sm leading-relaxed">BAST baru yang sah dan lengkap otomatis menjadi amanah di BMN Saya, tanpa penerimaan ulang. Email unik yang memenuhi syarat mendapat aktivasi awal otomatis. Penugasan lama dan masalah akses tetap ditangani sebagai pengecualian.</p>
    </header>
    {error && <p role="alert" className="rounded-lg bg-red-500/10 p-3 text-sm">{error}</p>}{pesan && <p role="status" className="rounded-lg bg-emerald-500/10 p-3 text-sm">{pesan}</p>}
    <div className="grid gap-3 rounded-xl border bg-card p-4 sm:grid-cols-2"><label className="block min-w-0 text-sm font-medium">Cari pemegang<input className={`${input} mt-1 font-normal`} data-testid="portal-admin-cari-pegawai" value={cariPegawai} onChange={e => setCariPegawai(e.target.value)} placeholder="Nama, email, atau satker" /></label><label className="block min-w-0 text-sm font-medium">Lingkup monitoring<select className={`${input} mt-1 font-normal`} data-testid="portal-admin-pegawai" disabled={busy} value={pilih} onChange={e => { setPilih(e.target.value); setPage(1); setCariAsetPantau(""); setStatusAsetPantau(""); }}><option value="">Semua pemegang di satker aktif</option>{selected && !pegawaiTampak.some(p => p.id === pilih) && <option value={selected.id}>{selected.nama}</option>}{pegawaiTampak.map(p => <option key={p.id} value={p.id}>{p.nama} · {p.kode_satker || "Satker belum diisi"}</option>)}</select></label></div>
    <section aria-label="Ringkasan monitoring" className="space-y-2">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {[
          ["pemegang", "Pemegang tercatat", monitoring?.pemegang, Users, "Dalam catatan penugasan"],
          ["diterima", "Penugasan diterima", monitoring?.penugasan?.diterima, Box, "Status yang tercatat"],
          ["menunggu", "Menunggu tinjauan", monitoring?.laporan?.menunggu_tinjauan, ClipboardCheck, "Laporan perlu diperiksa petugas"],
          ["perbaikan", "Perlu perbaikan", monitoring?.laporan?.perlu_perbaikan, FileCheck2, "Laporan dikembalikan untuk dilengkapi"],
        ].map(([id, label, count, Icon, description]) => <div key={id} className="min-w-0 rounded-xl border bg-card p-3 sm:p-4" data-testid={`portal-monitor-${id}`}><div className="flex items-center gap-2 text-sm text-muted-foreground"><Icon size={17} className="shrink-0" /><span>{label}</span></div><p className="my-2 text-2xl font-semibold tabular-nums">{monitoringLoading || count == null ? "—" : Number(count).toLocaleString("id-ID")}</p><p className="text-xs leading-relaxed text-muted-foreground">{description}</p></div>)}
      </div>
      {monitoringError && <p role="status" className={`rounded-lg bg-amber-500/10 p-3 text-sm ${notice}`}>{monitoringError}</p>}
      <p className="text-xs leading-relaxed text-muted-foreground">Ringkasan mencakup seluruh catatan dalam lingkup {selected?.nama || "satker aktif"}, bukan hanya halaman atau saringan laporan. Status penugasan tercatat bukan jaminan akses masih berlaku; kelayakannya diperiksa pada setiap barang.</p>
    </section>
    {loading && <p role="status" className="text-sm text-muted-foreground">Memuat amanah dan laporan…</p>}
    {pilih && <>
      {admin && akses && <details className="rounded-xl border bg-card p-4"><summary className="min-h-[44px] cursor-pointer py-2 text-sm font-medium" data-testid="portal-admin-akses-toggle">Pengaturan akses email · {akses.akses?.aktif ? "Aktif" : "Perlu pemeriksaan"}</summary><div className="mt-3 space-y-3"><h4 className="font-semibold">Pengecualian akses email</h4><p className="break-words text-sm">{akses.nama || selected?.nama} · {akses.email || "Email belum diisi di Master Pegawai"}</p><p className="text-sm">Akses: <strong>{akses.akses?.aktif ? "Aktif" : "Tidak aktif"}</strong>{akses.akses?.verified_at ? ` · Diperiksa ${when(akses.akses.verified_at)}` : ""}</p>
        <p className="text-sm text-muted-foreground">Tidak diperlukan untuk setiap BAST. Gunakan setelah pemeriksaan bila email/identitas berubah, ada kendala akses, atau akses pernah dicabut. Aktivasi email saja tidak memberi hak atas barang yang BAST atau penugasannya tidak lagi berlaku.</p>
        <p className="text-xs text-muted-foreground">Periksa bahwa alamat hanya dimiliki pegawai bersangkutan. Email kosong/duplikat, satker tidak sesuai, atau pegawai tidak memenuhi syarat akan ditolak server. Perubahan email/identitas membutuhkan pemeriksaan ulang.</p>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={emailBenar} data-testid="portal-admin-email-benar" disabled={busy} onChange={e => setEmailBenar(e.target.checked)} /><span>Saya telah memeriksa bahwa email tersebut benar milik pegawai ini dan bukan alamat bersama.</span></label>
        <label className="block text-sm">Alasan / hasil pemeriksaan<textarea className={`${input} mt-1`} rows={2} maxLength={2000} value={aksesCatatan} data-testid="portal-admin-akses-catatan" onChange={e => setAksesCatatan(e.target.value)} /></label><div className="flex flex-wrap gap-2"><button type="button" className={primary} disabled={busy || loading || !emailBenar || !akses.email} data-testid="portal-admin-aktifkan" onClick={() => kerja(() => ubahAkses(true))}>Setujui akses email</button><button type="button" className={button} disabled={busy || loading || !akses.akses?.aktif} data-testid="portal-admin-nonaktifkan" onClick={() => kerja(() => ubahAkses(false))}>Cabut akses portal</button></div>
      </div></details>}
      {!admin && <p className="text-sm text-muted-foreground">Persetujuan email serta pemetaan/pencabutan penugasan portal dilakukan admin satker. Operator dapat memeriksa laporan sesuai kewenangannya.</p>}
      <section className="space-y-3 rounded-xl border bg-card p-4"><div><h4 className="font-semibold">Aset dan riwayat amanah · {selected?.nama}</h4><p className="mt-1 text-sm text-muted-foreground">Bandingkan catatan barang dengan pembaruan terakhir dari pemegang. Laporan bukan perubahan otomatis data induk.</p></div>
        <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Cari dalam amanah pegawai<input className={`${input} mt-1`} data-testid="portal-admin-cari-amanah" value={cariAsetPantau} maxLength={120} onChange={e => setCariAsetPantau(e.target.value)} placeholder="Barang, kode, NUP, lokasi, atau BAST" /></label><label className="text-sm">Status penugasan<select className={`${input} mt-1`} data-testid="portal-admin-status-amanah" value={statusAsetPantau} onChange={e => setStatusAsetPantau(e.target.value)}><option value="">Semua catatan termasuk riwayat</option>{Object.entries(STATUS_PENUGASAN).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label></div>
        {penugasanError && <p role="alert" className="rounded-lg bg-red-500/10 p-3 text-sm">{penugasanError}</p>}
        {!penugasanTampak.length && !loading && !penugasanError && <p className="rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">{penugasan.length ? "Tidak ada amanah sesuai pencarian/status. Ubah saringan untuk melihat catatan lain." : "Belum ada amanah tercatat untuk pegawai ini. Setelah BAST baru sah dan lengkap, barang akan tampil otomatis."}</p>}
        <div className="grid gap-3 xl:grid-cols-2">{penugasanTampak.map(a => <article key={a.id} className="min-w-0 space-y-3 rounded-xl border p-4" data-testid={`portal-admin-amanah-${a.id}`}>
          <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><h5 className="break-words font-semibold">{a.asset_name || "Aset tanpa nama"}</h5><p className="mt-1 break-words text-xs text-muted-foreground">{a.asset_code || "Kode belum diisi"} · NUP {a.NUP || "—"}</p></div><span className={badge}>{STATUS_PENUGASAN[a.status] || a.status}</span></div>
          <dl className="grid gap-3 rounded-lg bg-muted/40 p-3 text-sm sm:grid-cols-2"><div><dt className="text-xs text-muted-foreground">Kondisi {a.akses_valid === false ? "tercatat saat penugasan" : "data induk"}</dt><dd className="mt-1 font-medium">{a.condition || "Belum diisi"}</dd></div><div><dt className="flex items-center gap-1 text-xs text-muted-foreground"><MapPin size={13} />Lokasi {a.akses_valid === false ? "tercatat saat penugasan" : "data induk"}</dt><dd className="mt-1 break-words font-medium">{a.location || "Belum diisi"}</dd></div></dl>
          {a.sumber_bast ? <div className="text-sm"><p className="font-medium">BAST {a.sumber_bast.nomor || "tertaut"}</p><p className="mt-1 text-xs text-muted-foreground">Tanggal {a.sumber_bast.tanggal || "—"}{a.sumber_bast.jangka_sampai ? ` · Batas penggunaan ${a.sumber_bast.jangka_sampai}` : ""}{a.penerimaan_otomatis ? " · Diterima melalui BAST, tanpa konfirmasi ulang" : ""}</p></div> : <p className="break-words text-sm"><span className={badge}>Penugasan lama / manual</span><br />Dasar: {a.dasar_penugasan || "Periksa dokumen sumber"}</p>}
          <div className="border-t pt-3"><p className="text-xs font-semibold text-muted-foreground">Pembaruan terakhir pemegang</p>{a.laporan_terakhir ? <div className="mt-1 space-y-1 text-sm"><p>{LABEL_STATUS[a.laporan_terakhir.status] || a.laporan_terakhir.status} · {when(a.laporan_terakhir.created_at)}</p><p>{a.laporan_terakhir.kondisi || "Kondisi tidak diisi"}{a.laporan_terakhir.status_operasional ? ` · ${a.laporan_terakhir.status_operasional.replaceAll("_", " ")}` : ""}</p><p className="break-words">Lokasi dilaporkan: {a.laporan_terakhir.lokasi_laporan || "Tidak diisi"}</p><p className="text-xs text-muted-foreground">Informasi dari laporan; periksa bukti dan status tinjauannya.</p></div> : <p className="mt-1 text-sm text-muted-foreground">Belum ada laporan untuk penugasan ini.</p>}</div>
          {a.konfirmasi && !a.penerimaan_otomatis && <p className="text-sm">Pernyataan: {a.konfirmasi.keputusan === "terima" ? "Menerima" : "Menyanggah"} · {a.konfirmasi.catatan || "Tanpa catatan"}</p>}
          {a.akses_valid === false && <p className={`rounded-lg bg-amber-500/10 p-3 text-sm ${notice}`}>Akses tidak berlaku: {a.alasan_akses || "Akses tidak lagi memenuhi syarat."} Riwayat tetap disimpan.</p>}
          {admin && a.status !== "dicabut" && <details className="border-t pt-2"><summary className="min-h-[44px] cursor-pointer py-3 text-xs text-muted-foreground" data-testid={`portal-admin-amanah-akses-${a.id}`}>Tindakan akses barang</summary><button type="button" className={button} disabled={busy} data-testid={`portal-admin-cabut-${a.id}`} onClick={() => setCabut({ item: a, catatan: "" })}>Cabut penugasan portal</button></details>}
        </article>)}</div>
        {!!penugasan.length && <p className="text-xs text-muted-foreground">Menampilkan {penugasanTampak.length} dari {penugasan.length} catatan penugasan pegawai ini, termasuk riwayat yang dicabut.</p>}
        {admin && <details className="rounded-lg border p-3"><summary className="min-h-[44px] cursor-pointer py-2 text-sm font-medium" data-testid="portal-admin-tambah-toggle">Pengecualian / penugasan lama yang belum bersumber dari BAST otomatis</summary><div className="mt-3 space-y-3"><p className="text-xs text-muted-foreground">Alur normal cukup menyelesaikan BAST. Gunakan pencatatan manual ini hanya untuk dasar penugasan lama/di luar alur otomatis yang sudah diperiksa; tidak memindahkan pemegang resmi dan masih memerlukan konfirmasi penerimaan portal.</p><label className="block text-sm">Cari aset<input className={`${input} mt-1`} data-testid="portal-admin-cari-aset" value={search} onChange={e => { setSearch(e.target.value); setAsset(null); }} placeholder="Minimal 2 karakter nama/kode" /></label><p className="text-xs text-muted-foreground">Hasil mengikuti lingkup satker aktif. Pilih baris kegiatan yang menjadi acuan; identitas fisik dan kecocokan pemegang akan diperiksa server.</p>
          <div className="max-h-64 space-y-2 overflow-y-auto">{hasil.map(a => <button type="button" key={a.id} className={`${button} w-full justify-start text-left ${asset?.id === a.id ? "border-primary bg-primary/5" : ""}`} data-testid={`portal-admin-aset-${a.id}`} onClick={() => setAsset(a)}><span><strong>{a.asset_name}</strong><br /><span className="text-xs">{a.asset_code} · NUP {a.NUP} · {a.location || "Lokasi belum diisi"} · {a.user || "Pemegang belum diisi"}</span></span></button>)}</div>
          {asset && <p className="rounded-lg bg-primary/5 p-2 text-sm">Terpilih: {asset.asset_name} · {asset.asset_code} / {asset.NUP}</p>}
          <label className="block text-sm">Dasar penugasan yang dapat ditelusuri<input className={`${input} mt-1`} data-testid="portal-admin-dasar" maxLength={1000} value={dasar} onChange={e => setDasar(e.target.value)} placeholder="Nomor/tanggal BAST atau surat penugasan sah" /></label><label className="block text-sm">Catatan<textarea className={`${input} mt-1`} data-testid="portal-admin-penugasan-catatan" maxLength={2000} rows={2} value={catatan} onChange={e => setCatatan(e.target.value)} /></label><button type="button" className={primary} data-testid="portal-admin-tambah" disabled={busy || loading || !asset} onClick={() => kerja(tambah)}><UserPlus size={16} />Catat penugasan portal</button>
        </div></details>}
      </section>
    </>}
    {cabut && <section className="space-y-3 rounded-xl border border-red-500/30 p-4"><h4 className="font-semibold">Cabut akses barang: {cabut.item.asset_name}</h4><p className="text-sm">Ini menghentikan akses portal, tidak membuktikan pengembalian barang atau mengakhiri tanggung jawab administratif. Riwayat tetap tersimpan.</p><label className="block text-sm">Alasan<textarea className={`${input} mt-1`} rows={3} maxLength={2000} data-testid="portal-admin-cabut-alasan" value={cabut.catatan} onChange={e => setCabut(v => ({ ...v, catatan: e.target.value }))} /></label><div className="flex flex-wrap gap-2"><button type="button" className={primary} data-testid="portal-admin-cabut-simpan" disabled={busy} onClick={() => kerja(async () => {
      if (cabut.catatan.trim().length < 5) throw new Error("Alasan pencabutan minimal 5 karakter.");
      await post(`/penugasan/${encodeURIComponent(cabut.item.id)}/cabut`, { catatan: cabut.catatan.trim(), version: cabut.item.version }, cabut.item.version);
      setCabut(null); await muat(); setPesan("Akses barang dicabut; riwayat tetap tercatat.");
    })}>Simpan pencabutan</button><button type="button" className={button} disabled={busy} data-testid="portal-admin-cabut-batal" onClick={() => setCabut(null)}>Batal</button></div></section>}
    <section className="space-y-3 rounded-xl border bg-card p-4"><div><h4 className="font-semibold">Pemeriksaan laporan pemegang</h4><p className="mt-1 text-sm text-muted-foreground">Baca bukti, periksa kesesuaian laporan, lalu berikan hasil pemeriksaan dan arahan tindak lanjut.</p></div>
      <div className="grid gap-3 sm:grid-cols-2"><label className="min-w-0 text-sm">Cari laporan<input className={`${input} mt-1`} data-testid="portal-admin-cari-laporan" maxLength={120} value={cariLaporan} disabled={busy} onChange={e => setCariLaporan(e.target.value)} placeholder="Barang, kode, NUP, pemegang, atau lokasi" /></label><label className="min-w-0 text-sm">Status laporan<select className={`${input} mt-1`} data-testid="portal-admin-status" value={filterStatus} disabled={busy} onChange={e => { setFilterStatus(e.target.value); setPage(1); }}><option value="">Semua status</option>{Object.entries(LABEL_STATUS).filter(([id]) => id !== "menunggu_verifikasi").map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label></div>
      <p className="rounded-lg bg-muted/50 p-3 text-xs leading-relaxed text-muted-foreground">Verifikasi menyatakan hasil pemeriksaan laporan, bukan perubahan kondisi induk, lokasi, pemegang, nilai, penyusutan, jurnal, atau penghapusan. Tindakan resmi tetap melalui modul terkait dan pejabat berwenang.</p>
      {laporanError && <p role="alert" className="rounded-lg bg-red-500/10 p-3 text-sm">{laporanError}</p>}
      {!laporanTampak.length && !loading && !laporanError && <div className="rounded-lg border border-dashed p-6 text-center"><ClipboardCheck size={26} className="mx-auto mb-2 text-muted-foreground" /><p className="text-sm font-medium">Tidak ada laporan sesuai pilihan.</p><p className="mt-1 text-xs text-muted-foreground">Ubah pencarian atau status untuk menelusuri riwayat lain. Laporan baru akan tampil setelah dikirim pemegang.</p></div>}
      {laporanTampak.map(r => <article key={r.id} className="min-w-0 space-y-3 rounded-xl border p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><h5 className="break-words font-semibold">{r.asset_name}</h5><p className="break-words text-sm text-muted-foreground">{r.pegawai_nama} · {r.asset_code} / NUP {r.NUP}</p></div><span className={badge}>{LABEL_STATUS[r.status] || r.status}</span></div><p className="text-xs text-muted-foreground">{LABEL_LAPORAN[r.jenis]} · Diterima server {when(r.created_at)}{r.diambil_pada ? ` · Waktu bukti menurut pelapor ${when(r.diambil_pada)}` : ""}</p><p className="text-sm">Kondisi dilaporkan: {r.kondisi} · {r.status_operasional?.replaceAll("_", " ")}</p><p className="break-words text-sm">Lokasi dilaporkan: {r.lokasi_laporan || "Tidak diisi"}</p><p className="whitespace-pre-wrap break-words text-sm">{r.catatan}</p>
        {r.jenis === "kehilangan" && <p className="rounded-lg bg-amber-500/10 p-3 text-sm">Perlu penanganan pengamanan segera. Kehilangan belum menetapkan kesalahan, TGR, atau penghapusan; ikuti prosedur dan kewenangan instansi.</p>}
        {!!r.perlu_tindak_lanjut?.length && <p className={`text-sm ${notice}`}>Perlu tindak lanjut: {r.perlu_tindak_lanjut.join(", ")}. Periksa melalui modul terkait; arahan ini belum merupakan pencatatan kasus atau transaksi.</p>}
        {!!r.bukti?.length && <div className="flex flex-wrap gap-2">{r.bukti.map((p, i) => <button type="button" key={i} className={button} disabled={busy} data-testid={`portal-admin-bukti-${r.id}-${i}`} onClick={() => kerja(() => lihat(r, i))}><Search size={15} />Periksa foto {i + 1}</button>)}</div>}
        {r.tinjauan?.map((t, i) => <p key={i} className="rounded-lg bg-muted p-3 text-sm"><strong>{LABEL_STATUS[t.keputusan] || t.keputusan}</strong> · {when(t.tanggal)}<br />{t.catatan}</p>)}
        {writer && ["diajukan", "menunggu_verifikasi"].includes(r.status) && <button type="button" className={primary} data-testid={`portal-admin-tinjau-${r.id}`} disabled={busy} onClick={() => setReview({ item: r, keputusan: "perlu_perbaikan", catatan: "" })}><FileCheck2 size={16} />Periksa & beri keputusan</button>}
      </article>)}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3"><p className="text-sm text-muted-foreground" data-testid="portal-admin-total-laporan">{laporanError ? "Jumlah laporan belum tersedia" : `${total} laporan sesuai saringan · Halaman ${page} dari ${totalPages}`}</p><div className="flex flex-wrap gap-2"><button type="button" className={button} data-testid="portal-admin-sebelumnya" disabled={busy || loading || page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>Sebelumnya</button><button type="button" className={button} data-testid="portal-admin-berikutnya" disabled={busy || loading || page >= totalPages} onClick={() => setPage(p => p + 1)}>Berikutnya</button></div></div>
    </section>
    {review && <section className="space-y-3 rounded-xl border border-primary/40 p-4" aria-label="Pemeriksaan laporan"><h4 className="font-semibold">Pemeriksaan · {review.item.asset_name}</h4><p className="text-sm">Keputusan memvalidasi laporan dan kelengkapan bukti saja. Tidak mengesahkan transaksi akuntansi atau mengganti data induk. Pelapor tidak boleh memverifikasi laporannya sendiri.</p><label className="block text-sm">Keputusan<select className={`${input} mt-1`} data-testid="portal-admin-keputusan" value={review.keputusan} onChange={e => setReview(v => ({ ...v, keputusan: e.target.value }))}><option value="perlu_perbaikan">Minta klarifikasi / perbaikan</option><option value="terverifikasi">Laporan sesuai dan terverifikasi</option><option value="ditolak">Tolak dengan alasan</option></select></label><label className="block text-sm">Hasil pemeriksaan dan arahan tindak lanjut<textarea className={`${input} mt-1`} data-testid="portal-admin-tinjauan-catatan" maxLength={4000} rows={4} value={review.catatan} onChange={e => setReview(v => ({ ...v, catatan: e.target.value }))} /></label><div className="flex flex-wrap gap-2"><button type="button" className={primary} disabled={busy} data-testid="portal-admin-tinjau-simpan" onClick={() => kerja(async () => {
      if (review.catatan.trim().length < 5) throw new Error("Tuliskan hasil pemeriksaan dan alasannya (minimal 5 karakter).");
      await post(`/laporan/${encodeURIComponent(review.item.id)}/tinjau`, { version: review.item.version, keputusan: review.keputusan, catatan: review.catatan.trim() }, review.item.version);
      setReview(null); await muat(); setPesan("Hasil pemeriksaan tersimpan dalam riwayat. Lanjutkan tindakan administratif melalui modul terkait sesuai kewenangan.");
    })}>Catat hasil pemeriksaan</button><button type="button" className={button} disabled={busy} data-testid="portal-admin-tinjau-batal" onClick={() => setReview(null)}>Batal</button></div></section>}
    {preview && <section role="dialog" aria-modal="true" aria-label="Bukti laporan pemegang" className="fixed inset-0 z-[150] flex flex-col bg-black/90 p-4"><div className="mb-3 flex items-center justify-between gap-3 text-white"><p className="min-w-0 truncate text-sm">{preview.nama}</p><button type="button" autoFocus className={button} data-testid="portal-admin-tutup-bukti" onClick={() => setPreview(null)}>Tutup</button></div><img src={preview.url} alt={preview.nama} className="min-h-0 flex-1 object-contain" /></section>}
  </section>;
}
