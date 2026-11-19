import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Check, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import PilihKelompok from "@/components/pegawai/PilihKelompok";
import CariOrangLuar from "@/components/pegawai/CariOrangLuar";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Pemilih pengguna aset dari SEMUA kelompok: Internal (Master Pegawai satker)
 * + Instansi Eksternal (Pusat/Daerah) + Pihak Ketiga — perilaku sama dengan
 * pemilih di form aset, dikemas agar bisa dipakai layar lain (mis. Ubah
 * Massal, yang dulu hanya punya tombol "Orang luar").
 *
 * Internal: `/pegawai` dimuat SEKALI saat pemilih pertama dibuka; pencarian
 * nama/NIP di klien (maks 40 baris). Pegawai berstatus meninggal tidak dapat
 * dipilih — almarhum tak mungkin menerima serah terima (aturan form aset).
 * Offline → pesan, pengguna tetap bisa mengetik manual di kolomnya.
 *
 * `onPilih(orang)` menerima { nama, nip, jabatan?, ... }.
 */
export default function TombolPilihPengguna({ onPilih, terpilihNip = "", testId = "pilih-pengguna",
  disabled = false }) {
  const [buka, setBuka] = useState(false);
  const [kelompok, setKelompok] = useState("internal");
  const [tataran, setTataran] = useState("pusat");
  const [q, setQ] = useState("");
  const [semua, setSemua] = useState(undefined); // undefined memuat · null gagal · array

  useEffect(() => {
    if (!buka || kelompok !== "internal" || semua !== undefined) return undefined;
    let batal = false;
    axios.get(`${API}/pegawai`)
      .then((r) => { if (!batal) setSemua(r.data?.items || []); })
      .catch(() => { if (!batal) setSemua(null); });
    return () => { batal = true; };
  }, [buka, kelompok, semua]);

  const hasil = useMemo(() => {
    if (!Array.isArray(semua)) return semua;
    const hidup = semua.filter((p) => String(p?.status || "") !== "meninggal");
    const kata = q.trim().toLowerCase();
    const cocok = !kata ? hidup : hidup.filter((p) =>
      [p.nama, p.nip].some((v) => String(v || "").toLowerCase().includes(kata)));
    return cocok.slice(0, 40);
  }, [semua, q]);

  const pilih = (p) => { setBuka(false); setQ(""); onPilih(p); };

  return (
    <Popover open={buka} onOpenChange={setBuka}>
      <PopoverTrigger asChild>
        <button type="button" disabled={disabled}
          title="Pilih pengguna dari Master Pegawai, instansi eksternal, atau pihak ketiga"
          aria-label="Pilih pengguna — pegawai internal, instansi eksternal, atau pihak ketiga"
          className="inline-flex items-center gap-1 shrink-0 self-stretch min-h-9 min-w-0 rounded-md border border-input bg-card px-2.5 text-xs hover:bg-muted disabled:opacity-50"
          data-testid={testId}>
          <Search className="w-3.5 h-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">Pilih</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[calc(100vw-2rem)] max-w-sm p-2 space-y-2">
        <PilihKelompok kelompok={kelompok} tataran={tataran} awalanTestId={testId}
          onKelompok={setKelompok} onTataran={setTataran} />
        {kelompok !== "internal" ? (
          <CariOrangLuar kelompok={kelompok} tataran={tataran} testId={`${testId}-luar`}
            terpilihNip={terpilihNip} onPilih={pilih} />
        ) : (
          <div className="space-y-2">
            <Input placeholder="Cari nama / NIP pegawai…" value={q} onChange={(e) => setQ(e.target.value)}
              aria-label="Cari pegawai internal" className="h-8" data-testid={`${testId}-cari`} />
            <div className="max-h-56 overflow-y-auto" role="listbox" aria-label="Pegawai internal">
              {hasil === null ? (
                <p className="text-xs text-center text-muted-foreground py-3">Master Pegawai tak tersedia (offline). Ketik manual.</p>
              ) : hasil === undefined ? (
                <p className="text-xs text-center text-muted-foreground py-3">Memuat…</p>
              ) : hasil.length === 0 ? (
                <p className="text-xs text-center text-muted-foreground py-3">{q.trim() ? "Tidak ditemukan" : "Belum ada pegawai di master"}</p>
              ) : hasil.map((p) => (
                <button type="button" key={p.id || p.nip} role="option"
                  aria-selected={!!terpilihNip && p.nip === terpilihNip} onClick={() => pilih(p)}
                  className="w-full text-left px-2 py-1.5 rounded hover:bg-muted flex items-start gap-2 min-w-0 min-h-0"
                  data-testid={`${testId}-opt-${p.nip || p.id}`}>
                  <span className="flex-1 min-w-0">
                    <span className="block text-xs text-foreground/90 break-words">{p.nama}</span>
                    <span className="block text-[10px] text-muted-foreground font-mono break-words">
                      {p.nip || "tanpa NIP"}{p.jabatan ? ` · ${p.jabatan}` : ""}{p.unit_kerja ? ` · ${p.unit_kerja}` : ""}
                    </span>
                  </span>
                  {terpilihNip && p.nip === terpilihNip && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" aria-hidden="true" />}
                </button>
              ))}
            </div>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
