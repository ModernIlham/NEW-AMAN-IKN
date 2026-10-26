import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { authMediaUrl } from "@/lib/mediaUrl";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const JENIS = { scan_manual: "Scan tanda tangan manual / format lain", e_meterai: "Dokumen setelah e-meterai", dokumen_lengkap: "Dokumen akhir lengkap / pelengkap" };
const STATUS = { menunggu: "Menunggu pemeriksaan", sesuai: "Kelengkapan diperiksa — sesuai", tidak_sesuai: "Tidak sesuai — perlu dokumen baru" };

export default function DokumenAkhirBast({ bast, editable, onUpdated }) {
  const [unggah, setUnggah] = useState(null);
  const [periksa, setPeriksa] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [preview, setPreview] = useState("");
  const inputRef = useRef(null);
  const lock = useRef(false);
  const dokumen = bast.dokumen_akhir || [];
  const boleh = editable && !bast.direvisi_oleh && !bast.tt_dicabut;
  useEffect(() => {
    if (!unggah?.file) { setPreview(""); return undefined; }
    const url = URL.createObjectURL(unggah.file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [unggah?.file]);

  const ubahUnggah = patch => setUnggah(v => ({ ...v, ...patch, key: crypto.randomUUID() }));
  const ubahPeriksa = patch => setPeriksa(v => ({ ...v, ...patch, key: crypto.randomUUID() }));
  const simpan = async () => {
    if (lock.current || !boleh) return;
    if (unggah && (!unggah.file || unggah.catatan.trim().length < 5)) return;
    if (periksa && (!periksa.dibaca || !periksa.setuju || periksa.catatan.trim().length < 5)) return;
    if (!unggah && !periksa) return;
    const draft = unggah || periksa;
    lock.current = true; setSibuk(true);
    try {
      let payload; let path = `${API}/bast/${bast.id}/dokumen-akhir`;
      if (unggah) {
        payload = new FormData();
        payload.append("file", unggah.file);
        payload.append("jenis", unggah.jenis);
        payload.append("catatan", unggah.catatan.trim());
      } else {
        path += `/${periksa.id}/periksa`;
        payload = { status: periksa.status, sudah_diperiksa: true, catatan: periksa.catatan.trim() };
      }
      await axios.post(path, payload, { headers: {
        "If-Match": String(bast.dokumen_akhir_version || 1), "Idempotency-Key": draft.key,
      }, timeout: 30000 });
      toast.success(unggah ? "Dokumen akhir diarsipkan; menunggu pemeriksaan petugas" : "Hasil pemeriksaan dicatat; dokumen asli tetap utuh");
      setUnggah(null); setPeriksa(null);
      await onUpdated();
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === "string" ? e.response.data.detail : "Belum dapat memastikan hasil. Coba kembali dengan berkas dan isian yang sama.");
      if (e.response?.status === 409) await onUpdated();
    } finally { lock.current = false; setSibuk(false); }
  };
  const bukaDokumen = id => window.open(authMediaUrl(`${API}/bast/${bast.id}/dokumen-akhir/${id}`), "_blank", "noopener,noreferrer");

  return <section className="mt-3 min-w-0 rounded-lg border border-border bg-muted/20 p-3 space-y-2" data-testid={`bast-arsip-akhir-${bast.id}`}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h4 className="font-semibold">Dokumen akhir / bukti tambahan</h4>
      {boleh && <Button type="button" size="sm" variant="outline" className="min-h-[44px] text-xs" disabled={sibuk || dokumen.length >= 20}
        data-testid={`bast-unggah-akhir-${bast.id}`} onClick={() => { setPeriksa(null); setUnggah({ file: null, jenis: "dokumen_lengkap", catatan: "", key: crypto.randomUUID() }); }}>Unggah dokumen akhir</Button>}
    </div>
    <p className="text-xs text-muted-foreground">Scan manual, format lain, atau hasil setelah e-meterai dapat diarsipkan di sini. Tidak menimpa bukti dasar, mengubah isi BAST, atau menerapkan ulang BMN Saya. Perubahan isi wajib melalui revisi resmi.</p>
    {unggah && <div className="space-y-3 border-t pt-3" data-testid="bast-akhir-form">
      <label className="block space-y-1"><span>Jenis dokumen</span><select className="w-full min-w-0 rounded-md border bg-background p-2 text-sm" value={unggah.jenis} disabled={sibuk} data-testid="bast-akhir-jenis" onChange={e => ubahUnggah({ jenis: e.target.value })}>
        {Object.entries(JENIS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label>
      <input ref={inputRef} className="hidden" type="file" accept=".pdf,.jpg,.jpeg,.png" disabled={sibuk} data-testid="bast-akhir-file" onChange={e => {
        const file = e.target.files?.[0]; e.target.value = "";
        if (!file) return;
        if (!/\.(pdf|jpe?g|png)$/i.test(file.name) || !file.size || file.size > 10 * 1024 * 1024) {
          toast.error("Pilih PDF/JPG/PNG yang tidak kosong, maksimal 10 MB"); return;
        }
        ubahUnggah({ file });
      }} />
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" disabled={sibuk} data-testid="bast-akhir-pilih" onClick={() => inputRef.current?.click()}>Pilih PDF / foto</Button>
        {preview && <a href={preview} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-[44px] items-center underline" data-testid="bast-akhir-preview-lokal">Pratinjau berkas terpilih</a>}
      </div>
      <p className="break-all text-xs">{unggah.file?.name || "Belum ada berkas dipilih"} · Maksimal 10 MB/berkas, 20 arsip/BAST. Berkas disimpan tanpa kompresi ulang.</p>
      <label className="block space-y-1"><span>Keterangan dokumen *</span><Textarea value={unggah.catatan} maxLength={1000} disabled={sibuk} data-testid="bast-akhir-catatan" placeholder="Contoh: dokumen lengkap setelah pembubuhan e-meterai, isi BAST tidak berubah" onChange={e => ubahUnggah({ catatan: e.target.value })} /></label>
      <p className="text-xs text-muted-foreground">Bila scan ini menjadi bukti awal untuk penerapan BAST, gunakan Unggah Bukti TTD / Lengkapi bukti pada tombol utama. Arsip tambahan ini tidak menggantikan verifikasi bukti awal.</p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" disabled={sibuk || !unggah.file || unggah.catatan.trim().length < 5} onClick={simpan} data-testid="bast-akhir-simpan">{sibuk ? "Menyimpan…" : "Arsipkan dokumen"}</Button>
        <Button type="button" variant="outline" disabled={sibuk} onClick={() => setUnggah(null)} data-testid="bast-akhir-batal">Batal</Button>
      </div>
    </div>}
    {!!dokumen.length && <details className="border-t pt-2" open={!!periksa || undefined}>
      <summary className="min-h-[44px] cursor-pointer py-3 font-medium" data-testid={`bast-akhir-riwayat-${bast.id}`}>Riwayat dokumen akhir ({dokumen.length})</summary>
      <ul className="space-y-3">
        {[...dokumen].reverse().map(d => <li key={d.id} className="rounded-md border p-2 space-y-1 break-words" data-testid={`bast-akhir-item-${d.id}`}>
          <p className="font-semibold break-all">{d.filename}</p>
          <p>{JENIS[d.jenis] || d.jenis} · {STATUS[d.status] || d.status}</p>
          <p className="text-muted-foreground">{d.oleh} · {String(d.diunggah_pada || "").slice(0, 10)}</p>
          <p>{d.catatan}</p>
          {d.pemeriksaan && <p className="text-muted-foreground">Diperiksa {d.pemeriksaan.oleh} · {String(d.pemeriksaan.pada).slice(0, 10)}: {d.pemeriksaan.catatan}</p>}
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" size="sm" className="min-h-[44px] text-xs" disabled={sibuk} data-testid={`bast-akhir-lihat-${d.id}`} onClick={() => {
              bukaDokumen(d.id); if (periksa?.id === d.id) ubahPeriksa({ dibaca: true });
            }}>Pratinjau dokumen</Button>
            {boleh && d.status === "menunggu" && <Button type="button" variant="outline" size="sm" className="min-h-[44px] text-xs" disabled={sibuk} data-testid={`bast-akhir-periksa-${d.id}`} onClick={() => {
              setUnggah(null); setPeriksa({ id: d.id, dibaca: false, setuju: false, status: "sesuai", catatan: "", key: crypto.randomUUID() });
            }}>Periksa kelengkapan</Button>}
          </div>
          {periksa?.id === d.id && <div className="space-y-3 border-t pt-2">
            <p>Buka Pratinjau dokumen di atas, cocokkan nomor, pihak, barang, seluruh halaman, tanda tangan dan kelengkapan meterai bila diperlukan. Pemeriksaan ini bukan validasi otomatis sertifikat TTE/e-meterai.</p>
            <label className="block space-y-1"><span>Hasil pemeriksaan</span><select value={periksa.status} disabled={sibuk} className="w-full rounded-md border bg-background p-2 text-sm" data-testid="bast-akhir-hasil" onChange={e => ubahPeriksa({ status: e.target.value, setuju: false })}><option value="sesuai">Sesuai</option><option value="tidak_sesuai">Tidak sesuai</option></select></label>
            <label className="block space-y-1"><span>Catatan pemeriksaan *</span><Textarea value={periksa.catatan} maxLength={1000} disabled={sibuk} data-testid="bast-akhir-catatan-periksa" onChange={e => ubahPeriksa({ catatan: e.target.value })} /></label>
            <label className="flex items-start gap-2"><input type="checkbox" checked={periksa.setuju} disabled={sibuk || !periksa.dibaca} className="mt-1 h-4 w-4 shrink-0" data-testid="bast-akhir-konfirmasi" onChange={e => ubahPeriksa({ setuju: e.target.checked })} /><span>Saya telah membuka dan memeriksa dokumen; hasil di atas sesuai pemeriksaan saya.</span></label>
            <div className="flex flex-wrap gap-2"><Button type="button" disabled={sibuk || !periksa.dibaca || !periksa.setuju || periksa.catatan.trim().length < 5} data-testid="bast-akhir-simpan-periksa" onClick={simpan}>{sibuk ? "Menyimpan…" : "Catat pemeriksaan"}</Button><Button type="button" variant="outline" disabled={sibuk} data-testid="bast-akhir-batal-periksa" onClick={() => setPeriksa(null)}>Batal</Button></div>
          </div>}
        </li>)}
      </ul>
    </details>}
  </section>;
}
