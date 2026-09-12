import React, { useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Eye, Plus, Trash2, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { authMediaUrl } from "@/lib/mediaUrl";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const KOSONG = { nama: "", nip: "", jabatan: "", email: "", jumlah_ttd: 1 };
const tervalidasi = (s) => ["terverifikasi", "ditandatangani"].includes(s.status);
const bisaHapus = (s) => ["aktif", "menunggu"].includes(s.status) && !s.signature_file_id;
const kunciBaru = () => globalThis.crypto?.randomUUID?.() || `peserta-${Date.now()}-${Math.random().toString(36).slice(2)}`;

export function RiwayatPenandatangan({ data }) {
  const riwayat = data?.riwayat_penandatangan || [];
  if (!riwayat.length) return null;
  return <details className="rounded-lg border border-border p-2 text-xs" data-testid="riwayat-penandatangan">
    <summary className="cursor-pointer font-medium">Riwayat perubahan penanda tangan ({riwayat.length})</summary>
    <ol className="mt-2 space-y-2 max-h-48 overflow-y-auto">
      {[...riwayat].reverse().map((e, i) => <li key={`${e.pada}-${i}`} className="break-words">
        <p className="font-medium">{e.aksi === "tambah" ? "Ditambahkan" : "Dihapus"}: {e.nama}</p>
        <p>{e.alasan}</p>
        <p className="text-muted-foreground">{e.oleh} · {e.pada ? new Date(e.pada).toLocaleString("id-ID") : "—"}</p>
        {e.konfirmasi_final && <p>Pengelola mengonfirmasi pemeriksaan dan finalisasi.</p>}
      </li>)}
    </ol>
  </details>;
}

export default function KelolaPenandatangan({ data, pegawai = [], onBerubah }) {
  const [open, setOpen] = useState(false);
  const [aksi, setAksi] = useState("tambah");
  const [target, setTarget] = useState(null);
  const [signer, setSigner] = useState(KOSONG);
  const [alasan, setAlasan] = useState("");
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState("");
  const [basi, setBasi] = useState(false);
  const [diperiksa, setDiperiksa] = useState(false);
  const [final, setFinal] = useState(false);
  const requestKey = useRef(null);
  const sudahKirim = useRef(false);
  const daftar = data?.signers || [];
  const sisa = daftar.filter((s) => s.signer_id !== target?.signer_id);
  const akanFinal = aksi === "hapus" && sisa.length > 0 && sisa.every(tervalidasi);

  const pilih = (mode, orang = null) => {
    setAksi(mode); setTarget(orang); setGalat(""); setFinal(false); setDiperiksa(false);
    requestKey.current = null;
  };
  const buka = () => {
    pilih("tambah"); setSigner({ ...KOSONG }); setAlasan(""); setBasi(false); setOpen(true);
  };
  const periksa = () => {
    const bagian = data.dok_file_id
      ? (daftar.some((s) => s.signature_file_id) ? "dokumen-ttd" : "dokumen") : "lembar-pdf";
    window.open(authMediaUrl(`${API}/ttd/permintaan/${data.id}/${bagian}`), "_blank", "noopener,noreferrer");
    setDiperiksa(true);
  };
  const simpan = async () => {
    if (sudahKirim.current || basi) return;
    const payload = { aksi, alasan: alasan.trim(),
      ...(aksi === "tambah" ? { signer: { ...signer, jumlah_ttd: Number(signer.jumlah_ttd) } }
        : { signer_id: target.signer_id, konfirmasi_final: akanFinal && final }) };
    const fingerprint = JSON.stringify(payload);
    if (requestKey.current?.fingerprint !== fingerprint) requestKey.current = { fingerprint, key: kunciBaru() };
    sudahKirim.current = true; setSibuk(true); setGalat("");
    try {
      await axios.post(`${API}/ttd/permintaan/${data.id}/penandatangan`, payload,
        { headers: { "If-Match": String(data.version), "Idempotency-Key": requestKey.current.key } });
      setOpen(false);
      toast.success(aksi === "tambah" ? "Penanda tangan ditambahkan. Terbitkan dan bagikan tautannya." : "Penanda tangan dihapus; riwayat perubahan tersimpan.");
      await onBerubah?.();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setGalat(typeof detail === "string" ? detail : detail?.message || "Gagal menyimpan perubahan. Coba lagi.");
      if (e?.response?.status === 409) setBasi(true);
      // Gangguan jaringan memakai kunci yang sama. Isian berbeda mendapatkan
      // kunci baru; konflik memerlukan muat ulang, tidak retry buta.
      if (e?.response?.status && e.response.status !== 409) requestKey.current = null;
    } finally { sudahKirim.current = false; setSibuk(false); }
  };

  if (!data?.dapat_kelola_penandatangan || ["selesai", "batal"].includes(data.status)) return null;
  return <>
    <Button variant="outline" size="sm" onClick={buka} className="text-xs">
      <Users className="w-4 h-4 mr-1.5" />Kelola penanda tangan
    </Button>
    <Dialog open={open} onOpenChange={(o) => { if (!sibuk) setOpen(o); }}>
      <DialogContent className="max-w-lg max-h-[90dvh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Kelola penanda tangan</DialogTitle>
          <DialogDescription>Perubahan peserta dicatat pada permintaan dan riwayat BAST terkait.
            Isi PDF, nomor surat, serta penerima/penanggung jawab dalam naskah BAST tidak diubah.</DialogDescription>
        </DialogHeader>
        <fieldset disabled={sibuk || basi} className="space-y-3 min-w-0">
          <div className="space-y-1">
            {daftar.map((s) => <div key={s.signer_id} className="flex items-center justify-between gap-2 border-b border-border py-1 text-xs">
              <span className="min-w-0 break-words">{s.nama}</span>
              {bisaHapus(s) && daftar.length > 1
                ? <Button size="sm" variant="ghost" onClick={() => pilih("hapus", s)} aria-label={`Hapus ${s.nama}`}><Trash2 className="w-4 h-4" /></Button>
                : <span className="text-muted-foreground">{bisaHapus(s) ? "Minimal satu peserta" : "Bubuhan dilindungi"}</span>}
            </div>)}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => pilih("tambah")}><Plus className="w-4 h-4 mr-1" />Tambah penanda tangan</Button>
          {aksi === "tambah" ? <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {[["nama", "Nama"], ["nip", "NIP/NIK (opsional)"], ["jabatan", "Jabatan (opsional)"], ["email", "Email (opsional)"]].map(([key, label]) =>
              <label key={key} className="text-xs space-y-1">{label}<Input value={signer[key]} maxLength={300}
                list={key === "nama" ? "saran-peserta-tambahan" : undefined}
                onChange={(e) => {
                  const value = e.target.value;
                  const pg = key === "nama" ? pegawai.find((p) => p.nama === value) : null;
                  setSigner((s) => pg ? { ...s, nama: pg.nama, nip: pg.nip || "", jabatan: pg.jabatan || "", email: pg.email || "" } : { ...s, [key]: value });
                }} /></label>)}
            <datalist id="saran-peserta-tambahan">{pegawai.map((p, i) => <option key={p.id || i} value={p.nama} />)}</datalist>
            <label className="text-xs space-y-1">Jumlah pembubuhan<Input type="number" min="1" max="20" value={signer.jumlah_ttd}
              onChange={(e) => setSigner((s) => ({ ...s, jumlah_ttd: e.target.value }))} /></label>
          </div> : <p className="text-sm text-destructive">Hapus {target?.nama}? Tautannya tidak dapat digunakan lagi.</p>}
          <label className="block text-xs space-y-1">Alasan perubahan
            <textarea value={alasan} maxLength={1000} rows={3} onChange={(e) => setAlasan(e.target.value)}
              className="w-full rounded-md border border-input bg-background p-2 text-sm" />
          </label>
          <Button variant="outline" size="sm" onClick={periksa}><Eye className="w-4 h-4 mr-1" />Periksa Dokumen</Button>
          {akanFinal && <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs space-y-2">
            <p>Semua peserta yang tersisa sudah tervalidasi. Penghapusan ini akan memfinalkan permintaan.</p>
            <label className="flex items-start gap-2"><input type="checkbox" checked={final} disabled={!diperiksa}
              onChange={(e) => setFinal(e.target.checked)} />Saya sudah memeriksa dokumen dan menyetujui finalisasi dengan peserta yang tersisa.</label>
          </div>}
        </fieldset>
        {galat && <p role="alert" className="text-sm text-destructive">{galat}</p>}
        <DialogFooter>
          {basi ? <Button variant="outline" onClick={async () => { await onBerubah?.(); setOpen(false); }}>Muat ulang permintaan</Button>
            : <Button onClick={simpan} disabled={sibuk || alasan.trim().length < 5 || (aksi === "tambah" &&
                (!signer.nama.trim() || !Number.isInteger(Number(signer.jumlah_ttd)) || Number(signer.jumlah_ttd) < 1 || Number(signer.jumlah_ttd) > 20)) || (akanFinal && !final)}>
              {sibuk ? "Menyimpan…" : aksi === "tambah" ? "Simpan penanda tangan" : akanFinal ? "Hapus dan finalisasi" : "Hapus penanda tangan"}
            </Button>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </>;
}
