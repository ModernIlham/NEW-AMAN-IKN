import React from "react";
import { PenLine } from "lucide-react";

import {
  labelBawaan, labelPejabat, pejabatSatker, setelSlot,
} from "@/lib/penandatanganSlot";

/**
 * Tiga pemilih penanda tangan (satu per slot dokumen) — dipakai DUA layar:
 * Master Satker (setelan tetap) dan penerbitan LPB gabungan (penimpa sekali
 * pakai). Satu komponen agar keduanya tak pernah berbeda perilaku.
 *
 * Props:
 *  - `slot`      daftar slot dari `GET /pejabat/referensi` (jangan disalin
 *                statis di layar — backend adalah sumbernya)
 *  - `pejabat`   daftar pejabat mentah; disaring ke satker `kodeSatker`
 *  - `nilai`     peta slot→id pejabat yang sedang dipilih
 *  - `bawaan`    lapis di bawahnya (setelan satker) untuk menerangkan opsi ""
 *  - `onUbah`    menerima peta BARU yang sudah bersih
 */
export default function PemilihPenandatangan({
  slot = [], pejabat = [], nilai = {}, bawaan = null, kodeSatker = "",
  onUbah, judul = "Penanda tangan dokumen", keterangan = "",
  testIdPrefix = "ttd-slot",
}) {
  const daftar = pejabatSatker(pejabat, kodeSatker);
  return (
    <div className="rounded-xl border border-border p-2.5 space-y-2"
      data-testid={`${testIdPrefix}-panel`}>
      <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
        <PenLine className="w-3.5 h-3.5" />{judul}
      </p>
      {keterangan && (
        <p className="text-[10px] text-muted-foreground">{keterangan}</p>
      )}
      {slot.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">
          Daftar slot tanda tangan belum termuat.
        </p>
      ) : daftar.length === 0 ? (
        // Dropdown kosong tanpa penjelasan membuat operator mengira fiturnya
        // rusak, padahal registry pejabatnya yang masih kosong.
        <p className="text-[11px] text-amber-600 dark:text-amber-400">
          Belum ada pejabat terdaftar untuk satker ini — isi Referensi Pejabat
          lebih dulu.
        </p>
      ) : (
        slot.map((s) => (
          <div key={s.kunci}>
            <label className="text-xs text-muted-foreground" htmlFor={`${testIdPrefix}-${s.kunci}`}>
              {s.label}
            </label>
            <select id={`${testIdPrefix}-${s.kunci}`}
              value={nilai?.[s.kunci] || ""}
              onChange={(e) => onUbah?.(setelSlot(nilai, s.kunci, e.target.value))}
              className="w-full h-9 mt-0.5 rounded-md border border-input bg-background px-2 text-sm"
              data-testid={`${testIdPrefix}-${s.kunci}`}>
              <option value="">{labelBawaan(s, bawaan, daftar)}</option>
              {daftar.map((p) => (
                <option key={p.id} value={p.id}>{labelPejabat(p)}</option>
              ))}
            </select>
            {s.arti && (
              <p className="text-[10px] text-muted-foreground mt-0.5">{s.arti}</p>
            )}
          </div>
        ))
      )}
    </div>
  );
}
