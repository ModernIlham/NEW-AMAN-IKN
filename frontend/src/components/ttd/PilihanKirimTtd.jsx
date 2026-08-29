import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Loader2 } from "lucide-react";
import {
  MODE_TTD, PILIHAN_BAWAAN, SIFAT_URGENSI, bersihkanPilihan,
} from "@/lib/opsiKirimTtd";

/**
 * Dialog pilihan sebelum dokumen dilempar ke e-sign.
 *
 * Permintaan pemilik: urutan teken (paralel/berurutan) dan sifat urgensi
 * dapat dipilih saat menekan "Kirim TTD". Sebelumnya keduanya dipatok
 * diam-diam ("paralel", "biasa"), sehingga pengirim tak pernah bisa
 * menyatakan bahwa dokumen ini harus berurutan atau mendesak.
 *
 * `<select>` NATIVE, bukan Radix Select: itu konvensi repo ini untuk pemilih
 * di dalam dialog (portal Radix pernah tenggelam di balik overlay), dan ia
 * pula yang membuat `select.options` bisa diuji apa adanya.
 */
export default function PilihanKirimTtd({
  terbuka, onTutup, onKirim, mengirim = false, judul = "",
}) {
  const [pilihan, setPilihan] = useState(PILIHAN_BAWAAN);
  const modeAktif = MODE_TTD.find((m) => m.nilai === pilihan.mode);

  return (
    <Dialog open={!!terbuka} onOpenChange={(o) => { if (!o) onTutup?.(); }}>
      <DialogContent className="max-w-md" data-testid="pilihan-kirim-ttd">
        <DialogHeader>
          <DialogTitle className="text-base">Kirim ke TTD elektronik</DialogTitle>
          <DialogDescription className="text-[11px]">
            {judul || "Tentukan urutan teken dan seberapa mendesak dokumen ini."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-muted-foreground block"
              htmlFor="ttd-mode">Urutan tanda tangan</label>
            <select id="ttd-mode" value={pilihan.mode}
              onChange={(e) => setPilihan((p) => ({ ...p, mode: e.target.value }))}
              className="w-full h-9 rounded-lg border border-border bg-background px-2 text-sm"
              data-testid="ttd-pilih-mode">
              {MODE_TTD.map((m) => (
                <option key={m.nilai} value={m.nilai}>{m.label}</option>
              ))}
            </select>
            {/* Arti pilihannya ditulis, bukan disembunyikan di balik istilah:
                "paralel" dan "berurutan" tak berarti apa-apa bagi orang yang
                baru pertama kali mengirimkan dokumen. */}
            {modeAktif && (
              <p className="text-[11px] text-muted-foreground leading-snug"
                data-testid="ttd-arti-mode">{modeAktif.arti}</p>
            )}
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-medium text-muted-foreground block"
              htmlFor="ttd-urgensi">Sifat urgensi</label>
            <select id="ttd-urgensi" value={pilihan.sifat_urgensi}
              onChange={(e) => setPilihan(
                (p) => ({ ...p, sifat_urgensi: e.target.value }))}
              className="w-full h-9 rounded-lg border border-border bg-background px-2 text-sm"
              data-testid="ttd-pilih-urgensi">
              {SIFAT_URGENSI.map((u) => (
                <option key={u.nilai} value={u.nilai}>{u.label}</option>
              ))}
            </select>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-2">
          <Button variant="outline" size="sm" className="h-9 text-xs"
            disabled={mengirim} onClick={() => onTutup?.()}>Batal</Button>
          <Button size="sm" className="h-9 text-xs" disabled={mengirim}
            onClick={() => onKirim?.(bersihkanPilihan(pilihan))}
            data-testid="ttd-kirim-lanjut">
            {mengirim ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
            Kirim tautan
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
