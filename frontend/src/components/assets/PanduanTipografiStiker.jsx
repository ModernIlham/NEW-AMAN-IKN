import React, { useEffect, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const angka = (n) => Number(n).toLocaleString("id-ID", { maximumFractionDigits: 2 });

export default function PanduanTipografiStiker({ aktif, kertas, ukuran }) {
  const [terbuka, setTerbuka] = useState(false);
  const [hasil, setHasil] = useState(null);
  const [percobaan, setPercobaan] = useState(0);
  useEffect(() => {
    if (!aktif || !terbuka) return undefined;
    let batal = false;
    setHasil(null);
    axios.get(`${API}/stiker/tipografi`, { params: { kertas } })
      .then(r => {
        if (r.data?.kertas !== kertas || !Array.isArray(r.data?.peran) || !Array.isArray(r.data?.ukuran)) {
          throw new Error("Spesifikasi font tidak valid");
        }
        if (!batal) setHasil({ kertas, data: r.data });
      })
      .catch(() => { if (!batal) setHasil({ kertas, gagal: true }); });
    return () => { batal = true; };
  }, [aktif, terbuka, kertas, percobaan]);

  // Kertas baru tidak boleh sempat menampilkan angka milik kertas sebelumnya.
  const data = hasil?.kertas === kertas ? hasil.data : null;
  const gagal = hasil?.kertas === kertas && hasil.gagal;
  const pilihan = (data?.ukuran || []).filter(u => ukuran === "per_aset" || u.kode === ukuran);

  return (
    <details onToggle={e => setTerbuka(e.currentTarget.open)} data-testid="stiker-tipografi"
      className="rounded-lg border border-border bg-muted/30 text-[11px] text-foreground">
      <summary className="min-h-[44px] px-2 py-3 cursor-pointer rounded-lg hover:bg-muted focus-visible:outline focus-visible:outline-2"
        data-testid="stiker-tipografi-buka">Font dan ukuran teks</summary>
      <div className="px-2 pb-2 space-y-2" aria-live="polite">
        {!data && !gagal && <p className="text-muted-foreground">Memuat ukuran teks untuk {kertas}…</p>}
        {gagal && <div role="alert">
          <p>Panduan font gagal dimuat. Pembuatan PDF tetap dapat dicoba.</p>
          <Button variant="outline" className="min-h-[44px] mt-1 text-xs" onClick={() => setPercobaan(n => n + 1)}
            data-testid="stiker-tipografi-coba-lagi">Coba lagi</Button>
        </div>}
        {data && <>
          <p><strong>{data.font_tebal}</strong> untuk judul, kode barang, NUP, dan nama barang.
            Keterangan lainnya memakai {data.font_biasa} biasa.</p>
          <table className="w-full text-left" data-testid="stiker-tipografi-tabel">
            <caption className="text-left text-muted-foreground mb-1">Ukuran dasar huruf (pt) · kertas {kertas}</caption>
            <thead><tr className="border-b border-border">
              <th scope="col" className="py-1 pr-2">Bagian</th>
              {pilihan.map(u => <th scope="col" className="py-1 px-1 text-right" key={u.kode}>{u.nama}</th>)}
            </tr></thead>
            <tbody>{data.peran.map(p => <tr key={p.kode} className="border-b border-border/60">
              <th scope="row" className={`py-1 pr-2 ${p.tebal ? "font-bold" : "font-normal"}`}>{p.nama}</th>
              {pilihan.map(u => <td className="py-1 px-1 text-right tabular-nums" key={u.kode}>{angka(u.font_pt[p.kode])}</td>)}
            </tr>)}</tbody>
          </table>
          <p className="text-muted-foreground" data-testid="stiker-tipografi-dimensi">
            Dimensi aktual: {pilihan.map(u => `${u.nama} ${angka(u.lebar_mm)} × ${angka(u.tinggi_mm)} mm`).join("; ")}.
          </p>
          <p className="text-muted-foreground">Angka ini sebelum penyesuaian teks panjang: judul/kode dapat mengecil;
            nama barang maksimal tiga baris lalu elipsis. Cetak 100% / Ukuran aktual, bukan Sesuaikan halaman.
            Gunakan stiker contoh berukuran untuk mengecek hasil dengan penggaris.</p>
        </>}
      </div>
    </details>
  );
}
