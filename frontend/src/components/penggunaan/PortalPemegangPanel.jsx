import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { ExternalLink, FileCheck2, RefreshCw, Search, ShieldCheck, UserPlus } from "lucide-react";
import { kunciPortal, LABEL_LAPORAN, LABEL_STATUS, STATUS_PENUGASAN } from "@/lib/portalPemegang";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;
const ROOT = `${API}/portal-pemegang/admin`;
const input = "w-full min-w-0 rounded-lg border border-input bg-background px-3 py-2 text-sm";
const button = "inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium disabled:opacity-50";
const primary = `${button} border-primary bg-primary text-primary-foreground`;
const when = value => value ? new Date(value).toLocaleString("id-ID") : "—";

/** Kantor daring: memetakan akses, bukan memindahkan pemegang/master. */
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
  const loadSeq = useRef(0);
  const searchSeq = useRef(0);
  const writeKeys = useRef(new Map());
  const selected = pegawai.find(p => p.id === pilih);

  const muat = useCallback(async () => {
    const seq = ++loadSeq.current;
    setLoading(true);
    try {
      const responses = await Promise.all([
        axios.get(`${ROOT}/laporan`, { params: { page, page_size: 30, status: filterStatus, ...(pilih ? { pegawai_id: pilih } : {}) } }),
        pilih ? axios.get(`${ROOT}/penugasan`, { params: { pegawai_id: pilih } }) : Promise.resolve({ data: { items: [] } }),
        pilih && admin ? axios.get(`${ROOT}/akses`, { params: { pegawai_id: pilih } }) : Promise.resolve({ data: null }),
      ]);
      if (seq !== loadSeq.current) return;
      setLaporan(responses[0].data.items || []); setTotal(responses[0].data.total || 0); setPenugasan(responses[1].data.items || []); setAkses(responses[2].data);
    } catch (e) {
      if (seq === loadSeq.current) { setLaporan([]); setPenugasan([]); setAkses(null); setError(typeof e.response?.data?.detail === "string" ? e.response.data.detail : "Gagal memuat pengelolaan portal. Coba muat ulang."); }
    } finally { if (seq === loadSeq.current) setLoading(false); }
  }, [pilih, admin, page, filterStatus]);
  useEffect(() => {
    let current = true;
    axios.get(`${API}/pegawai`).then(r => { if (current) setPegawai(r.data.items || []); }).catch(() => { if (current) setError("Daftar pegawai gagal dimuat. Buka ulang panel atau periksa koneksi."); });
    return () => { current = false; };
  }, []);
  useEffect(() => {
    setAkses(null); setPenugasan([]); setLaporan([]); setAsset(null); setHasil([]); setEmailBenar(false); setAksesCatatan(""); setReview(null); setCabut(null);
    muat();
    return () => { loadSeq.current += 1; };
  }, [muat]);
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
    const response = await axios.get(`${ROOT}/laporan/${encodeURIComponent(r.id)}/bukti/${i}`, { responseType: "blob" });
    setPreview({ url: URL.createObjectURL(response.data), nama: r.bukti[i].nama });
  };
  const pegawaiTampak = pegawai.filter(p => `${p.nama} ${p.email} ${p.kode_satker}`.toLowerCase().includes(cariPegawai.toLowerCase()));
  const laporanTampak = laporan;
  const totalPages = Math.max(1, Math.ceil(total / 30));

  return <section className="space-y-4" data-testid="penggunaan-portal-panel">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="flex items-center gap-2 text-lg font-semibold"><ShieldCheck size={20} />Portal Pemegang BMN</h3><p className="mt-1 text-sm text-muted-foreground">Penugasan akses, penerimaan dan laporan keadaan barang yang tercatat historis.</p></div><div className="flex flex-wrap gap-2"><a href="/bmn-saya" target="_blank" rel="noopener noreferrer" className={button} data-testid="portal-buka-publik"><ExternalLink size={16} />Buka BMN Saya</a><button type="button" className={button} disabled={busy || loading} data-testid="portal-admin-muat" onClick={() => kerja(muat)}><RefreshCw size={16} />Muat ulang</button></div></div>
    <p className="rounded-xl border bg-muted/30 p-3 text-sm">Penugasan BMN Saya mengikuti BAST yang sah dan lengkap secara otomatis: tidak perlu mengetik barang/dasar atau meminta pemegang menerima ulang. Admin tetap memeriksa email pegawai sekali untuk akses login. Verifikasi laporan keadaan tidak otomatis mengubah kondisi induk, lokasi, pemegang, nilai, penyusutan, jurnal, atau status penghapusan; tindak lanjut resmi melalui modul dan pejabat berwenang.</p>
    {error && <p role="alert" className="rounded-lg bg-red-500/10 p-3 text-sm">{error}</p>}{pesan && <p role="status" className="rounded-lg bg-emerald-500/10 p-3 text-sm">{pesan}</p>}
    <div className="grid gap-3 sm:grid-cols-2"><label className="block text-sm">Cari pegawai<input className={`${input} mt-1`} data-testid="portal-admin-cari-pegawai" value={cariPegawai} onChange={e => setCariPegawai(e.target.value)} placeholder="Nama, email, atau satker" /></label><label className="block text-sm">Pegawai<select className={`${input} mt-1`} data-testid="portal-admin-pegawai" disabled={busy} value={pilih} onChange={e => { setPilih(e.target.value); setPage(1); }}><option value="">Semua laporan · pilih pegawai untuk mengelola akses</option>{selected && !pegawaiTampak.some(p => p.id === pilih) && <option value={selected.id}>{selected.nama}</option>}{pegawaiTampak.map(p => <option key={p.id} value={p.id}>{p.nama} · {p.kode_satker || "Satker belum diisi"}</option>)}</select></label></div>
    {loading && <p role="status" className="text-sm text-muted-foreground">Memuat penugasan dan laporan…</p>}
    {pilih && <>
      {admin && akses && <section className="space-y-3 rounded-xl border p-4"><h4 className="font-semibold">Persetujuan email portal</h4><p className="break-words text-sm">{akses.nama || selected?.nama} · {akses.email || "Email belum diisi di Master Pegawai"}</p><p className="text-sm">Akses: <strong>{akses.akses?.aktif ? "Aktif" : "Tidak aktif"}</strong>{akses.akses?.verified_at ? ` · Diperiksa ${when(akses.akses.verified_at)}` : ""}</p>
        <p className="text-xs text-muted-foreground">Periksa bahwa alamat hanya dimiliki pegawai bersangkutan. Email kosong/duplikat, satker tidak sesuai, atau pegawai tidak memenuhi syarat akan ditolak server. Perubahan email/identitas membutuhkan pemeriksaan ulang.</p>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={emailBenar} data-testid="portal-admin-email-benar" disabled={busy} onChange={e => setEmailBenar(e.target.checked)} /><span>Saya telah memeriksa bahwa email tersebut benar milik pegawai ini dan bukan alamat bersama.</span></label>
        <label className="block text-sm">Alasan / hasil pemeriksaan<textarea className={`${input} mt-1`} rows={2} maxLength={2000} value={aksesCatatan} data-testid="portal-admin-akses-catatan" onChange={e => setAksesCatatan(e.target.value)} /></label><div className="flex flex-wrap gap-2"><button type="button" className={primary} disabled={busy || loading || !emailBenar || !akses.email} data-testid="portal-admin-aktifkan" onClick={() => kerja(() => ubahAkses(true))}>Setujui akses email</button><button type="button" className={button} disabled={busy || loading || !akses.akses?.aktif} data-testid="portal-admin-nonaktifkan" onClick={() => kerja(() => ubahAkses(false))}>Cabut akses portal</button></div>
      </section>}
      {!admin && <p className="text-sm text-muted-foreground">Persetujuan email serta pemetaan/pencabutan penugasan portal dilakukan admin satker. Operator dapat memeriksa laporan sesuai kewenangannya.</p>}
      <section className="space-y-3 rounded-xl border p-4"><h4 className="font-semibold">Penugasan portal · {selected?.nama}</h4>
        {!penugasan.length && !loading && <p className="text-sm text-muted-foreground">Belum ada penugasan portal untuk pegawai ini.</p>}
        {penugasan.map(a => <article key={a.id} className="space-y-2 rounded-lg border p-3"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-medium">{a.asset_name}</p><p className="text-xs text-muted-foreground">{a.asset_code} · NUP {a.NUP} · {STATUS_PENUGASAN[a.status] || a.status}</p></div>{admin && a.status !== "dicabut" && <button type="button" className={button} disabled={busy} data-testid={`portal-admin-cabut-${a.id}`} onClick={() => setCabut({ item: a, catatan: "" })}>Cabut penugasan portal</button>}</div><p className="break-words text-sm">Dasar: {a.dasar_penugasan}</p>{a.konfirmasi && <p className="text-sm">Pernyataan: {a.konfirmasi.keputusan === "terima" ? "Menerima" : "Menyanggah"} · {a.konfirmasi.catatan || "Tanpa catatan"}</p>}{a.akses_valid === false && <p className="text-sm text-amber-600">Perlu diperiksa: {a.alasan_akses || "Akses tidak lagi memenuhi syarat."}</p>}</article>)}
        {admin && <details className="rounded-lg border p-3"><summary className="cursor-pointer text-sm font-medium" data-testid="portal-admin-tambah-toggle">Pengecualian / penugasan lama yang belum bersumber dari BAST otomatis</summary><div className="mt-3 space-y-3"><p className="text-xs text-muted-foreground">Alur normal cukup menyelesaikan BAST. Gunakan pencatatan manual ini hanya untuk dasar penugasan lama/di luar alur otomatis yang sudah diperiksa; tidak memindahkan pemegang resmi dan masih memerlukan konfirmasi penerimaan portal.</p><label className="block text-sm">Cari aset<input className={`${input} mt-1`} data-testid="portal-admin-cari-aset" value={search} onChange={e => { setSearch(e.target.value); setAsset(null); }} placeholder="Minimal 2 karakter nama/kode" /></label><p className="text-xs text-muted-foreground">Hasil mengikuti lingkup satker aktif. Pilih baris kegiatan yang menjadi acuan; identitas fisik dan kecocokan pemegang akan diperiksa server.</p>
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
    <section className="space-y-3"><div className="flex flex-wrap items-center justify-between gap-3"><h4 className="font-semibold">Pemeriksaan laporan pemegang</h4><label className="text-sm">Status<select className={`${input} mt-1`} data-testid="portal-admin-status" value={filterStatus} disabled={busy} onChange={e => { setFilterStatus(e.target.value); setPage(1); }}><option value="">Semua status</option>{Object.entries(LABEL_STATUS).filter(([id]) => id !== "menunggu_verifikasi").map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label></div>
      {!laporanTampak.length && !loading && <p className="rounded-lg border p-4 text-sm text-muted-foreground">Tidak ada laporan sesuai pilihan.</p>}
      {laporanTampak.map(r => <article key={r.id} className="space-y-3 rounded-xl border p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><h5 className="font-semibold">{r.asset_name}</h5><p className="text-sm text-muted-foreground">{r.pegawai_nama} · {r.asset_code} / NUP {r.NUP}</p></div><span className="text-xs font-medium">{LABEL_STATUS[r.status] || r.status}</span></div><p className="text-xs text-muted-foreground">{LABEL_LAPORAN[r.jenis]} · Diterima server {when(r.created_at)}{r.diambil_pada ? ` · Waktu bukti menurut pelapor ${when(r.diambil_pada)}` : ""}</p><p className="text-sm">Kondisi dilaporkan: {r.kondisi} · {r.status_operasional?.replaceAll("_", " ")}</p><p className="text-sm">Lokasi dilaporkan: {r.lokasi_laporan || "Tidak diisi"}</p><p className="whitespace-pre-wrap break-words text-sm">{r.catatan}</p>
        {r.jenis === "kehilangan" && <p className="rounded-lg bg-amber-500/10 p-3 text-sm">Perlu penanganan pengamanan segera. Kehilangan belum menetapkan kesalahan, TGR, atau penghapusan; ikuti prosedur dan kewenangan instansi.</p>}
        {!!r.perlu_tindak_lanjut?.length && <p className="text-sm text-amber-600">Tindak lanjut: {r.perlu_tindak_lanjut.join(", ")}</p>}
        {!!r.bukti?.length && <div className="flex flex-wrap gap-2">{r.bukti.map((p, i) => <button type="button" key={i} className={button} disabled={busy} data-testid={`portal-admin-bukti-${r.id}-${i}`} onClick={() => kerja(() => lihat(r, i))}><Search size={15} />Periksa foto {i + 1}</button>)}</div>}
        {r.tinjauan?.map((t, i) => <p key={i} className="rounded-lg bg-muted p-3 text-sm"><strong>{LABEL_STATUS[t.keputusan] || t.keputusan}</strong> · {when(t.tanggal)}<br />{t.catatan}</p>)}
        {writer && ["diajukan", "menunggu_verifikasi"].includes(r.status) && <button type="button" className={primary} data-testid={`portal-admin-tinjau-${r.id}`} disabled={busy} onClick={() => setReview({ item: r, keputusan: "perlu_perbaikan", catatan: "" })}><FileCheck2 size={16} />Periksa & beri keputusan</button>}
      </article>)}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3"><p className="text-sm text-muted-foreground">{total} laporan · Halaman {page} dari {totalPages}</p><div className="flex gap-2"><button type="button" className={button} data-testid="portal-admin-sebelumnya" disabled={busy || loading || page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>Sebelumnya</button><button type="button" className={button} data-testid="portal-admin-berikutnya" disabled={busy || loading || page >= totalPages} onClick={() => setPage(p => p + 1)}>Berikutnya</button></div></div>
    </section>
    {review && <section className="space-y-3 rounded-xl border border-primary/40 p-4" aria-label="Pemeriksaan laporan"><h4 className="font-semibold">Pemeriksaan · {review.item.asset_name}</h4><p className="text-sm">Keputusan memvalidasi laporan dan kelengkapan bukti saja. Tidak mengesahkan transaksi akuntansi atau mengganti data induk. Pelapor tidak boleh memverifikasi laporannya sendiri.</p><label className="block text-sm">Keputusan<select className={`${input} mt-1`} data-testid="portal-admin-keputusan" value={review.keputusan} onChange={e => setReview(v => ({ ...v, keputusan: e.target.value }))}><option value="perlu_perbaikan">Minta klarifikasi / perbaikan</option><option value="terverifikasi">Laporan sesuai dan terverifikasi</option><option value="ditolak">Tolak dengan alasan</option></select></label><label className="block text-sm">Hasil pemeriksaan dan arahan tindak lanjut<textarea className={`${input} mt-1`} data-testid="portal-admin-tinjauan-catatan" maxLength={4000} rows={4} value={review.catatan} onChange={e => setReview(v => ({ ...v, catatan: e.target.value }))} /></label><div className="flex flex-wrap gap-2"><button type="button" className={primary} disabled={busy} data-testid="portal-admin-tinjau-simpan" onClick={() => kerja(async () => {
      if (review.catatan.trim().length < 5) throw new Error("Tuliskan hasil pemeriksaan dan alasannya (minimal 5 karakter).");
      await post(`/laporan/${encodeURIComponent(review.item.id)}/tinjau`, { version: review.item.version, keputusan: review.keputusan, catatan: review.catatan.trim() }, review.item.version);
      setReview(null); await muat(); setPesan("Hasil pemeriksaan tersimpan dalam riwayat. Lanjutkan tindakan administratif melalui modul terkait sesuai kewenangan.");
    })}>Catat hasil pemeriksaan</button><button type="button" className={button} disabled={busy} data-testid="portal-admin-tinjau-batal" onClick={() => setReview(null)}>Batal</button></div></section>}
    {preview && <section role="dialog" aria-modal="true" aria-label="Bukti laporan pemegang" className="fixed inset-0 z-[150] flex flex-col bg-black/90 p-4"><div className="mb-3 flex items-center justify-between gap-3 text-white"><p className="min-w-0 truncate text-sm">{preview.nama}</p><button type="button" autoFocus className={button} data-testid="portal-admin-tutup-bukti" onClick={() => setPreview(null)}>Tutup</button></div><img src={preview.url} alt={preview.nama} className="min-h-0 flex-1 object-contain" /></section>}
  </section>;
}
