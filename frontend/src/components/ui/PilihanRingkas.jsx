import React, { useId, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, Search, X } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/** Satu baris saat tertutup; pencarian tidak pernah mengubah nilai pilihan. */
export default function PilihanRingkas({ options = [], value = "", onChange, disabled = false,
  placeholder = "Pilih…", label = "Pilihan", testId = "pilihan-ringkas", emptyText = "Tidak ada pilihan yang sesuai.",
  emptyLabel = "Kosongkan pilihan", clearable = true, className = "" }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [aktif, setAktif] = useState(-1);
  const [batas, setBatas] = useState(100);
  const inputRef = useRef(null);
  const listId = useId();
  const selected = options.find(o => String(o.value) === String(value));
  const hasil = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("id");
    return options.filter(o => !q || [o.label, o.description, o.searchText, ...(Array.isArray(o.keywords) ? o.keywords : [o.keywords])]
      .filter(Boolean).join(" ").toLocaleLowerCase("id").includes(q));
  }, [options, query]);
  const tampak = hasil.slice(0, batas);
  const tampil = open && !disabled;
  const buka = next => { setOpen(next); setQuery(""); setAktif(-1); setBatas(100); };
  const pilih = option => {
    if (disabled || option?.disabled) return;
    onChange(String(option?.value ?? ""), option || null); buka(false);
  };
  const keyDown = event => {
    if (["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      const arah = event.key === "ArrowDown" ? 1 : -1;
      let next = aktif < 0 && arah === -1 ? 0 : aktif;
      for (let i = 0; i < tampak.length; i += 1) {
        next = (next + arah + tampak.length) % tampak.length;
        if (!tampak[next].disabled) { setAktif(next); document.getElementById(`${listId}-${next}`)?.scrollIntoView?.({ block: "nearest" }); break; }
      }
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (aktif >= 0 && tampak[aktif]) pilih(tampak[aktif]);
    }
  };
  return <Popover open={tampil} onOpenChange={buka}>
    <div className={`flex min-w-0 items-stretch gap-1 ${className}`}>
      <PopoverTrigger asChild><button type="button" data-testid={testId} aria-label={label} disabled={disabled}
        className="flex min-h-[44px] w-full min-w-0 items-center justify-between gap-2 rounded-lg border border-input bg-background px-3 py-2 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50">
        <span className={`min-w-0 truncate ${selected ? "" : "text-muted-foreground"}`}>{selected?.label || (value ? "Pilihan tertaut tidak tersedia — periksa kembali" : placeholder)}</span><ChevronDown size={16} className="shrink-0 text-muted-foreground" aria-hidden="true" />
      </button></PopoverTrigger>
      {clearable && value && <button type="button" disabled={disabled} data-testid={`${testId}-clear`} aria-label={`Kosongkan ${label.toLocaleLowerCase("id")}`} onClick={() => pilih(options.find(o => String(o.value) === "") || null)} className="inline-flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center rounded-lg border border-input text-muted-foreground hover:bg-muted disabled:opacity-50"><X size={16} aria-hidden="true" /></button>}
    </div>
    <PopoverContent align="start" sideOffset={4} collisionPadding={8} className="z-[160] flex max-h-[var(--radix-popover-content-available-height)] w-[var(--radix-popover-trigger-width)] min-w-[220px] max-w-[calc(100vw-32px)] flex-col overflow-hidden p-0" data-testid={`${testId}-panel`} onOpenAutoFocus={event => { event.preventDefault(); inputRef.current?.focus(); }}>
      <div className="relative shrink-0 border-b p-2"><Search size={16} aria-hidden="true" className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-muted-foreground" /><input ref={inputRef} role="combobox" aria-label={`Cari ${label.toLocaleLowerCase("id")}`} aria-autocomplete="list" aria-expanded={tampil} aria-controls={listId} aria-activedescendant={aktif >= 0 ? `${listId}-${aktif}` : undefined}
        data-testid={`${testId}-search`} value={query} onKeyDown={keyDown} onChange={e => { setQuery(e.target.value); setAktif(-1); setBatas(100); }} placeholder="Ketik untuk mencari…" autoComplete="off"
        className="min-h-[44px] w-full min-w-0 rounded-md border border-input bg-background py-2 pl-9 pr-3 text-sm" /></div>
      <div id={listId} role="listbox" aria-label={label} className="min-h-0 max-h-[min(45vh,320px)] overflow-y-auto overscroll-contain p-1">
        {clearable && !options.some(o => String(o.value) === "") && <button type="button" role="option" aria-selected={!value} tabIndex={-1} data-testid={`${testId}-option-empty`} onClick={() => pilih(null)} className="min-h-[44px] w-full rounded-md px-3 py-2 text-left text-sm text-muted-foreground hover:bg-muted">{emptyLabel}</button>}
        {tampak.map((o, i) => <button type="button" role="option" aria-selected={String(value) === String(o.value)} disabled={o.disabled} tabIndex={-1} id={`${listId}-${i}`} key={o.value} data-testid={`${testId}-option-${o.value}`} onClick={() => pilih(o)}
          className={`flex min-h-[44px] w-full min-w-0 items-start gap-2 rounded-md px-2 py-2 text-left text-sm disabled:opacity-50 ${i === aktif ? "bg-accent text-accent-foreground" : "hover:bg-muted"}`}>
          <Check size={16} aria-hidden="true" className={`mt-0.5 shrink-0 ${String(value) === String(o.value) ? "text-primary" : "opacity-0"}`} /><span className="min-w-0"><span className="block break-words font-medium">{o.label}</span>{o.description && <span className="mt-0.5 block break-words text-xs text-muted-foreground">{o.description}</span>}</span>
        </button>)}
        {!hasil.length && <p role="status" className="px-3 py-4 text-sm text-muted-foreground">{emptyText}</p>}
      </div>
      {hasil.length > tampak.length && <button type="button" data-testid={`${testId}-more`} className="min-h-[44px] w-full shrink-0 border-t px-3 py-2 text-sm text-primary" onClick={() => setBatas(n => n + 100)}>Tampilkan lebih banyak ({tampak.length} dari {hasil.length})</button>}
    </PopoverContent>
  </Popover>;
}
