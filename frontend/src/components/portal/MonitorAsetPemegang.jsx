import React from "react";
import { AlertCircle, ArrowUpRight, ClipboardCheck, Clock3, FileText, History, MapPin, PackageCheck, Search } from "lucide-react";
import { LABEL_LAPORAN, LABEL_STATUS, STATUS_PENUGASAN } from "@/lib/portalPemegang";
import { cariAsetPemegang, cocokMonitorPemegang, FILTER_MONITOR, OPERASIONAL_MONITOR, perluPerhatianPemegang, tanggalMonitor } from "./monitorPemegang";

const tombol = "inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50";
const utama = `${tombol} border-primary bg-primary text-primary-foreground hover:bg-primary/90`;
const labelStat = { semua: "Barang dipantau", belum: "Belum dilaporkan", menunggu: "Menunggu pemeriksaan", perhatian: "Perlu perhatian" };
const iconStat = { semua: PackageCheck, belum: ClipboardCheck, menunggu: Clock3, perhatian: AlertCircle };

export function RingkasanMonitorPemegang({ ringkasan, filter, onPilih }) {
  return <section aria-label="Ringkasan pemantauan barang" className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4">
    {FILTER_MONITOR.map(([id]) => {
      const Icon = iconStat[id];
      return <button key={id} type="button" data-testid={`portal-ringkasan-${id}`} aria-pressed={filter === id}
        className={`min-h-[100px] min-w-0 rounded-2xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:p-4 ${filter === id ? "border-primary/50 bg-primary/5" : "bg-card hover:bg-muted/50"}`}
        onClick={() => onPilih(id)}><span className="flex items-center justify-between gap-2"><span className="text-2xl font-bold tabular-nums">{ringkasan[id]}</span><Icon size={19} aria-hidden="true" className="shrink-0 text-primary" /></span><span className="mt-1 block text-xs text-muted-foreground sm:text-sm">{labelStat[id]}</span></button>;
    })}
  </section>;
}

export default function MonitorAsetPemegang({ aset, terbaru, search, onSearch, filter, onFilter, busy, online, onLaporan, onKonfirmasi, onRiwayat }) {
  const tampak = aset.filter(a => cocokMonitorPemegang(a, terbaru.get(a.id), filter) && cariAsetPemegang(a, terbaru.get(a.id), search));
  return <section aria-label="Barang yang Anda pantau" className="space-y-4">
    <div className="grid gap-3 rounded-2xl border bg-card p-4 sm:grid-cols-[minmax(0,1fr)_minmax(180px,240px)]">
      <label htmlFor="portal-cari" className="min-w-0 text-sm font-medium">Cari barang<span className="relative mt-1 block"><Search size={17} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" /><input id="portal-cari" type="search" data-testid="portal-cari" className="min-h-[44px] w-full min-w-0 rounded-xl border border-input bg-background py-2 pl-10 pr-3 text-sm" value={search} onChange={e => onSearch(e.target.value)} placeholder="Nama, kode, NUP, lokasi, atau BAST" /></span></label>
      <label htmlFor="portal-filter" className="min-w-0 text-sm font-medium">Tampilkan<select id="portal-filter" data-testid="portal-filter" value={filter} onChange={e => onFilter(e.target.value)} className="mt-1 min-h-[44px] w-full min-w-0 rounded-xl border border-input bg-background px-3 py-2 text-sm">{FILTER_MONITOR.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <p role="status" className="text-xs text-muted-foreground sm:col-span-2">{tampak.length} dari {aset.length} barang ditampilkan. Ringkasan dihitung dari laporan terakhir setiap barang; satu barang dapat masuk lebih dari satu kategori.</p>
    </div>
    {!aset.length ? <div className="rounded-2xl border border-dashed bg-card p-6 text-center"><PackageCheck size={30} className="mx-auto mb-3 text-primary" aria-hidden="true" /><h3 className="font-semibold">Belum ada barang yang dapat dipantau</h3><p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">Barang muncul setelah BAST lengkap dan sah ditautkan kepada Anda. Bila barang sudah diterima tetapi belum terlihat, hubungi operator atau admin satker untuk memeriksa BAST dan identitas pegawai.</p></div>
      : !tampak.length ? <div className="rounded-2xl border border-dashed bg-card p-6 text-center"><p className="text-sm text-muted-foreground">Tidak ada barang sesuai pencarian dan saringan ini.</p><button type="button" className={`${tombol} mt-3`} data-testid="portal-reset-filter" onClick={() => { onSearch(""); onFilter("semua"); }}>Tampilkan semua barang</button></div> : null}
    <div className="grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3">{tampak.map(a => {
      const terakhir = terbaru.get(a.id);
      const perhatian = perluPerhatianPemegang(a, terakhir);
      return <article className="min-w-0 overflow-hidden rounded-2xl border bg-card shadow-sm" key={a.id} data-testid={`portal-aset-${a.id}`}>
        <div className="space-y-3 p-4 sm:p-5">
          <div className="flex items-start gap-3"><div className="rounded-xl bg-primary/10 p-2.5 text-primary"><PackageCheck size={22} aria-hidden="true" /></div><div className="min-w-0 flex-1"><h3 className="break-words font-semibold leading-snug">{a.asset_name || "Aset"}</h3><p className="mt-1 break-all font-mono text-xs text-muted-foreground">{a.asset_code || "Kode belum dicatat"} · NUP {a.NUP || "—"}</p></div></div>
          <div className="flex flex-wrap gap-2"><span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium">{a.status === "diterima" ? "Dalam tanggung jawab Anda" : STATUS_PENUGASAN[a.status] || a.status}</span>{perhatian && <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-800 dark:text-amber-200"><AlertCircle size={13} aria-hidden="true" />Perlu perhatian</span>}</div>
          <dl className="grid grid-cols-2 gap-3 rounded-xl bg-muted/40 p-3 text-sm"><div className="min-w-0"><dt className="text-xs text-muted-foreground">Kondisi di data induk</dt><dd className="mt-1 break-words font-medium">{a.condition || "Belum dicatat"}</dd></div><div className="min-w-0"><dt className="flex items-center gap-1 text-xs text-muted-foreground"><MapPin size={12} aria-hidden="true" />Lokasi di data induk</dt><dd className="mt-1 break-words font-medium">{a.location || "Belum dicatat"}</dd></div></dl>
          <section className="space-y-2 rounded-xl border p-3" aria-label={`Laporan terakhir ${a.asset_name || "aset"}`} data-testid={`portal-terakhir-${a.id}`}>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Pembaruan terakhir Anda</h4>
            {terakhir ? <><p className={`inline-block rounded-md px-2 py-1 text-xs font-medium ${terakhir.status === "terverifikasi" ? "bg-emerald-500/10 text-emerald-800 dark:text-emerald-200" : "bg-muted text-foreground"}`}>{LABEL_STATUS[terakhir.status] || terakhir.status}</p><p className="text-xs text-muted-foreground">{LABEL_LAPORAN[terakhir.jenis] || "Laporan"} · {tanggalMonitor(terakhir.created_at)}</p><p className="break-words text-sm">{terakhir.kondisi || "Kondisi belum dilaporkan"} · {OPERASIONAL_MONITOR[terakhir.status_operasional] || "Keadaan belum dilaporkan"}</p><p className="break-words text-xs text-muted-foreground">Lokasi dilaporkan: {terakhir.lokasi_laporan || "Tidak disebutkan"}</p>{["perlu_perbaikan", "ditolak"].includes(terakhir.status) && <p className="text-xs text-amber-800 dark:text-amber-200">Buka riwayat untuk membaca catatan petugas sebelum mengirim pembaruan.</p>}</>
              : <><p className="text-sm">Belum ada laporan terkirim.</p><p className="text-xs text-muted-foreground">Periksa barang dan kabarkan keadaan terbarunya. Draf belum dihitung sebagai laporan.</p></>}
            <p className="text-xs text-muted-foreground">Pengamatan Anda, bukan pengganti data induk resmi.</p>
          </section>
          {a.sumber_bast ? <details className="rounded-xl border border-primary/20 bg-primary/5 text-xs" data-testid={`portal-aset-bast-${a.id}`}><summary className="min-h-[44px] cursor-pointer break-words px-3 py-3 font-medium">{a.sumber_bast.nomor || "Dasar BAST"}</summary><div className="space-y-1 px-3 pb-3"><p className="font-medium">{a.penerimaan_otomatis ? "Penerimaan tercatat melalui BAST sah" : "Bersumber dari BAST"}</p><p>Tanggal BAST: {tanggalMonitor(a.sumber_bast.tanggal, true)}</p>{a.penerimaan_otomatis && <p>Tidak perlu menerima ulang; langsung pantau dan laporkan keadaan barang.</p>}{a.sumber_bast.jangka_sampai && <p>Batas penggunaan sementara: {tanggalMonitor(a.sumber_bast.jangka_sampai, true)}. Lewat jangka waktu tidak berarti barang sudah dikembalikan; hubungi operator untuk penyelesaian.</p>}</div></details>
            : <details className="rounded-xl border text-xs"><summary className="min-h-[44px] cursor-pointer px-3 py-3 font-medium">Dasar penugasan lama</summary><p className="break-words px-3 pb-3 text-muted-foreground">{a.dasar_penugasan || "Hubungi operator untuk memeriksa dokumen dasar."}</p></details>}
          <div className="flex flex-wrap gap-2 border-t pt-3">{a.status === "menunggu_konfirmasi" && !a.penerimaan_otomatis ? <button type="button" className={`${tombol} flex-1`} data-testid={`portal-konfirmasi-${a.id}`} disabled={busy || !online} onClick={() => onKonfirmasi(a)}>Konfirmasi penugasan lama</button>
            : a.status === "diterima" ? <button type="button" className={`${utama} flex-1`} data-testid={`portal-buat-laporan-${a.id}`} disabled={busy} onClick={() => onLaporan(a)}><FileText size={16} aria-hidden="true" />Perbarui keadaan<ArrowUpRight size={14} aria-hidden="true" /></button> : <p className="text-xs text-muted-foreground">Hubungi operator untuk penyelesaian penugasan.</p>}
            <button type="button" className={tombol} data-testid={`portal-riwayat-${a.id}`} onClick={() => onRiwayat(a)}><History size={16} aria-hidden="true" />Riwayat</button></div>
        </div>
      </article>;
    })}</div>
  </section>;
}
