import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Camera, CheckCircle2, FileText, LogOut, Mail, PackageCheck, RefreshCw, ShieldCheck, Upload, WifiOff, X } from "lucide-react";
import {
  aktifkanLuringPortal, bacaBuktiPortal, bacaLuringPortal, hapusDrafPortal, hapusLuringPortal,
  kunciPortal, LABEL_LAPORAN, LABEL_STATUS, pemilikPortal, periksaAntreanPortal, portalRequest,
  simpanDrafPortal, simpanSnapshotPortal, STATUS_PENUGASAN, tenggatPortal,
} from "@/lib/portalPemegang";

const input = "w-full min-w-0 rounded-lg border border-input bg-background px-3 py-2 text-sm";
const button = "inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium disabled:opacity-50";
const primary = `${button} border-primary bg-primary text-primary-foreground`;
const blankReport = assignment => ({ penugasan_id: assignment.id, penugasan_version: assignment.version,
  jenis: "berkala", kondisi: "Tidak diketahui", status_operasional: "tidak_diketahui",
  lokasi_laporan: "", catatan: "", diambil_pada: "", bukti: [] });
const tanggal = value => value ? new Date(value).toLocaleString("id-ID") : "—";

export default function PortalPemegangPage() {
  const [token, setToken] = useState("");
  const [sesi, setSesi] = useState(null);
  const [email, setEmail] = useState("");
  const [aset, setAset] = useState([]);
  const [laporan, setLaporan] = useState([]);
  const [antrean, setAntrean] = useState([]);
  const [luring, setLuring] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [pesan, setPesan] = useState("");
  const [error, setError] = useState("");
  const [tab, setTab] = useState("aset");
  const [search, setSearch] = useState("");
  const [form, setForm] = useState(null);
  const [draftId, setDraftId] = useState(null);
  const [terkunci, setTerkunci] = useState(false);
  const [konfirmasi, setKonfirmasi] = useState(null);
  const [bukti, setBukti] = useState(null);
  const sesiRef = useRef(null);
  const mounted = useRef(true);
  const fileRef = useRef(null);
  const cameraRef = useRef(null);
  const requestKey = useRef(kunciPortal());
  const payloadTerkirim = useRef(null);

  // Bersihkan fragmen SEBELUM efek jaringan. GET/email scanner tidak pernah
  // mengonsumsi token; pengguna tetap menekan tombol Masuk secara eksplisit.
  useLayoutEffect(() => {
    const value = new URLSearchParams(window.location.hash.slice(1)).get("token");
    if (value) {
      setToken(value);
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }
  }, []);

  const bersihkan = useCallback(async (message = "Sesi berakhir. Minta tautan masuk baru melalui email.") => {
    sesiRef.current = null;
    setSesi(null); setAset([]); setLaporan([]); setAntrean([]); setForm(null);
    setLuring(false); setKonfirmasi(null); setBukti(null); setTerkunci(false); payloadTerkirim.current = null; setPesan(message);
    await hapusLuringPortal().catch(() => {});
  }, []);

  const tangani = useCallback(async e => {
    if (e.status === 401) await bersihkan();
    else setError(e.message || "Tidak dapat terhubung. Draf yang sudah disimpan tetap ada sampai batas sesi.");
  }, [bersihkan]);

  const muat = useCallback(async () => {
    const active = await portalRequest("/sesi");
    if (!mounted.current) return;
    // Pergantian identitas mencabut seluruh tampilan dan data perangkat lama.
    if (sesiRef.current && pemilikPortal(sesiRef.current) !== pemilikPortal(active)) await bersihkan("");
    sesiRef.current = active; setSesi(active);
    const cache = await bacaLuringPortal(active).catch(() => ({ aktif: false, antrean: [], aset: [] }));
    if (!mounted.current || sesiRef.current !== active) return;
    setAntrean(cache.antrean); setLuring(cache.aktif);
    const [assetsResult, reportsResult] = await Promise.all([portalRequest("/aset"), portalRequest("/laporan")]);
    if (!mounted.current || sesiRef.current !== active) return;
    const assignments = assetsResult.items || [];
    setAset(assignments); setLaporan(reportsResult.items || []);
    if (cache.aktif) await simpanSnapshotPortal(active, assignments);
    return { sesi: active, aset: assignments };
  }, [bersihkan]);

  useEffect(() => {
    mounted.current = true;
    muat().catch(e => {
      if (!mounted.current) return;
      if (e.status === 401) bersihkan("");
      else setError("Hubungkan internet untuk memeriksa sesi. Masuk pertama dan membuka ulang portal memerlukan koneksi.");
    }).finally(() => { if (mounted.current) setLoading(false); });
    return () => { mounted.current = false; };
  }, [muat, bersihkan]);

  useEffect(() => {
    const changed = () => setOnline(navigator.onLine);
    window.addEventListener("online", changed); window.addEventListener("offline", changed);
    return () => { window.removeEventListener("online", changed); window.removeEventListener("offline", changed); };
  }, []);

  useEffect(() => {
    if (!sesi) return undefined;
    const interval = setInterval(() => {
      if (tenggatPortal(sesi) <= Date.now()) bersihkan("Batas penyimpanan sesi tercapai; data perangkat telah dibersihkan. Masuk kembali untuk melanjutkan.");
    }, 15000);
    return () => clearInterval(interval);
  }, [sesi, bersihkan]);

  useEffect(() => () => { if (bukti?.url) URL.revokeObjectURL(bukti.url); }, [bukti]);

  const kerja = async fn => {
    if (busy) return;
    setBusy(true); setError(""); setPesan("");
    try { await fn(); } catch (e) { await tangani(e); }
    finally { setBusy(false); }
  };
  const aktifkan = async () => {
    if (luring) {
      if (antrean.length && !window.confirm("Hapus seluruh draf dan foto yang hanya tersimpan pada perangkat ini?")) return;
      await hapusLuringPortal(); setLuring(false); setAntrean([]);
    } else {
      await aktifkanLuringPortal(sesi); await simpanSnapshotPortal(sesi, aset); setLuring(true);
      setPesan("Penyimpanan luring aktif hanya sampai batas sesi yang ditampilkan (maksimal 30 menit tanpa pemeriksaan daring). Keluar/kedaluwarsa akan menghapus draf dan foto lokal; kirim sebelum batas waktu.");
    }
  };
  const bukaForm = assignment => {
    setForm(blankReport(assignment)); setDraftId(null); requestKey.current = kunciPortal(); payloadTerkirim.current = null; setTerkunci(false); setError(""); setTab("aset");
  };
  const lampirkan = async e => {
    const files = Array.from(e.target.files || []); e.target.value = "";
    const assignmentId = form.penugasan_id;
    try { const photos = await bacaBuktiPortal(files, form.bukti); setForm(f => f?.penugasan_id === assignmentId ? ({ ...f, bukti: photos }) : f); }
    catch (err) { setError(err.message); }
  };
  const payloadForm = () => ({ ...form, catatan: form.catatan.trim(),
    ...(form.diambil_pada ? { diambil_pada: new Date(form.diambil_pada).toISOString() } : { diambil_pada: null }) });
  const simpan = async siap => {
    if (!luring) throw new Error("Aktifkan penyimpanan pada perangkat pribadi terlebih dahulu.");
    if (form.catatan.trim().length < 5) throw new Error("Tuliskan hasil pemeriksaan atau kronologi minimal 5 karakter.");
    const next = await simpanDrafPortal(sesi, payloadForm(), { id: draftId, key: requestKey.current, siap });
    setAntrean(next); setForm(null); setDraftId(null); setPesan(siap ? "Masuk antrean perangkat, BELUM dikirim. Saat tersambung tekan Kirim antrean; penugasan akan diperiksa ulang." : "Draf tersimpan pada perangkat, belum dikirim.");
  };
  const kirim = async () => {
    if (form.catatan.trim().length < 5) throw new Error("Tuliskan hasil pemeriksaan atau kronologi minimal 5 karakter.");
    if (!navigator.onLine) { await simpan(true); return; }
    const fresh = await muat();
    if (!fresh) return;
    const candidate = { owner: pemilikPortal(sesi), expires: tenggatPortal(sesi), payload: form };
    const invalid = periksaAntreanPortal(candidate, fresh.sesi, fresh.aset);
    if (invalid) throw new Error(invalid);
    payloadTerkirim.current = payloadTerkirim.current || payloadForm();
    setTerkunci(true);
    try {
      await portalRequest("/laporan", { method: "POST", body: payloadTerkirim.current, csrf: fresh.sesi.csrf_token,
        version: form.penugasan_version, key: requestKey.current });
    } catch (e) {
      if (e.status && e.status < 500 && e.status !== 409) { setTerkunci(false); payloadTerkirim.current = null; }
      throw e;
    }
    if (draftId && luring) setAntrean(await hapusDrafPortal(fresh.sesi, draftId));
    setForm(null); setDraftId(null); setTerkunci(false); payloadTerkirim.current = null; setPesan("Laporan diterima untuk pemeriksaan operator. Data induk dan pembukuan belum berubah."); await muat();
  };
  const kirimAntrean = async () => {
    const fresh = await muat();
    if (!fresh) return;
    const queue = await bacaLuringPortal(fresh.sesi);
    let sent = 0;
    for (const d of queue.antrean.filter(v => v.siap)) {
      const invalid = periksaAntreanPortal(d, fresh.sesi, fresh.aset);
      if (invalid) throw new Error(`${invalid} Antrean tetap tersimpan sampai batas sesi.`);
      await portalRequest("/laporan", { method: "POST", body: d.payload, csrf: fresh.sesi.csrf_token, version: d.payload.penugasan_version, key: d.key });
      setAntrean(await hapusDrafPortal(fresh.sesi, d.id)); sent += 1;
    }
    await muat(); setPesan(`${sent} laporan berhasil dikirim untuk pemeriksaan.`);
  };
  const lihatBukti = async (report, index) => {
    const pemilik = pemilikPortal(sesiRef.current);
    const data = await portalRequest(`/laporan/${encodeURIComponent(report.id)}/bukti/${index}`, { blob: true });
    if (!mounted.current || pemilik !== pemilikPortal(sesiRef.current) || tenggatPortal(sesiRef.current) <= Date.now()) return;
    setBukti({ url: URL.createObjectURL(data), nama: report.bukti[index].nama });
  };

  const tampak = aset.filter(a => `${a.asset_name} ${a.asset_code} ${a.NUP} ${a.location}`.toLowerCase().includes(search.toLowerCase()));
  return <main className="min-h-screen bg-background text-foreground" data-testid="portal-pemegang">
    <div className="mx-auto max-w-5xl space-y-5 px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
        <div className="flex items-center gap-3"><ShieldCheck className="h-9 w-9 text-primary" aria-hidden="true" /><div><h1 className="text-xl font-bold">BMN Saya</h1><p className="text-sm text-muted-foreground">AMAN · Portal pemegang barang</p></div></div>
        {sesi && <button type="button" className={button} data-testid="portal-keluar" disabled={busy} onClick={() => kerja(async () => {
          if (antrean.length && !window.confirm("Keluar akan menghapus draf dan foto yang belum dikirim dari perangkat ini. Tetap keluar?")) return;
          try { await portalRequest("/auth/keluar", { method: "POST", csrf: sesi.csrf_token }); await bersihkan("Anda telah keluar. Data luring perangkat dibersihkan."); }
          catch (e) { await bersihkan("Data perangkat dibersihkan. Sesi server belum dapat dicabut; sambungkan internet lalu keluar kembali, atau tunggu sesi berakhir."); throw e; }
        })}><LogOut size={16} />Keluar</button>}
      </header>
      {error && <p role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm">{error}</p>}
      {pesan && <p role="status" className="rounded-xl border border-primary/20 bg-primary/5 p-3 text-sm">{pesan}</p>}
      {loading ? <p role="status" className="p-6 text-center">Memeriksa sesi…</p> : !sesi || token ? <section className="mx-auto max-w-md space-y-4 rounded-2xl border p-5">
        <h2 className="text-lg font-semibold">Barang yang diamanahkan kepada Anda</h2>
        <p className="text-sm text-muted-foreground">Gunakan email pribadi yang sudah dicatat dan disetujui admin satker di Master Pegawai. Tidak perlu membuat akun staf.</p>
        {token && <div className="space-y-3 rounded-xl bg-primary/5 p-3"><p className="text-sm">Tautan siap diperiksa. Tekan tombol berikut hanya jika Anda sendiri meminta tautan masuk ini.</p><button type="button" className={`${primary} w-full`} data-testid="portal-masuk-token" disabled={busy || !online} onClick={() => kerja(async () => {
          await portalRequest("/auth/masuk", { method: "POST", body: { token } }); setToken(""); await muat();
        })}>Masuk ke BMN Saya</button><p className="text-xs text-muted-foreground">Gunakan browser tempat Anda meminta tautan. Bila berbeda atau kedaluwarsa, minta tautan baru di bawah.</p></div>}
        <form className="space-y-3" onSubmit={e => { e.preventDefault(); kerja(async () => {
          const result = await portalRequest("/auth/minta-link", { method: "POST", body: { email: email.trim() } });
          setToken(""); setPesan(result.pesan || result.message || "Jika email memenuhi syarat, tautan masuk akan dikirim. Periksa kotak masuk dan folder spam.");
        }); }}>
          <label className="block space-y-1 text-sm" htmlFor="portal-email"><span>Email terdaftar</span><input id="portal-email" data-testid="portal-email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={e => setEmail(e.target.value)} className={input} /></label>
          <button className={`${primary} w-full`} data-testid="portal-minta-link" disabled={busy || !online}><Mail size={16} />Kirim tautan masuk</button>
        </form>
        <p className="text-xs text-muted-foreground">Email belum terdaftar, berubah, atau dipakai bersama? Hubungi admin satker. Tautan masuk tidak berfungsi sebagai tanda tangan elektronik.</p>
      </section> : <>
        <section className="space-y-2"><h2 className="text-lg font-semibold">{sesi.pegawai.nama}</h2><p className="text-sm text-muted-foreground">Satker {sesi.pegawai.kode_satker} · Kirim draf sebelum {tanggal(tenggatPortal(sesi))}</p>
          {!online && <p role="status" className="flex items-center gap-2 text-sm text-amber-600"><WifiOff size={16} />Luring: perubahan belum dikirim ke operator.</p>}
          <p className="text-sm text-muted-foreground">Laporan Anda menjadi bukti pemeriksaan. Kondisi induk, pemegang resmi, nilai dan pembukuan hanya berubah melalui proses berwenang.</p>
        </section>
        <div className="flex flex-wrap items-center justify-between gap-3"><nav className="flex flex-wrap gap-2" aria-label="Menu portal">
          {[["aset", "Barang Saya"], ["laporan", "Laporan Saya"], ["antrean", `Draf & Antrean (${antrean.length})`]].map(([id, label]) => <button key={id} type="button" aria-pressed={tab === id} className={tab === id ? primary : button} data-testid={`portal-tab-${id}`} onClick={() => setTab(id)}>{label}</button>)}
        </nav><button type="button" className={button} disabled={busy || !online} data-testid="portal-muat-ulang" onClick={() => kerja(muat)}><RefreshCw size={16} />Muat ulang</button></div>
        {tab === "aset" && <section className="space-y-3">
          <label htmlFor="portal-cari" className="block text-sm">Cari barang<input id="portal-cari" data-testid="portal-cari" className={`${input} mt-1`} value={search} onChange={e => setSearch(e.target.value)} placeholder="Nama, kode, NUP, atau lokasi" /></label>
          {!aset.length && <p className="rounded-xl border p-5 text-sm">Belum ada penugasan yang dapat diakses. Hubungi operator untuk menautkan barang berdasarkan dokumen penugasan yang sah.</p>}
          {!!aset.length && !tampak.length && <p className="text-sm">Tidak ada barang sesuai pencarian.</p>}
          <div className="grid gap-3 sm:grid-cols-2">{tampak.map(a => <article className="min-w-0 space-y-3 rounded-xl border p-4" key={a.id} data-testid={`portal-aset-${a.id}`}>
            <div className="flex gap-2"><PackageCheck size={20} className="shrink-0 text-primary" /><h3 className="break-words font-semibold">{a.asset_name || "Aset"}</h3></div>
            <p className="break-words text-sm text-muted-foreground">{a.asset_code} · NUP {a.NUP}</p><p className="text-xs font-medium">{STATUS_PENUGASAN[a.status] || a.status}</p>
            <dl className="space-y-1 text-sm"><div><dt className="text-muted-foreground">Kondisi di data induk</dt><dd>{a.condition || "Belum dicatat"}</dd></div><div><dt className="text-muted-foreground">Lokasi di data induk</dt><dd>{a.location || "Belum dicatat"}</dd></div><div><dt className="text-muted-foreground">Dasar penugasan</dt><dd className="break-words">{a.dasar_penugasan || "—"}</dd></div></dl>
            {a.sumber_bast && <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs" data-testid={`portal-aset-bast-${a.id}`}><p className="font-medium">{a.penerimaan_otomatis ? "Penerimaan tercatat melalui BAST sah" : "Bersumber dari BAST"}</p><p className="break-words">{a.sumber_bast.nomor || "Nomor belum tercatat"} · {String(a.sumber_bast.tanggal || "").slice(0, 10)}</p>{a.penerimaan_otomatis && <p>Tidak perlu menerima ulang; langsung laporkan keadaan barang.</p>}{a.sumber_bast.jangka_sampai && <p className="mt-1">Batas penggunaan sementara: {String(a.sumber_bast.jangka_sampai).slice(0, 10)}. Lewat jangka waktu tidak berarti barang sudah dikembalikan; hubungi operator untuk penyelesaian.</p>}</div>}
            {a.status === "menunggu_konfirmasi" && !a.penerimaan_otomatis ? <button type="button" className={button} data-testid={`portal-konfirmasi-${a.id}`} disabled={busy || !online} onClick={() => setKonfirmasi({ aset: a, keputusan: "terima", catatan: "" })}>Konfirmasi penerimaan</button>
              : a.status === "diterima" ? <button type="button" className={primary} data-testid={`portal-buat-laporan-${a.id}`} disabled={busy} onClick={() => bukaForm(a)}><FileText size={16} />Laporkan keadaan</button>
                : <p className="text-xs text-muted-foreground">Hubungi operator untuk penyelesaian penugasan.</p>}
          </article>)}</div>
        </section>}
        {konfirmasi && <section className="space-y-3 rounded-xl border border-primary/40 p-4" aria-label="Konfirmasi penerimaan">
          <h3 className="font-semibold">Konfirmasi {konfirmasi.aset.asset_name}</h3><p className="text-sm">Konfirmasi ini mencatat pernyataan penerimaan, bukan pengganti BAST/TTD. Jika belum menerima atau barang berbeda, pilih sanggahan.</p>
          <label className="block text-sm">Pernyataan<select className={`${input} mt-1`} data-testid="portal-konfirmasi-keputusan" value={konfirmasi.keputusan} onChange={e => setKonfirmasi(v => ({ ...v, keputusan: e.target.value }))}><option value="terima">Saya sudah menerima dan memeriksa barang</option><option value="sanggah">Saya belum menerima / terdapat ketidaksesuaian</option></select></label>
          <label className="block text-sm">Catatan<textarea className={`${input} mt-1`} data-testid="portal-konfirmasi-catatan" rows={3} maxLength={2000} value={konfirmasi.catatan} onChange={e => setKonfirmasi(v => ({ ...v, catatan: e.target.value }))} /></label>
          <div className="flex flex-wrap gap-2"><button type="button" className={primary} disabled={busy || !online} data-testid="portal-konfirmasi-simpan" onClick={() => kerja(async () => {
            if (konfirmasi.keputusan === "sanggah" && konfirmasi.catatan.trim().length < 5) throw new Error("Jelaskan ketidaksesuaian atau alasan belum menerima barang (minimal 5 karakter).");
            await portalRequest(`/penugasan/${encodeURIComponent(konfirmasi.aset.id)}/konfirmasi`, { method: "POST", body: { keputusan: konfirmasi.keputusan, catatan: konfirmasi.catatan, version: konfirmasi.aset.version }, csrf: sesi.csrf_token, version: konfirmasi.aset.version });
            setKonfirmasi(null); await muat(); setPesan("Pernyataan Anda tercatat dalam riwayat penugasan.");
          })}>Simpan pernyataan</button><button type="button" className={button} data-testid="portal-konfirmasi-batal" onClick={() => setKonfirmasi(null)}>Batal</button></div>
        </section>}
        {form && <section className="space-y-4 rounded-xl border border-primary/40 p-4" aria-label="Form laporan" data-testid="portal-form-laporan">
          <div className="flex items-start justify-between gap-3"><h3 className="font-semibold">Laporan keadaan barang</h3><button type="button" aria-label="Tutup form laporan" className={button} data-testid="portal-tutup-form" disabled={busy} onClick={() => { if ((!form.catatan && !form.bukti.length) || window.confirm("Tutup tanpa menyimpan perubahan pada form? Draf yang sudah disimpan tidak dihapus.")) setForm(null); }}><X size={16} /></button></div>
          <p className="text-sm font-medium">{aset.find(a => a.id === form.penugasan_id)?.asset_name || "Barang penugasan"}</p>
          {terkunci && <p className="rounded-lg bg-amber-500/10 p-3 text-sm">Pengiriman telah dicoba. Isi dikunci sampai hasilnya dipastikan; tekan kirim kembali untuk pemeriksaan dengan kunci yang sama. Jangan membuat laporan pengganti sebelum memeriksa riwayat.</p>}
          <fieldset disabled={busy || terkunci} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2"><label className="block text-sm">Jenis laporan<select className={`${input} mt-1`} data-testid="portal-jenis" value={form.jenis} onChange={e => setForm(f => ({ ...f, jenis: e.target.value }))}>{Object.entries(LABEL_LAPORAN).map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select></label>
            <label className="block text-sm">Kondisi hasil pemeriksaan<select className={`${input} mt-1`} data-testid="portal-kondisi" value={form.kondisi} onChange={e => setForm(f => ({ ...f, kondisi: e.target.value }))}>{["Tidak diketahui", "Baik", "Rusak Ringan", "Rusak Berat"].map(v => <option key={v}>{v}</option>)}</select></label>
            <label className="block text-sm">Keadaan operasional<select className={`${input} mt-1`} data-testid="portal-operasional" value={form.status_operasional} onChange={e => setForm(f => ({ ...f, status_operasional: e.target.value }))}>{[["tidak_diketahui", "Tidak diketahui"], ["digunakan", "Sedang digunakan"], ["tidak_digunakan", "Tidak digunakan"], ["diperbaiki", "Sedang diperbaiki"]].map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select></label>
            <label className="block text-sm">Lokasi yang dilaporkan (opsional)<input className={`${input} mt-1`} data-testid="portal-lokasi" maxLength={300} value={form.lokasi_laporan} onChange={e => setForm(f => ({ ...f, lokasi_laporan: e.target.value }))} /></label>
          </div>
          {form.jenis === "kehilangan" && <p className="rounded-lg bg-amber-500/10 p-3 text-sm">Segera hubungi operator/pengamanan. Foto terkini dan GPS tidak diwajibkan untuk barang hilang. Laporan ini tidak otomatis menghapus barang, menetapkan kesalahan, atau membebankan TGR.</p>}
          {form.jenis === "pengembalian" && <p className="rounded-lg bg-amber-500/10 p-3 text-sm">Permohonan belum mengakhiri tanggung jawab atau mengganti pemegang. Tunggu pemeriksaan, persetujuan dan dokumen serah terima yang sah.</p>}
          <label className="block text-sm">Hasil pemeriksaan / kronologi<textarea className={`${input} mt-1`} data-testid="portal-catatan" rows={4} maxLength={4000} value={form.catatan} onChange={e => setForm(f => ({ ...f, catatan: e.target.value }))} placeholder="Jelaskan keadaan sebenarnya, masalah, dan tindakan yang sudah dilakukan." /></label>
          <label className="block text-sm">Waktu pengambilan bukti (opsional)<input type="datetime-local" className={`${input} mt-1`} data-testid="portal-diambil-pada" value={form.diambil_pada || ""} onChange={e => setForm(f => ({ ...f, diambil_pada: e.target.value }))} /></label>
          <div className="space-y-2"><p className="text-sm font-medium">Bukti foto (opsional)</p><p className="text-xs text-muted-foreground">Maksimal 3 foto, total 3 MB · JPEG/PNG/WebP. Bukti disimpan tanpa kompresi ulang. Hindari wajah, identitas pribadi, atau dokumen sensitif yang tidak relevan.</p>
            <div className="flex flex-wrap gap-2"><button type="button" className={button} data-testid="portal-pilih-foto" disabled={busy} onClick={() => fileRef.current?.click()}><Upload size={16} />Pilih file/foto</button><button type="button" className={button} data-testid="portal-kamera" disabled={busy} onClick={() => cameraRef.current?.click()}><Camera size={16} />Ambil foto</button></div>
            <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" multiple className="hidden" data-testid="portal-berkas-foto" onChange={lampirkan} /><input ref={cameraRef} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="hidden" data-testid="portal-berkas-kamera" onChange={lampirkan} />
            <ul className="space-y-1">{form.bukti.map((p, i) => <li key={`${p.nama}-${i}`} className="flex min-w-0 items-center justify-between gap-2 rounded-lg border px-3 py-1"><span className="truncate text-sm">{p.nama}</span><button type="button" aria-label={`Hapus foto ${p.nama}`} className={button} data-testid={`portal-hapus-foto-${i}`} disabled={busy} onClick={() => setForm(f => ({ ...f, bukti: f.bukti.filter((_, j) => j !== i) }))}><X size={16} /></button></li>)}</ul>
          </div>
          </fieldset>
          <div className="flex flex-wrap gap-2"><button type="button" className={primary} disabled={busy || (terkunci && !online)} data-testid="portal-kirim-laporan" onClick={() => kerja(kirim)}>{online ? "Kirim untuk diperiksa" : "Masukkan antrean"}</button><button type="button" className={button} disabled={busy || !luring || terkunci} data-testid="portal-simpan-draf" onClick={() => kerja(() => simpan(false))}>Simpan draf perangkat</button></div>
        </section>}
        {tab === "laporan" && <section className="space-y-3"><h3 className="font-semibold">Riwayat laporan Anda</h3>{!laporan.length && <p className="text-sm text-muted-foreground">Belum ada laporan terkirim. Draf perangkat ada pada tab Draf & Antrean.</p>}{laporan.map(r => <article key={r.id} className="space-y-2 rounded-xl border p-4" data-testid={`portal-laporan-${r.id}`}><div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold">{r.asset_name}</h4><span className="text-xs font-medium">{LABEL_STATUS[r.status] || r.status}</span></div><p className="text-xs text-muted-foreground">{LABEL_LAPORAN[r.jenis]} · {tanggal(r.created_at)}</p><p className="text-sm">Dilaporkan: {r.kondisi} · {r.status_operasional?.replaceAll("_", " ")} · {r.lokasi_laporan || "Lokasi tidak disebutkan"}</p><p className="whitespace-pre-wrap break-words text-sm">{r.catatan}</p>
          {!!r.bukti?.length && <div className="flex flex-wrap gap-2">{r.bukti.map((p, i) => <button type="button" key={i} className={button} disabled={busy || !online} data-testid={`portal-lihat-bukti-${r.id}-${i}`} onClick={() => kerja(() => lihatBukti(r, i))}>Lihat foto {i + 1}</button>)}</div>}
          {r.tinjauan?.map((t, i) => <p key={i} className="rounded-lg bg-muted p-3 text-sm"><strong>{LABEL_STATUS[t.keputusan] || t.keputusan}</strong> · {tanggal(t.tanggal)}<br />{t.catatan}</p>)}
          {r.status === "perlu_perbaikan" && aset.some(a => a.id === r.penugasan_id && a.status === "diterima") && <button type="button" className={button} data-testid={`portal-perbaiki-${r.id}`} disabled={busy} onClick={() => {
            const a = aset.find(v => v.id === r.penugasan_id); bukaForm(a); setForm({ ...blankReport(a), jenis: r.jenis, kondisi: r.kondisi, status_operasional: r.status_operasional, lokasi_laporan: r.lokasi_laporan || "", catatan: r.catatan || "", laporan_sebelumnya_id: r.id });
          }}>Buat laporan perbaikan tertaut</button>}
        </article>)}</section>}
        {tab === "antrean" && <section className="space-y-3"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">Draf & antrean pada perangkat ini</h3><button type="button" className={primary} disabled={busy || !online || !antrean.some(d => d.siap)} data-testid="portal-kirim-antrean" onClick={() => kerja(kirimAntrean)}>Kirim antrean</button></div><p className="text-sm text-muted-foreground">Belum masuk riwayat server sampai berhasil dikirim. Antrean tidak dikirim otomatis; identitas dan versi penugasan diperiksa ulang. Data lokal dihapus saat keluar/kedaluwarsa.</p>
          {!antrean.length && <p className="text-sm">Belum ada draf atau antrean.</p>}{antrean.map(d => <article key={d.id} className="space-y-2 rounded-xl border p-4"><p className="font-medium">{aset.find(a => a.id === d.payload.penugasan_id)?.asset_name || "Penugasan tidak lagi tersedia"}</p><p className="text-sm">{d.siap ? "Antrean siap dikirim" : "Draf belum diajukan"} · {LABEL_LAPORAN[d.payload.jenis]}</p><p className="whitespace-pre-wrap break-words text-sm">{d.payload.catatan}</p><p className="text-xs text-muted-foreground">Batas penyimpanan: {tanggal(d.expires)}</p><div className="flex flex-wrap gap-2">{!d.siap && <button type="button" className={button} data-testid={`portal-buka-draf-${d.id}`} disabled={busy} onClick={() => {
            const invalid = periksaAntreanPortal(d, sesi, aset); if (invalid) { setError(invalid); return; }
            setForm({ ...d.payload, diambil_pada: d.payload.diambil_pada ? new Date(new Date(d.payload.diambil_pada).getTime() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16) : "" }); setDraftId(d.id); requestKey.current = d.key; payloadTerkirim.current = null; setTerkunci(false); setTab("aset");
          }}>Buka draf</button>}<button type="button" className={button} data-testid={`portal-hapus-draf-${d.id}`} disabled={busy} onClick={() => kerja(async () => { if (window.confirm("Hapus draf/antrean dan bukti lokal ini?")) setAntrean(await hapusDrafPortal(sesi, d.id)); })}>Hapus dari perangkat</button></div></article>)}
        </section>}
        <aside className="space-y-2 rounded-xl border bg-muted/30 p-4"><label className="flex items-start gap-3 text-sm"><input className="mt-1 h-4 w-4" type="checkbox" checked={luring} data-testid="portal-luring-aktif" disabled={busy} onChange={() => kerja(aktifkan)} /><span>Saya menggunakan perangkat pribadi dan mengizinkan penyimpanan draf/foto luring sementara.</span></label><p className="text-xs text-muted-foreground">Jangan aktifkan pada perangkat bersama. Maksimal 10 draf. Kirim sebelum batas waktu di atas: sesi berakhir setelah 30 menit tanpa pemeriksaan daring, atau maksimal 8 jam sejak masuk. Draf/foto lokal dihapus saat keluar, kedaluwarsa, atau sesi ditolak; data yang belum dikirim akan hilang. Tidak ada token masuk disimpan di draf. Buka pertama/ulang memerlukan internet; selama halaman terbuka dan sesi berlaku, draf dapat disimpan luring. Pencabutan akses saat perangkat terputus baru diketahui ketika tersambung kembali.</p></aside>
        <footer className="flex items-start gap-2 border-t pt-4 text-xs text-muted-foreground"><CheckCircle2 size={16} className="shrink-0" /><p>Jaga barang, laporkan keadaan sebenarnya, dan ikuti arahan operator. Verifikasi laporan bukan pengesahan penghapusan, serah terima, kapitalisasi biaya, atau perubahan nilai akuntansi.</p></footer>
      </>}
      {bukti && <section role="dialog" aria-modal="true" aria-label="Bukti laporan" className="fixed inset-0 z-[150] flex flex-col bg-black/90 p-4"><div className="mb-3 flex items-center justify-between gap-3 text-white"><p className="min-w-0 truncate text-sm">{bukti.nama}</p><button autoFocus type="button" className={button} data-testid="portal-tutup-bukti" onClick={() => setBukti(null)}>Tutup</button></div><img src={bukti.url} alt={bukti.nama} className="min-h-0 flex-1 object-contain" /></section>}
    </div>
  </main>;
}
