import React, { useEffect, useMemo, useRef, useState } from "react";
import { Search, X, Upload, MapPin } from "lucide-react";
import { bacaMarkerPin, cariIkonPin, KATEGORI_PIN, opsiPinDesain, PIN_BAWAAN, siapkanIkonPin } from "../../lib/markerPin";

const kontrol = "w-full min-w-0 rounded-md border border-border bg-background text-foreground text-xs px-2 py-2";
const tombol = "min-h-[44px] px-2 py-1.5 rounded-md border text-xs hover:bg-muted transition-colors";

export default function MarkerPinEditor({ value = "", onChange, onBusyChange, disabled = false, scopeKey = "", color = "#64748b" }) {
  const d = useMemo(() => bacaMarkerPin(value), [value]);
  const [q, setQ] = useState("");
  const [kategori, setKategori] = useState("Semua");
  const [galat, setGalat] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);
  const urutan = useRef(0);
  // Hasil decode lambat tak boleh menulis ke aset berikutnya/reset/jenis lain.
  useEffect(() => { urutan.current += 1; setBusy(false); setGalat(""); }, [scopeKey]);
  useEffect(() => () => { urutan.current += 1; }, []);
  useEffect(() => { onBusyChange?.(busy); return () => onBusyChange?.(false); }, [busy, onBusyChange]);
  const ubah = (patch) => { urutan.current += 1; setBusy(false); setGalat(""); onChange(JSON.stringify({ ...(d || PIN_BAWAAN), ...patch })); };
  const pilihan = cariIkonPin(q, kategori);
  const preview = opsiPinDesain(value, { color });
  const unggah = async (e) => {
    const file = e.target.files?.[0]; e.target.value = "";
    if (!file) return;
    const tiket = ++urutan.current;
    setBusy(true); setGalat("");
    try {
      const image = await siapkanIkonPin(file);
      if (tiket === urutan.current) onChange(JSON.stringify({ ...(d || PIN_BAWAAN), mode: "custom", image }));
    } catch (err) { if (tiket === urutan.current) setGalat(err.message); }
    finally { if (tiket === urutan.current) setBusy(false); }
  };
  return <fieldset disabled={disabled} className="min-w-0 space-y-3 rounded-lg border border-border bg-card p-3" data-testid="marker-pin-editor">
    <legend className="px-1 text-xs font-semibold">Desain marker pin</legend>
    <div className="flex items-center gap-3">
      <div className="h-16 w-16 shrink-0 rounded-lg bg-muted flex items-center justify-center" aria-label="Pratinjau marker">
        {preview ? <div data-testid="marker-pin-preview" dangerouslySetInnerHTML={{ __html: preview.html }} /> : <MapPin className="w-8 h-8" style={{ color }} />}
      </div>
      <p className="text-[11px] text-muted-foreground">Berlaku pada gaya Pin di peta aset dan peta dibagikan. Warna luar tetap mengikuti status inventarisasi.</p>
    </div>
    <div className="grid grid-cols-2 gap-2" role="group" aria-label="Isi tengah pin">
      {[["", "Polos"], ["icon", "Ikon"], ["text", "Huruf / angka"], ["custom", "Ikon custom"]].map(([mode, label]) => <button key={mode} type="button" data-testid={`marker-mode-${mode || "plain"}`} aria-pressed={(d?.mode || "") === mode}
        className={`${tombol} ${(d?.mode || "") === mode ? "border-primary bg-primary/10 text-primary" : "border-border"}`}
        onClick={() => {
          if (!mode) { urutan.current += 1; setBusy(false); setGalat(""); onChange(""); }
          else if (mode === "custom") fileRef.current?.click();
          else ubah({ mode, image: "" });
        }}>{mode === "custom" && busy ? "Menyiapkan…" : label}</button>)}
    </div>
    <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" aria-label="Unggah ikon marker" data-testid="marker-upload" onChange={unggah} />
    <p className="text-[10px] text-muted-foreground">Custom: PNG/JPEG/WebP ≤2 MB, maksimal 4096×4096. Otomatis menjadi PNG transparan 64×64 dengan ruang tepi; hasil ≤10 KB. Jangan unggah data pribadi: ikon ikut peta dibagikan.</p>
    {galat && <p role="alert" className="text-xs text-destructive">{galat}</p>}
    {d?.mode === "custom" && <button type="button" className={`${tombol} w-full border-border flex gap-2 items-center justify-center`} onClick={() => fileRef.current?.click()} data-testid="marker-reupload"><Upload className="w-4 h-4" />Ganti ikon custom</button>}
    {d?.mode === "text" && <label className="block text-xs space-y-1">Huruf / angka (1–3 karakter)
      <input data-testid="marker-text" aria-label="Huruf marker" className={kontrol} maxLength={3} value={d.text} onChange={(e) => { const text = e.target.value.replace(/[^A-Za-z0-9]/g, ""); ubah({ text: text || "A" }); }} />
    </label>}
    {d?.mode === "icon" && <div className="space-y-2">
      <label className="block text-xs space-y-1">Kategori ikon<select className={kontrol} value={kategori} onChange={(e) => setKategori(e.target.value)} data-testid="marker-category"><option>Semua</option>{KATEGORI_PIN.map((k) => <option key={k}>{k}</option>)}</select></label>
      <div className="relative min-w-0">
        <Search className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input type="text" className={`${kontrol} !pl-8 !pr-11`} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari ikon…" aria-label="Cari ikon marker" data-testid="marker-search" />
        {q && <button type="button" className="absolute right-0 top-0 h-full w-10 min-w-0 min-h-0 flex items-center justify-center" aria-label="Hapus pencarian ikon" onClick={() => setQ("")}><X className="w-4 h-4" /></button>}
      </div>
      <div className="grid grid-cols-3 gap-1.5 max-h-56 overflow-y-auto p-1" role="group" aria-label="Pilihan ikon">
        {pilihan.map(({ id, nama, Icon }) => <button type="button" key={id} title={nama} aria-label={nama} aria-pressed={d.icon === id} data-testid={`marker-icon-${id}`} onClick={() => ubah({ icon: id })}
          className={`${tombol} min-w-0 flex flex-col items-center gap-1 ${d.icon === id ? "border-primary bg-primary/10 text-primary" : "border-border"}`}><Icon className="w-5 h-5 shrink-0" /><span className="text-[10px] leading-tight break-words">{nama}</span></button>)}
      </div>
      {!pilihan.length && <p className="text-xs text-muted-foreground">Ikon tidak ditemukan. Ubah kata pencarian atau kategori.</p>}
    </div>}
    {d && <div className="space-y-2 border-t border-border pt-3">
      <label className="flex gap-2 items-center text-xs min-h-[44px]"><input type="checkbox" checked={d.circle} onChange={(e) => ubah({ circle: e.target.checked })} data-testid="marker-circle" />Isi lingkaran di belakang ikon</label>
      <div className="grid grid-cols-2 gap-2">
        {[["iconColor", "Warna ikon / huruf"], ["circleColor", "Warna lingkaran"], ["strokeColor", "Warna garis tepi"]].map(([key, label]) => <label key={key} className="min-w-0 text-[11px] space-y-1">{label}<input type="color" aria-label={label} data-testid={`marker-${key}`} className="block w-full h-11 rounded border border-border bg-background" value={d[key]} disabled={(key === "iconColor" && d.mode === "custom") || (key === "circleColor" && !d.circle)} onChange={(e) => ubah({ [key]: e.target.value })} /></label>)}
        <label className="min-w-0 text-[11px] space-y-1">Ketebalan garis<select className={`${kontrol} min-h-[44px]`} aria-label="Ketebalan garis marker" data-testid="marker-stroke" value={d.strokeWidth} onChange={(e) => ubah({ strokeWidth: Number(e.target.value) })}>{[0, 1, 2, 3].map((n) => <option key={n} value={n}>{n ? `${n} px` : "Tanpa garis"}</option>)}</select></label>
      </div>
    </div>}
  </fieldset>;
}
