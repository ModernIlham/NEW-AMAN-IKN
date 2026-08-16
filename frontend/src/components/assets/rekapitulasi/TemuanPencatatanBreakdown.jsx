import React from "react";
import { ClipboardCheck } from "lucide-react";

const fmtRp = (val) => {
  try { return `Rp ${Math.round(val).toLocaleString("id-ID")}`; }
  catch { return "Rp 0"; }
};

/**
 * Rekap temuan pencatatan lapangan.
 *
 * Dihitung dari SELURUH aset kegiatan — bukan hanya yang tidak ditemukan.
 * Itu inti field `temuan_pencatatan`: cacat pencatatan paling sering dijumpai
 * pada barang yang JUSTRU KETEMU (kode tak sesuai fisik, stiker tertempel di
 * barang lain). Sebelum kartu ini ada, satu-satunya cara melihatnya adalah
 * membuka ekspor Excel dan menyaring sendiri.
 *
 * Panel disembunyikan bila belum ada satu pun temuan — layar rekapitulasi
 * sudah padat, dan kartu kosong hanya menambah derau.
 */
export default function TemuanPencatatanBreakdown({ temuan }) {
  if (!temuan || (temuan.count || 0) <= 0) return null;

  const jenis = Object.entries(temuan.per_jenis || {})
    .filter(([, v]) => (v?.count || 0) > 0);

  return (
    <div
      className="bg-sky-50/50 dark:bg-sky-900/20 border border-sky-100 dark:border-sky-800 rounded-lg p-2.5 space-y-2"
      data-testid="temuan-pencatatan-breakdown"
    >
      <p className="text-xs font-medium text-sky-700 dark:text-sky-400 flex items-center gap-1.5">
        <ClipboardCheck className="w-3.5 h-3.5" /> Temuan Pencatatan Lapangan
      </p>

      <div className="bg-card rounded p-2 border border-sky-100 dark:border-sky-800">
        <p className="text-[10px] text-sky-600 dark:text-sky-400 font-medium">
          Total BMN dengan temuan
        </p>
        <p className="text-sm font-bold text-sky-800 dark:text-sky-200">
          {temuan.count} NUP
        </p>
        <p className="text-[10px] text-sky-500 dark:text-sky-400">
          {fmtRp(temuan.value || 0)} · termasuk BMN yang ditemukan
        </p>
      </div>

      <div className="space-y-1">
        {jenis.map(([nama, v]) => (
          <div
            key={nama}
            className="flex items-center justify-between text-[10px] bg-card rounded px-2 py-1 border border-sky-50 dark:border-sky-900"
          >
            <span className="text-muted-foreground truncate max-w-[58%]">{nama}</span>
            <span className="text-sky-700 dark:text-sky-400 font-medium">
              {v.count} NUP · {fmtRp(v.value)}
            </span>
          </div>
        ))}
      </div>

      <p className="text-[10px] text-muted-foreground leading-snug">
        Temuan ini bahan usul <strong>reklasifikasi</strong> dan perbaikan
        pelabelan — bukan penghapusan BMN.
      </p>
    </div>
  );
}
