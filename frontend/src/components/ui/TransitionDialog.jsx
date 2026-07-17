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
 * (text/date/textarea) dengan validasi wajib, ramah mobile & dark mode.
 *
 * Pakai (pola useConfirm):
 *   const { minta, transitionDialog } = useTransitionDialog();
 *   const v = await minta({
 *     judul: "Tandai Selesai", deskripsi: "…",
 *     fields: [
 *       { key: "nomor", label: "Nomor dokumen", type: "text" },
 *       { key: "tanggal", label: "Tanggal", type: "date" },
 *       { key: "catatan", label: "Catatan", type: "textarea", wajib: true },
 *     ],
 *     confirmLabel: "Simpan",
 *   });
 *   if (v === null) return;            // batal
 *   … v.nomor, v.tanggal, v.catatan …
 * Render {transitionDialog} sekali di akhir halaman.
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
    const kurang = (opsi.fields || []).find(
      (f) => f.wajib && !String(nilai[f.key] ?? "").trim());
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
              ) : (
                <Input id={`trx-${f.key}`} type={f.type === "date" ? "date" : "text"}
                  value={state.nilai[f.key] ?? ""} placeholder={f.placeholder || ""}
                  onChange={(e) => setState((s) => ({ ...s, nilai: { ...s.nilai, [f.key]: e.target.value } }))}
                  data-testid={`transisi-${f.key}`} />
              )}
            </div>
          ))}
        </div>
        <div className="flex justify-end gap-2 pt-1">
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
