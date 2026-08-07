import React, { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";

/**
 * useTransitionDialog — pengganti rantai `window.prompt` untuk isian
 * transisi status/aksi kecil (audit G5 #1): satu Dialog ber-field
 * (text/date/textarea/select) dengan validasi wajib, ramah mobile & dark mode.
 *
 * Pakai (pola useConfirm):
 *   const { minta, transitionDialog } = useTransitionDialog();
 *   const v = await minta({
 *     judul: "Tandai Selesai", deskripsi: "…",
 *     fields: [
 *       { key: "nomor", label: "Nomor dokumen", type: "text" },
 *       { key: "tanggal", label: "Tanggal", type: "date" },
 *       { key: "catatan", label: "Catatan", type: "textarea", wajib: true },
 *       { key: "pejabat", label: "PPK", type: "select", default: "auto",
 *         opsi: [{ id: "auto", label: "Otomatis" }, …], petunjuk: "…" },
 *     ],
 *     confirmLabel: "Simpan",
 *   });
 *   if (v === null) return;            // batal
 *   … v.nomor, v.tanggal, v.catatan, v.pejabat …
 * Render {transitionDialog} sekali di akhir halaman.
 *
 * `select` memakai <select> NATIVE, bukan Radix Select. Dua alasan: daftar
 * pilihan di sini selalu pendek dan terkurasi, dan roda pemilih bawaan sistem
 * jauh lebih enak dipakai satu tangan di lapangan daripada popup melayang.
 * Nilai kosong ("") adalah pilihan SAH — dipakai untuk "kosongkan penetapan" —
 * jadi field select yang `wajib` divalidasi terpisah dari field teks.
 */
export function useTransitionDialog() {
  const [state, setState] = useState({ open: false, opsi: {}, nilai: {} });
  const resolverRef = useRef(null);

  const minta = useCallback((opsi = {}) => {
    return new Promise((resolve) => {
      resolverRef.current = resolve;
      const nilai = {};
      (opsi.fields || []).forEach((f) => { nilai[f.key] = f.default ?? ""; });
      setState({ open: true, opsi, nilai });
    });
  }, []);

  const tutup = useCallback((hasil) => {
    setState((s) => ({ ...s, open: false }));
    const resolve = resolverRef.current;
    resolverRef.current = null;
    resolve?.(hasil);
  }, []);

  const simpan = useCallback(() => {
    const { opsi, nilai } = state;
    // Field `select` DIKECUALIKAN dari cek "wajib diisi": pilihan bernilai
    // kosong di sana punya arti tersendiri (mis. "Kosongkan penetapan"), dan
    // memperlakukannya sebagai isian kosong akan memblokir aksi yang sah.
    const kurang = (opsi.fields || []).find(
      (f) => f.wajib && f.type !== "select"
             && !String(nilai[f.key] ?? "").trim());
    if (kurang) { toast.error(`${kurang.label} wajib diisi`); return; }
    tutup({ ...nilai });
  }, [state, tutup]);

  const transitionDialog = (
    <Dialog open={state.open} onOpenChange={(o) => { if (!o) tutup(null); }}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{state.opsi.judul || "Isian"}</DialogTitle>
          {state.opsi.deskripsi && (
            <DialogDescription className="text-xs">{state.opsi.deskripsi}</DialogDescription>
          )}
        </DialogHeader>
        <div className="space-y-2.5">
          {(state.opsi.fields || []).map((f) => (
            <div key={f.key}>
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor={`trx-${f.key}`}>
                {f.label}{f.wajib ? " *" : ""}
              </label>
              {f.type === "textarea" ? (
                <Textarea id={`trx-${f.key}`} rows={3} value={state.nilai[f.key] ?? ""}
                  placeholder={f.placeholder || ""}
                  onChange={(e) => setState((s) => ({ ...s, nilai: { ...s.nilai, [f.key]: e.target.value } }))}
                  data-testid={`transisi-${f.key}`} />
              ) : f.type === "select" ? (
                <select id={`trx-${f.key}`} value={state.nilai[f.key] ?? ""}
                  onChange={(e) => setState((s) => ({ ...s, nilai: { ...s.nilai, [f.key]: e.target.value } }))}
                  className="w-full h-9 rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  data-testid={`transisi-${f.key}`}>
                  {(f.opsi || []).map((o) => (
                    <option key={o.id} value={o.id}>{o.label}</option>
                  ))}
                </select>
              ) : (
                <Input id={`trx-${f.key}`} type={f.type === "date" ? "date" : "text"}
                  value={state.nilai[f.key] ?? ""} placeholder={f.placeholder || ""}
                  onChange={(e) => setState((s) => ({ ...s, nilai: { ...s.nilai, [f.key]: e.target.value } }))}
                  data-testid={`transisi-${f.key}`} />
              )}
              {f.petunjuk && (
                <p className="text-[10px] text-muted-foreground mt-1">{f.petunjuk}</p>
              )}
            </div>
          ))}
        </div>
        <div className="flex flex-wrap justify-end gap-2 pt-1">
          <Button variant="outline" onClick={() => tutup(null)}>Batal</Button>
          <Button onClick={simpan} data-testid="transisi-simpan">
            {state.opsi.confirmLabel || "Simpan"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );

  return { minta, transitionDialog };
}
