import React, { useEffect, useState } from "react";
import axios from "axios";
import { ChevronLeft, ChevronRight, Loader2, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { getSatkerAktif, SATKER_AKTIF_EVENT } from "@/lib/satkerAktif";
import { usePencarianBaca } from "@/hooks/usePencarianBaca";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const PAGE_SIZE = 20;

/** Pemilih aset bersama: seluruh hasil dapat dijangkau, NUP dicari persis.
 * Halaman hasil tidak mengubah pilihan yang disimpan oleh form pemanggil.
 */
export default function PencarianAset({ user, value, onChange, onPilih,
  selectedIds = [], filters = {}, allowEmpty = false, disabled = false,
  id, testId = "cari-aset", itemTestId }) {
  const [satker, setSatker] = useState(getSatkerAktif);
  useEffect(() => {
    const sync = () => setSatker(getSatkerAktif());
    const storage = event => { if (event.key === "satker_aktif" || event.key === null) sync(); };
    window.addEventListener(SATKER_AKTIF_EVENT, sync);
    window.addEventListener("storage", storage);
    sync();
    return () => {
      window.removeEventListener(SATKER_AKTIF_EVENT, sync);
      window.removeEventListener("storage", storage);
    };
  }, []);
  const scope = JSON.stringify([user?.id, String(user?.kode_satker || "").trim() || satker]);
  // Remount hanya konteks pemilih, bukan form/pilihan yang sedang dikerjakan.
  return <HasilPencarian key={scope} {...{ value, onChange, onPilih, selectedIds,
    filters, allowEmpty, disabled, id, testId, itemTestId, scope, satker }} />;
}

function HasilPencarian({ value, onChange, onPilih, selectedIds, filters,
  allowEmpty, disabled, id, testId, itemTestId, scope, satker }) {
  const [nup, setNup] = useState("");
  const [pagination, setPagination] = useState({ key: "", page: 1 });
  const [result, setResult] = useState(null);
  const [retry, setRetry] = useState(0);
  const text = String(value || "").trim();
  const exactNup = nup.trim();
  const validNup = !exactNup || /^[0-9]{1,20}$/.test(exactNup);
  const filterKey = JSON.stringify(filters);
  const queryKey = JSON.stringify([scope, text, exactNup, filterKey, allowEmpty]);
  const page = pagination.key === queryKey ? pagination.page : 1;
  useEffect(() => { setPagination({ key: queryKey, page: 1 }); }, [queryKey]);
  const requestKey = JSON.stringify([queryKey, page, retry]);
  const enabled = validNup && (allowEmpty || text.length >= 2 || !!exactNup);
  const current = result?.key === requestKey ? result : null;
  usePencarianBaca({
    lingkup: scope, kunci: requestKey, aktif: enabled,
    jalankan: signal => axios.get(`${API}/assets`, {
      signal, headers: { "X-Satker-Aktif": satker },
      params: { ...JSON.parse(filterKey), search: text, ...(exactNup ? { nup: exactNup } : {}),
        page, page_size: PAGE_SIZE, sort_by: "oldest", pencarian_lengkap: true },
    }),
    padaHasil: response => { if (getSatkerAktif() === satker) setResult({ key: requestKey, data: response.data }); },
    padaGagal: () => { if (getSatkerAktif() === satker) setResult({ key: requestKey, error: true }); },
  });
  const rows = current?.data?.items || [];
  const total = Number(current?.data?.total || 0);
  const pages = Math.max(1, Number(current?.data?.total_pages || 1));
  const busy = enabled && !current;
  const selected = new Set(selectedIds);
  return <div className="space-y-1.5" data-testid={`${testId}-picker`}>
    <div className="flex gap-2">
      <div className="relative min-w-0 flex-1">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input id={id} aria-label="Cari nama atau kode aset" className="pl-8" disabled={disabled}
          placeholder="Cari nama/kode aset…" value={value} onChange={event => onChange(event.target.value)}
          data-testid={testId} />
      </div>
      <Input aria-label="NUP persis" inputMode="numeric" maxLength={20} className="w-24 shrink-0"
        placeholder="NUP" value={nup} disabled={disabled} aria-invalid={!validNup}
        onChange={event => setNup(event.target.value)} data-testid={`${testId}-nup`} />
    </div>
    {!validNup && <p role="alert" className="text-xs text-red-600">NUP harus berupa 1–20 digit angka.</p>}
    {!enabled && validNup && <p className="text-[11px] text-muted-foreground">Ketik minimal 2 karakter nama/kode, atau isi NUP yang dicari.</p>}
    {enabled && <div className="overflow-hidden rounded-lg border border-border" aria-busy={busy}>
      <div className="max-h-52 overflow-y-auto divide-y divide-border/60">
        {busy ? <div role="status" className="flex items-center justify-center gap-2 p-3 text-xs text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />Mencari aset…
        </div> : current?.error ? <div role="alert" className="p-2 text-xs">
          Gagal memuat aset. <button type="button" className="underline" disabled={disabled}
            onClick={() => setRetry(number => number + 1)}>Coba lagi</button>
        </div> : rows.length === 0 ? <p className="p-3 text-center text-xs text-muted-foreground">Tidak ada aset yang cocok.</p>
          : rows.map(asset => <button key={asset.id} type="button"
            disabled={disabled || selected.has(asset.id)}
            data-testid={itemTestId ? itemTestId(asset.id) : `${testId}-pilih-${asset.id}`}
            onClick={() => { if (getSatkerAktif() === satker) onPilih(asset); }}
            className="w-full px-2.5 py-2 text-left hover:bg-muted disabled:opacity-50">
            <span className="block truncate text-xs font-semibold text-foreground">{asset.asset_name || "—"}</span>
            <span className="block text-[10px] font-mono text-muted-foreground">
              {asset.asset_code} · NUP {asset.NUP ?? "—"}{selected.has(asset.id) ? " · Dipilih" : ""}
            </span>
          </button>)}
      </div>
      {current?.data && <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-2 py-1.5 text-[11px] text-muted-foreground">
        <span role="status">{total ? (page - 1) * PAGE_SIZE + 1 : 0}–{Math.min(page * PAGE_SIZE, total)} dari {total} aset</span>
        <div className="flex items-center gap-1">
          <button type="button" aria-label="Halaman aset sebelumnya" className="h-7 w-7 rounded border border-border disabled:opacity-40"
            disabled={disabled || page <= 1} onClick={() => setPagination({ key: queryKey, page: page - 1 })}>
            <ChevronLeft className="mx-auto h-3.5 w-3.5" />
          </button>
          <span>{page}/{pages}</span>
          <button type="button" aria-label="Halaman aset berikutnya" className="h-7 w-7 rounded border border-border disabled:opacity-40"
            disabled={disabled || page >= pages} onClick={() => setPagination({ key: queryKey, page: page + 1 })}>
            <ChevronRight className="mx-auto h-3.5 w-3.5" />
          </button>
        </div>
      </div>}
    </div>}
  </div>;
}
