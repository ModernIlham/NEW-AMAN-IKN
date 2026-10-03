import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Check, Loader2, Search, UserPlus, X } from "lucide-react";
import { kunciPortal } from "@/lib/portalPemegang";

const ROOT = `${process.env.REACT_APP_BACKEND_URL || ""}/api/portal-pemegang/admin`;
const input = "min-h-[44px] w-full min-w-0 rounded-lg border border-input bg-background px-3 py-2 text-sm";
const button = "inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm disabled:opacity-50";
const readError = (error, fallback) => typeof error?.response?.data?.detail === "string" ? error.response.data.detail : fallback;
const samePhysical = (left, right) => left.id === right.id || (left.kunci_fisik || []).some(key => (right.kunci_fisik || []).includes(key));
export const BATAS_PILIHAN_PORTAL = 100;

/** Pengecualian legacy: tiap barang adalah transaksi tersendiri, bukan batch atomik. */
export default function PenugasanPortalMassal({ pegawaiId, disabled = false, onBusyChange, onUncertainChange, onComplete }) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [semuaSatker, setSemuaSatker] = useState(false);
  const [data, setData] = useState({ items: [], total: 0, total_pages: 1 });
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [selected, setSelected] = useState([]);
  const [dasar, setDasar] = useState("");
  const [catatan, setCatatan] = useState("");
  const [error, setError] = useState("");
  const [selectionNotice, setSelectionNotice] = useState("");
  const [results, setResults] = useState({});
  const [progress, setProgress] = useState(null);
  const [processing, setProcessing] = useState(false);
  const alive = useRef(false);
  const running = useRef(false);
  const keys = useRef(new Map());
  const completed = useRef([]);
  const locked = disabled || processing;
  const uncertain = selected.some(a => results[a.id]?.status === "belum_pasti");

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; onBusyChange?.(false); onUncertainChange?.(false); };
  }, [onBusyChange, onUncertainChange]);
  useEffect(() => { onUncertainChange?.(uncertain); }, [uncertain, onUncertainChange]);
  useEffect(() => {
    if (!uncertain && !processing) return undefined;
    const warn = event => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [uncertain, processing]);
  useEffect(() => {
    if (search.trim() === query) return undefined;
    const timer = setTimeout(() => { setQuery(search.trim()); setPage(1); }, 250);
    return () => clearTimeout(timer);
  }, [search, query]);
  useEffect(() => {
    let current = true;
    setLoading(true); setLoadError(""); setData({ items: [], total: 0, total_pages: 1 });
    axios.get(`${ROOT}/kandidat-aset`, { params: { pegawai_id: pegawaiId, search: query, page, page_size: 20, semua_satker: semuaSatker } }).then(r => {
      if (current) setData({ items: r.data.items || [], total: r.data.total || 0, total_pages: r.data.total_pages || 1, message: r.data.message });
    }).catch(e => {
      if (current) setLoadError(readError(e, "Daftar barang gagal dimuat. Pilihan sebelumnya tetap disimpan; coba muat ulang."));
    }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [pegawaiId, query, page, semuaSatker, refresh]);

  const blockedReason = a => {
    if (completed.current.some(done => samePhysical(a, done))) return "Sudah berhasil dicatat dalam sesi ini.";
    if (a.boleh_dipilih !== true) return a.alasan || "Barang belum memenuhi syarat penugasan portal.";
    if (selected.some(chosen => chosen.id !== a.id && samePhysical(a, chosen))) return "Barang fisik ini sudah dipilih dari kegiatan lain.";
    return "";
  };
  const toggle = a => {
    if (locked) return;
    if (selected.some(chosen => chosen.id === a.id)) {
      if (results[a.id]?.status === "belum_pasti") { setError("Selesaikan percobaan ulang barang yang hasilnya belum pasti sebelum melepas pilihan."); return; }
      setSelected(items => items.filter(chosen => chosen.id !== a.id)); return;
    }
    const reason = blockedReason(a);
    if (reason) { setError(reason); return; }
    if (selected.length >= BATAS_PILIHAN_PORTAL) { setError(`Maksimal ${BATAS_PILIHAN_PORTAL} barang per proses. Selesaikan pilihan ini terlebih dahulu.`); return; }
    setSelected(items => [...items, a]); setError("");
  };
  const selectVisible = () => {
    if (locked) return;
    const next = [...selected];
    let duplicate = 0; let unavailable = 0; let ambiguous = 0;
    for (const a of data.items) {
      if (next.length >= BATAS_PILIHAN_PORTAL) break;
      if (next.some(chosen => chosen.id === a.id)) continue;
      if (next.some(chosen => samePhysical(a, chosen))) { duplicate += 1; continue; }
      if (a.boleh_dipilih !== true || completed.current.some(done => samePhysical(a, done))) { unavailable += 1; continue; }
      if (data.items.some(other => other.id !== a.id && other.boleh_dipilih === true && samePhysical(a, other))) { ambiguous += 1; continue; }
      next.push(a);
    }
    setSelected(next); setError("");
    setSelectionNotice(`${next.length - selected.length} barang ditambahkan dari halaman ini. ${ambiguous} baris perlu dipilih kegiatan acuannya satu per satu; ${duplicate} baris barang fisik yang sudah dipilih dan ${unavailable} baris tidak memenuhi syarat dilewati.${next.length >= BATAS_PILIHAN_PORTAL ? " Batas 100 pilihan tercapai." : ""}`);
  };
  const remove = id => {
    if (locked) return;
    if ((id && results[id]?.status === "belum_pasti") || (!id && uncertain)) {
      setError("Selesaikan percobaan ulang barang yang hasilnya belum pasti sebelum melepas pilihan."); return;
    }
    setSelected(items => id ? items.filter(item => item.id !== id) : []);
  };
  const run = async () => {
    if (running.current || disabled) return;
    if (!selected.length || selected.length > BATAS_PILIHAN_PORTAL) { setError("Pilih 1 sampai 100 barang terlebih dahulu."); return; }
    if (dasar.trim().length < 10) { setError("Tuliskan dasar penugasan yang dapat ditelusuri (minimal 10 karakter)."); return; }
    const queue = selected.map(asset => {
      const body = results[asset.id]?.status === "belum_pasti" ? results[asset.id].body : {
        pegawai_id: pegawaiId, asset_id: asset.id, dasar_penugasan: dasar.trim(), catatan: catatan.trim(),
      };
      const signature = JSON.stringify(body);
      if (!keys.current.has(signature)) keys.current.set(signature, kunciPortal());
      return { asset, body, key: keys.current.get(signature) };
    });
    running.current = true; setProcessing(true); onBusyChange?.(true); setError("");
    const summary = { total: queue.length, done: 0, berhasil: 0, gagal: 0, dihentikan: false };
    setProgress({ ...summary });
    try {
      for (const { asset, body, key } of queue) {
        if (!alive.current) return;
        setResults(previous => ({ ...previous, [asset.id]: { asset, status: "mengirim", body, pesan: "Sedang dikirim…" } }));
        try {
          await axios.post(`${ROOT}/penugasan`, body, { headers: { "If-Match": "0", "Idempotency-Key": key }, timeout: 30000 });
          if (!alive.current) return;
          completed.current.push(asset); summary.berhasil += 1;
          setSelected(items => items.filter(a => a.id !== asset.id));
          setResults(previous => ({ ...previous, [asset.id]: { asset, status: "berhasil", pesan: "Pencatatan dikonfirmasi server; lihat status terkini pada monitoring." } }));
        } catch (e) {
          if (!alive.current) return;
          const status = e.response?.status;
          // Galat pada retry (mis. sesi kedaluwarsa/429) tidak membuktikan
          // permintaan pertama yang terputus belum tersimpan di server.
          const unknown = !status || status >= 500 || results[asset.id]?.status === "belum_pasti";
          const stop = unknown || [401, 403, 429].includes(status);
          summary.gagal += 1; summary.dihentikan = stop;
          setResults(previous => ({ ...previous, [asset.id]: { asset, body, status: unknown ? "belum_pasti" : "gagal",
            pesan: readError(e, unknown ? "Hasil belum dapat dipastikan. Coba ulang dengan kunci dan isi yang sama; jangan mencatat ulang dari sesi lain." : "Belum berhasil. Periksa data sebelum mencoba kembali."),
          } }));
        }
        summary.done += 1; setProgress({ ...summary });
        if (summary.dihentikan) break;
      }
      if (alive.current) {
        setRefresh(value => value + 1);
        try { await onComplete?.({ ...summary }); }
        catch { if (alive.current) setError("Hasil per barang sudah tercatat di bawah, tetapi monitoring gagal disegarkan. Muat ulang monitoring; jangan kirim ulang barang yang berhasil."); }
      }
    } finally {
      running.current = false;
      if (alive.current) { setProcessing(false); onBusyChange?.(false); }
    }
  };

  return <div className="space-y-3" data-testid="portal-massal">
    <p className="text-xs leading-relaxed text-muted-foreground">Untuk penugasan lama yang sudah diperiksa. Alur normal tetap melalui BAST sah. Pilih beberapa barang, isi satu dasar, lalu catat per barang; data induk tidak dipindahkan dan pemegang legacy tetap melakukan konfirmasi.</p>
    <div className="flex min-w-0 flex-wrap items-center gap-2"><label className="min-w-0 flex-1 text-sm"><span className="sr-only">Cari barang penugasan lama</span><div className="relative"><Search size={16} className="pointer-events-none absolute left-3 top-3.5 text-muted-foreground" /><input className={`${input} pl-9`} data-testid="portal-admin-cari-aset" disabled={locked} maxLength={120} value={search} onChange={e => setSearch(e.target.value)} placeholder="Cari nama, kode, NUP, atau lokasi" /></div></label><button type="button" className={button} disabled={locked || loading} data-testid="portal-massal-muat" onClick={() => setRefresh(value => value + 1)}>Muat ulang</button></div>
    <label className="flex min-h-[44px] cursor-pointer items-center gap-2 text-xs"><input type="checkbox" data-testid="portal-massal-seluruh-satker" checked={semuaSatker} disabled={locked} onChange={e => { setSemuaSatker(e.target.checked); setPage(1); }} /><span>Tampilkan seluruh barang di satker aktif untuk pemeriksaan penugasan lama</span></label>
    <p className="text-xs text-muted-foreground">{semuaSatker ? "Barang tetap dibatasi satker aktif. Kecocokan pemegang dan dokumen wajib diperiksa; pilihan tidak mengubah pemegang resmi." : "Daftar awal mengikuti nomor identitas pemegang terpilih, bukan hanya kesamaan nama."} Pilih kegiatan acuan yang berlaku; satu barang fisik hanya dipilih sekali.</p>
    {loadError && <p role="alert" className="rounded-lg bg-red-500/10 p-3 text-sm">{loadError}</p>}
    {data.message && <p className="text-sm text-muted-foreground">{data.message}</p>}
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs"><span>{selected.length}/{BATAS_PILIHAN_PORTAL} barang dipilih · {data.total} hasil pencarian</span><button type="button" className={button} disabled={locked || loading || search.trim() !== query || !data.items.length || selected.length >= BATAS_PILIHAN_PORTAL} data-testid="portal-massal-pilih-tampak" onClick={selectVisible}>Pilih hasil halaman ini</button></div>
    {selectionNotice && <p role="status" className="text-xs text-muted-foreground" data-testid="portal-massal-seleksi-info">{selectionNotice}</p>}
    <div className="max-h-72 space-y-1 overflow-y-auto rounded-lg border p-1" aria-busy={loading}>
      {loading && <p role="status" className="p-3 text-sm text-muted-foreground">Memuat barang…</p>}
      {!loading && !data.items.length && !loadError && <p className="p-3 text-sm text-muted-foreground">Tidak ada barang sesuai pencarian. Ubah kata kunci atau periksa lingkup daftar.</p>}
      {data.items.map(a => { const chosen = selected.some(item => item.id === a.id); const reason = blockedReason(a); return <button type="button" key={a.id} aria-pressed={chosen} disabled={locked || (!chosen && !!reason)} onClick={() => toggle(a)} data-testid={`portal-admin-aset-${a.id}`} className={`${button} w-full !justify-start border-transparent text-left ${chosen ? "bg-primary/10 ring-1 ring-inset ring-primary" : "hover:bg-muted/50"}`}><span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${chosen ? "border-primary bg-primary text-primary-foreground" : "border-input"}`}>{chosen && <Check size={14} />}</span><span className="min-w-0 break-words"><span className="font-medium">{a.asset_name || "Aset tanpa nama"}</span><span className="block text-xs text-muted-foreground">{a.asset_code} · NUP {a.NUP} · {a.activity_name || "Kegiatan tercatat"}</span><span className="block text-xs text-muted-foreground">{a.location || "Lokasi belum diisi"} · {a.user || "Pemegang belum diisi"}</span>{reason && <span className="block text-xs text-amber-800 dark:text-amber-300">{reason}</span>}</span></button>; })}
    </div>
    <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-muted-foreground">Halaman {page} dari {data.total_pages}. Pilihan bertahan saat pindah halaman atau mencari.</p><div className="flex min-w-0 flex-wrap gap-2"><button type="button" className={button} disabled={locked || loading || page <= 1} data-testid="portal-massal-sebelumnya" onClick={() => setPage(value => value - 1)}>Sebelumnya</button><button type="button" className={button} disabled={locked || loading || page >= data.total_pages} data-testid="portal-massal-berikutnya" onClick={() => setPage(value => value + 1)}>Berikutnya</button></div></div>
    {!!selected.length && <section className="space-y-2 rounded-lg bg-muted/40 p-3" aria-label="Barang terpilih"><div className="flex flex-wrap items-center justify-between gap-2"><h5 className="text-sm font-medium">{selected.length} barang terpilih</h5><button type="button" className={button} disabled={locked || uncertain} data-testid="portal-massal-reset" onClick={() => remove()}>Kosongkan pilihan</button></div><div className="max-h-48 space-y-1 overflow-y-auto">{selected.map(a => <div key={a.id} className="flex items-center justify-between gap-2 rounded-lg border bg-background pl-3"><p className="min-w-0 break-words text-xs">{a.asset_name} · {a.asset_code} / {a.NUP}</p><button type="button" className={`${button} shrink-0 border-0 px-2`} disabled={locked || results[a.id]?.status === "belum_pasti"} aria-label={`Lepas ${a.asset_name}`} data-testid={`portal-massal-lepas-${a.id}`} onClick={() => remove(a.id)}><X size={16} /></button></div>)}</div></section>}
    {uncertain && <p className="rounded-lg bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-300">Ada hasil yang belum pasti. Pemegang, pilihan terkait, dasar dan catatan dikunci untuk percobaan ulang yang sama. Jangan memuat ulang atau meninggalkan halaman sebelum hasil pasti; kunci percobaan hanya disimpan selama panel ini terbuka. Melipat rincian tidak menghapus pilihan.</p>}
    <label className="block text-sm">Dasar penugasan untuk pilihan ini<input className={`${input} mt-1`} data-testid="portal-admin-dasar" maxLength={1000} disabled={locked || uncertain} value={dasar} onChange={e => setDasar(e.target.value)} placeholder="Nomor/tanggal BAST atau surat penugasan sah" /></label>
    <label className="block text-sm">Catatan<textarea className={`${input} mt-1`} data-testid="portal-admin-penugasan-catatan" maxLength={2000} rows={2} disabled={locked || uncertain} value={catatan} onChange={e => setCatatan(e.target.value)} /></label>
    {error && <p role="alert" className="rounded-lg bg-red-500/10 p-3 text-sm">{error}</p>}
    <button type="button" className={`${button} border-primary bg-primary text-primary-foreground`} data-testid="portal-admin-tambah" disabled={locked || !selected.length} onClick={run}>{processing ? <Loader2 size={16} className="animate-spin" /> : <UserPlus size={16} />}{processing ? "Mencatat per barang…" : `Catat ${selected.length || "pilihan"} barang`}</button>
    {progress && <div className="space-y-2 rounded-lg border p-3" data-testid="portal-massal-hasil"><p role="status" className="text-sm font-medium">{progress.done}/{progress.total} diproses · {progress.berhasil} berhasil · {progress.gagal} belum berhasil{progress.dihentikan ? " · Proses dijeda" : ""}</p><p className="text-xs text-muted-foreground">Proses per barang, bukan satu transaksi sekaligus. Yang berhasil tidak dikirim ulang; pilihan belum berhasil/tidak terkirim tetap tersedia untuk diperiksa dan dicoba ulang.</p><ul className="max-h-56 space-y-2 overflow-y-auto text-xs">{Object.entries(results).map(([id, result]) => <li key={id} className="rounded border p-2" data-testid={`portal-massal-hasil-${id}`}><strong>{result.asset.asset_name} · NUP {result.asset.NUP}</strong><p>{result.status === "berhasil" ? "Berhasil" : result.status === "belum_pasti" ? "Hasil belum pasti" : result.status === "mengirim" ? "Mengirim" : "Belum berhasil"}: {result.pesan}</p></li>)}</ul></div>}
  </div>;
}
