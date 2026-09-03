import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Share2, Copy, Clock, Plus, Loader2, Link2, MessageSquare, MapPin,
  Trash2, RefreshCcw, Check, RotateCw, ChevronDown, Pencil, X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import {
  Popover, PopoverContent, PopoverTrigger,
} from "@/components/ui/popover";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { getApiError } from "../../lib/utils";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
/** Kenapa peta sedang disempitkan — dipakai untuk menyebut sebabnya, bukan
 *  sekadar "terpilih", supaya operator tahu penyempit mana yang sedang aktif. */
const LABEL_SEBAB = {
  seleksi: "yang dipilih",
  filter: "hasil filter",
  kelompok: "kelompok barang serupa",
};
const PRESET = [
  { label: "1 hari", jam: 24 }, { label: "3 hari", jam: 72 },
  { label: "7 hari", jam: 168 }, { label: "30 hari", jam: 720 },
];

/**
 * Logo WhatsApp. Digambar sendiri karena lucide sengaja tidak memuat ikon
 * MEREK — dan di baris aksi yang sempit, gagang telepon generik tidak
 * memberitahu ke mana tautan akan dikirim, sedangkan logo ini memberitahu.
 */
function IkonWhatsApp({ className = "" }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false" className={className}>
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51a12.8 12.8 0 0 0-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.872.118.571-.085 1.758-.719 2.006-1.413.247-.694.247-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884a9.82 9.82 0 0 1 6.988 2.896 9.83 9.83 0 0 1 2.892 6.994c-.003 5.45-4.437 9.886-9.884 9.886m8.413-18.297A11.8 11.8 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.9 11.9 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893A11.8 11.8 0 0 0 20.464 3.488" />
    </svg>
  );
}

function sisa(iso) {
  const ms = new Date(iso).getTime() - Date.now();
  if (isNaN(ms) || ms <= 0) return "berakhir";
  const jam = Math.floor(ms / 3600000), hari = Math.floor(jam / 24);
  return hari >= 1 ? `${hari} hari lagi` : `${Math.max(1, jam)} jam lagi`;
}

/**
 * Bagikan peta kegiatan sebagai link kolaboratif ber-masa-tayang. Selama aktif,
 * siapa pun berlink dapat melihat titik aset, berkomentar, & menambah titik.
 * Dikelola operator/admin satker kegiatan; dapat diperpanjang & dibatalkan.
 */
export default function BagikanPetaDialog({ open, onClose, activity, lingkup = null }) {
  const [shares, setShares] = useState([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [durasiJam, setDurasiJam] = useState(72);
  const [judul, setJudul] = useState("");
  const [izinTitik, setIzinTitik] = useState(true);
  const [izinKomentar, setIzinKomentar] = useState(true);
  // Judul link yang sudah terbit boleh dikoreksi tanpa menerbitkan tautan baru
  // (id share yang sedang diedit + nilai yang sedang diketik).
  const [editJudul, setEditJudul] = useState("");
  const [nilaiJudul, setNilaiJudul] = useState("");
  const [menyimpanJudul, setMenyimpanJudul] = useState(false);
  const [tersalin, setTersalin] = useState("");
  // Link mati > sebulan tidak lagi dikirim server. Jumlahnya ditampilkan agar
  // daftar yang menyusut tak terbaca sebagai data hilang.
  const [diarsipkan, setDiarsipkan] = useState(0);
  const { confirm, confirmDialog } = useConfirm();

  // Lingkup dibekukan pemanggil saat tombol Bagikan ditekan; di sini ia hanya
  // dibaca. `ids` null = seluruh kegiatan (perilaku sejak awal).
  const ids = lingkup?.disempitkan ? (lingkup.ids || []) : null;
  const disempitkan = !!lingkup?.disempitkan;
  const jumlahTitik = disempitkan
    ? (ids ? ids.length : 0)
    : (Number(lingkup?.jumlah) || 0);

  const muat = useCallback(() => {
    if (!activity?.id) return;
    setLoading(true);
    axios.get(`${API}/peta/share`, { params: { activity_id: activity.id } })
      .then((r) => { setShares(r.data?.items || []); setDiarsipkan(r.data?.diarsipkan || 0); })
      .catch(() => { setShares([]); setDiarsipkan(0); })
      .finally(() => setLoading(false));
  }, [activity?.id]);

  useEffect(() => { if (open) { muat(); setTersalin(""); setEditJudul(""); } }, [open, muat]);

  const salin = async (link, sid) => {
    try {
      await navigator.clipboard.writeText(link);
      setTersalin(sid); setTimeout(() => setTersalin(""), 2000);
      toast.success("Link disalin");
    } catch { toast.error("Tak bisa menyalin — salin manual dari kotak link"); }
  };

  const buat = async () => {
    setCreating(true);
    try {
      const r = await axios.post(`${API}/peta/share`, {
        activity_id: activity.id, judul: judul.trim(), durasi_jam: durasiJam,
        izinkan_titik_publik: izinTitik, izinkan_komentar_publik: izinKomentar,
        // Hanya dikirim saat peta memang sedang disempitkan. Tanpa penyempit,
        // biarkan server memakai perilaku "seluruh kegiatan" yang HIDUP —
        // mengirim daftar id lengkap akan membekukannya tanpa diminta.
        ...(ids ? { asset_ids: ids } : {}),
      });
      toast.success("Link peta kolaboratif dibuat");
      setJudul("");
      muat();
      if (r.data?.link) salin(r.data.link, r.data.id);
    } catch (e) { toast.error(getApiError(e, "Gagal membuat link")); }
    finally { setCreating(false); }
  };

  const bagikanWA = (link, judulShare) => {
    const teks = `${judulShare || "Peta Kolaboratif"} — bantu tandai & beri komentar:\n${link}`;
    window.open(`https://wa.me/?text=${encodeURIComponent(teks)}`, "_blank", "noopener");
  };

  const bagikanNatif = async (link, judulShare) => {
    if (navigator.share) {
      try { await navigator.share({ title: judulShare || "Peta Kolaboratif", url: link }); } catch { /* dibatalkan */ }
    } else { salin(link); }
  };

  const mulaiEditJudul = (s) => { setEditJudul(s.id); setNilaiJudul(s.judul || ""); };

  /**
   * Simpan judul baru. Judul ikut tampil di halaman publik & teks ajakan
   * WhatsApp, jadi salah ketik harus bisa dikoreksi tanpa mematikan tautan
   * yang sudah tersebar — server hanya mengubah field judul, jti tak dirotasi.
   */
  const simpanJudul = async (sid) => {
    const judul = nilaiJudul.trim().slice(0, 140);
    setMenyimpanJudul(true);
    try {
      await axios.put(`${API}/peta/share/${sid}/judul`, { judul });
      // Perbarui di tempat: memuat ulang seluruh daftar hanya untuk satu judul
      // membuat layar berkedip tanpa alasan.
      setShares((ds) => ds.map((x) => (x.id === sid ? { ...x, judul } : x)));
      setEditJudul("");
      toast.success("Judul peta diperbarui");
    } catch (e) { toast.error(getApiError(e, "Gagal mengubah judul")); }
    finally { setMenyimpanJudul(false); }
  };

  // Laci durasi perpanjang, per share (id share yang sedang terbuka).
  const [menuPerpanjang, setMenuPerpanjang] = useState("");

  const perpanjang = async (sid, jam) => {
    try {
      await axios.put(`${API}/peta/share/${sid}/perpanjang`, { durasi_jam: jam });
      toast.success(`Diperpanjang ${jam >= 24 ? `${Math.round(jam / 24)} hari` : `${jam} jam`}`);
      muat();
    } catch (e) { toast.error(getApiError(e, "Gagal memperpanjang")); }
    finally { setMenuPerpanjang(""); }
  };

  const batal = async (sid) => {
    const ok = await confirm({
      title: "Batalkan link peta?",
      description: "Link akan mati permanen untuk publik. Kontribusi yang sudah masuk tetap tersimpan. Untuk berbagi lagi, gunakan Terbitkan ulang.",
      confirmLabel: "Batalkan", variant: "danger",
    });
    if (!ok) return;
    try { await axios.post(`${API}/peta/share/${sid}/batal`); toast.success("Link dibatalkan"); muat(); }
    catch (e) { toast.error(getApiError(e, "Gagal membatalkan")); }
  };

  const terbitkanUlang = async (sid, jam, { revive = false } = {}) => {
    const ok = await confirm({
      title: revive ? "Terbitkan ulang link ini?" : "Ganti tautan (terbitkan ulang)?",
      description: revive
        ? "Link baru dibuat & diaktifkan kembali. Kontribusi lama tetap tersimpan."
        : "Tautan LAMA yang sudah tersebar akan langsung mati; tautan baru dibuat. Pakai ini bila link bocor.",
      confirmLabel: "Terbitkan ulang",
    });
    if (!ok) return;
    try {
      const r = await axios.post(`${API}/peta/share/${sid}/terbitkan-ulang`, { durasi_jam: jam });
      toast.success("Link diterbitkan ulang — tautan baru aktif");
      muat();
      if (r.data?.link) salin(r.data.link, sid);
    } catch (e) { toast.error(getApiError(e, "Gagal menerbitkan ulang")); }
  };

  const aktif = shares.filter((s) => s.status !== "batal");
  const dibatalkan = shares.filter((s) => s.status === "batal");

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-lg w-[calc(100%-1.5rem)] overflow-x-hidden p-4 sm:p-6">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Share2 className="w-5 h-5 text-blue-600" />Bagikan Peta Kolaboratif</DialogTitle>
          <DialogDescription className="text-xs">
            Bagikan peta kegiatan ini via link. Selama masa tayang, siapa pun berlink dapat melihat titik aset,
            berkomentar, dan menambah titik. Setelah kedaluwarsa hanya operator/admin satker ini yang bisa membuka.
          </DialogDescription>
        </DialogHeader>

        {/* Buat link baru */}
        <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-3 space-y-2.5">
          <p className="text-xs font-semibold text-blue-700 dark:text-blue-300">Buat link baru</p>
          <Input value={judul} onChange={(e) => setJudul(e.target.value)} maxLength={140}
            placeholder="Judul peta (opsional, mis. Verifikasi Lapangan Blok A)" className="h-9 text-sm" data-testid="bagikan-judul" />
          <div>
            <p className="text-[11px] text-muted-foreground mb-1">Masa tayang</p>
            <div className="flex flex-wrap gap-1.5">
              {PRESET.map((p) => (
                <button key={p.jam} type="button" onClick={() => setDurasiJam(p.jam)}
                  className={`px-2.5 h-8 rounded-full text-[11px] font-semibold border min-w-0 min-h-0 ${durasiJam === p.jam ? "bg-teal-700 border-teal-700 text-white" : "border-border text-muted-foreground hover:bg-muted"}`}
                  data-testid={`bagikan-durasi-${p.jam}`}>{p.label}</button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <label className="flex items-center gap-1.5 text-[11px] cursor-pointer">
              <input type="checkbox" checked={izinTitik} onChange={(e) => setIzinTitik(e.target.checked)} className="w-3.5 h-3.5" />
              <MapPin className="w-3 h-3 text-emerald-600" />Tamu boleh menambah titik
            </label>
            <label className="flex items-center gap-1.5 text-[11px] cursor-pointer">
              <input type="checkbox" checked={izinKomentar} onChange={(e) => setIzinKomentar(e.target.checked)} className="w-3.5 h-3.5" />
              <MessageSquare className="w-3 h-3 text-blue-600" />Tamu boleh berkomentar
            </label>
          </div>
          {/* Apa yang akan dibagikan — ditulis SEBELUM tombolnya, sebab
              inilah keputusan yang sedang diambil operator. Peta yang
              disempitkan filter/seleksi membagikan titik itu saja, dan tanpa
              kalimat ini tak ada tempat untuk mengetahuinya. */}
          <div className={`rounded-lg border px-2.5 py-2 ${disempitkan
            ? "border-amber-400/50 bg-amber-500/10"
            : "border-border bg-muted/40"}`} data-testid="bagikan-lingkup">
            <p className="text-[11px] font-semibold text-foreground flex items-center gap-1.5">
              <MapPin className={`w-3 h-3 flex-shrink-0 ${disempitkan ? "text-amber-600" : "text-muted-foreground"}`} />
              {disempitkan
                ? <>Akan dibagikan <b>{jumlahTitik}</b> titik {LABEL_SEBAB[lingkup?.sebab] || "terpilih"}</>
                : <>Akan dibagikan <b>seluruh titik</b> kegiatan ini</>}
            </p>
            <p className="text-[10px] text-muted-foreground leading-snug mt-0.5">
              {disempitkan
                ? `Titik lain tidak ikut, meski ada di kegiatan yang sama${lingkup?.total ? ` (${lingkup.total} titik seluruhnya)` : ""}. Himpunan ini tetap sama walau filter diubah setelah link terbit.`
                : "Aset yang ditambahkan setelah ini ikut tampil di peta yang dibagikan."}
            </p>
            {disempitkan && lingkup?.terpotong && (
              <p className="text-[10px] text-amber-700 dark:text-amber-400 leading-snug mt-1" data-testid="bagikan-lingkup-terpotong">
                Sebagian titik yang cocok filter belum termuat di peta — yang belum termuat tidak ikut dibagikan.
              </p>
            )}
            {disempitkan && jumlahTitik === 0 && (
              <p className="text-[10px] text-red-600 dark:text-red-400 leading-snug mt-1" data-testid="bagikan-lingkup-kosong">
                Tak ada titik yang tampil. Longgarkan filter atau kosongkan seleksi dulu.
              </p>
            )}
          </div>
          <Button onClick={buat} disabled={creating || (disempitkan && jumlahTitik === 0)} size="sm" className="w-full h-9 gap-1.5 bg-teal-700 hover:bg-teal-800 text-white" data-testid="bagikan-buat">
            {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}Buat & salin link
          </Button>
        </div>

        {/* Daftar link aktif */}
        <div className="space-y-2">
          <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wide">Link aktif</p>
          {loading ? (
            <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>
          ) : aktif.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">Belum ada link. Buat di atas.</p>
          ) : aktif.map((s) => (
            <div key={s.id} className="rounded-lg border border-border bg-card p-2.5 space-y-2" data-testid={`bagikan-item-${s.id}`}>
              <div className="flex items-center justify-between gap-2">
                {editJudul === s.id ? (
                  <form className="flex items-center gap-1 flex-1 min-w-0"
                    onSubmit={(e) => { e.preventDefault(); simpanJudul(s.id); }}>
                    <Input autoFocus value={nilaiJudul} onChange={(e) => setNilaiJudul(e.target.value)}
                      maxLength={140} placeholder="Judul peta" className="h-7 text-xs flex-1 min-w-0 min-h-0"
                      data-testid={`bagikan-judul-input-${s.id}`} />
                    <button type="submit" disabled={menyimpanJudul} title="Simpan judul"
                      className="h-7 w-7 rounded-md border border-emerald-300 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400 flex items-center justify-center flex-shrink-0 min-w-0 min-h-0"
                      data-testid={`bagikan-judul-simpan-${s.id}`}>
                      {menyimpanJudul ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                    </button>
                    <button type="button" onClick={() => setEditJudul("")} title="Batal"
                      className="h-7 w-7 rounded-md border border-border text-muted-foreground flex items-center justify-center flex-shrink-0 min-w-0 min-h-0"
                      data-testid={`bagikan-judul-batal-${s.id}`}>
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </form>
                ) : (<>
                  <div className="flex items-center gap-1 min-w-0 flex-1">
                    <p className="text-xs font-semibold text-foreground truncate">{s.judul || "Peta Kolaboratif"}</p>
                    <button onClick={() => mulaiEditJudul(s)} title="Ubah judul peta"
                      aria-label="Ubah judul peta"
                      className="h-6 w-6 rounded-md text-muted-foreground hover:bg-muted flex items-center justify-center flex-shrink-0 min-w-0 min-h-0"
                      data-testid={`bagikan-judul-edit-${s.id}`}>
                      <Pencil className="w-3 h-3" />
                    </button>
                  </div>
                  <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full flex-shrink-0 ${s.kedaluwarsa ? "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400" : "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400"}`}>
                    <Clock className="w-2.5 h-2.5 inline mr-0.5" />{s.kedaluwarsa ? "Kedaluwarsa" : sisa(s.berlaku_sampai)}
                  </span>
                </>)}
              </div>
              {s.link && (
                <div className="flex items-center gap-1.5">
                  <div className="flex-1 min-w-0 bg-muted rounded-md px-2 py-1.5 text-[10px] font-mono text-muted-foreground flex items-center gap-1">
                    <Link2 className="w-3 h-3 flex-shrink-0" />
                    {/* min-w-0 + flex-1 pada SPAN teks agar text-overflow:ellipsis ("...")
                        benar-benar tampil & link panjang tak pernah melebihi kanvas
                        (truncate pada wadah flex tak memunculkan elipsis). */}
                    <span className="min-w-0 flex-1 truncate" title={s.link}>{s.link}</span>
                  </div>
                  <button onClick={() => salin(s.link, s.id)} title="Salin" className="h-8 w-8 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:bg-muted min-w-0 min-h-0" data-testid={`bagikan-salin-${s.id}`}>
                    {tersalin === s.id ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              )}
              {/* Jumlah titik yang DIBAGIKAN lewat tautan ini. Tanpa angka
                  ini, dua tautan pada kegiatan yang sama tampak identik
                  padahal yang satu membagikan lima titik dan yang lain
                  seluruhnya. */}
              <p className="text-[10px] text-muted-foreground flex items-center gap-1 flex-wrap">
                <span className="inline-flex items-center gap-0.5">
                  <MapPin className="w-2.5 h-2.5" />
                  {s.lingkup === "terpilih"
                    ? <><b className="text-foreground/80">{s.jumlah_titik_dibagikan || 0}</b> titik dibagikan</>
                    : <>seluruh titik kegiatan</>}
                </span>
                <span aria-hidden="true">·</span>
                <span>{s.jumlah_kontribusi || 0} kontribusi</span>
              </p>
              <div className="flex flex-wrap items-center gap-1.5">
                {/* Di HP baris aksi ini sempit — dua tombol berlabel memaksanya
                    pecah baris. Labelnya disembunyikan di <sm; yang tersisa
                    logo WhatsApp (bukan ikon telepon generik) & ikon bagikan,
                    keduanya sudah menyatakan tujuannya sendiri. */}
                {s.link && (
                  <button onClick={() => bagikanWA(s.link, s.judul)}
                    title="Bagikan lewat WhatsApp" aria-label="Bagikan lewat WhatsApp"
                    className="h-7 w-7 sm:w-auto sm:px-2 rounded-md bg-green-600 text-white text-[11px] font-semibold flex items-center justify-center sm:gap-1 flex-shrink-0 min-w-0 min-h-0"
                    data-testid={`bagikan-wa-${s.id}`}>
                    <IkonWhatsApp className="w-3.5 h-3.5" /><span className="hidden sm:inline">WhatsApp</span>
                  </button>
                )}
                {s.link && (
                  <button onClick={() => bagikanNatif(s.link, s.judul)}
                    title="Bagikan lewat aplikasi lain" aria-label="Bagikan lewat aplikasi lain"
                    className="h-7 w-7 sm:w-auto sm:px-2 rounded-md border border-border text-[11px] text-muted-foreground flex items-center justify-center sm:gap-1 flex-shrink-0 min-w-0 min-h-0"
                    data-testid={`bagikan-natif-${s.id}`}>
                    <Share2 className="w-3.5 h-3.5" /><span className="hidden sm:inline">Bagikan…</span>
                  </button>
                )}
                {/* Perpanjang: durasinya DIPILIH, bukan dipatok 7 hari. Pilihannya
                    sama persis dengan saat link dibuat (PRESET) supaya operator
                    tak perlu menghafal dua daftar yang berbeda. */}
                <Popover open={menuPerpanjang === s.id}
                  onOpenChange={(o) => setMenuPerpanjang(o ? s.id : "")}>
                  <PopoverTrigger asChild>
                    <button title="Perpanjang masa tayang — pilih durasi" className="h-7 px-2 rounded-md border border-blue-300 dark:border-blue-800 text-blue-600 dark:text-blue-400 text-[11px] font-semibold flex items-center gap-1 min-w-0 min-h-0" data-testid={`bagikan-perpanjang-${s.id}`}>
                      <RefreshCcw className="w-3 h-3" />Perpanjang
                      <ChevronDown className="w-3 h-3 opacity-70" />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent align="start" className="w-auto p-1">
                    <p className="px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                      Perpanjang dari sekarang
                    </p>
                    <div className="flex flex-col">
                      {PRESET.map((d) => (
                        <button key={d.jam} onClick={() => perpanjang(s.id, d.jam)}
                          className="h-8 px-3 rounded-md text-[12px] font-semibold text-left hover:bg-muted min-w-0 min-h-0"
                          data-testid={`bagikan-perpanjang-${s.id}-${d.jam}`}>
                          {d.label}
                        </button>
                      ))}
                    </div>
                  </PopoverContent>
                </Popover>
                <button onClick={() => terbitkanUlang(s.id, 168)} title="Ganti tautan — matikan link lama yang bocor, buat link baru" className="h-7 w-7 rounded-md border border-amber-300 dark:border-amber-800 text-amber-600 dark:text-amber-400 flex items-center justify-center min-w-0 min-h-0" data-testid={`bagikan-ganti-${s.id}`}>
                  <RotateCw className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => batal(s.id)} title="Batalkan" className="h-7 w-7 rounded-md border border-red-200 dark:border-red-800 text-red-500 flex items-center justify-center min-w-0 min-h-0" data-testid={`bagikan-batal-${s.id}`}>
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Link dibatalkan — bisa diterbitkan ulang (tautan baru, yang lama tetap mati) */}
        {dibatalkan.length > 0 && (
          <div className="space-y-2">
            <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wide">Dibatalkan</p>
            {dibatalkan.map((s) => (
              <div key={s.id} className="rounded-lg border border-dashed border-border bg-muted/40 p-2.5 flex items-center justify-between gap-2" data-testid={`bagikan-batal-item-${s.id}`}>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-muted-foreground truncate line-through">{s.judul || "Peta Kolaboratif"}</p>
                  <p className="text-[10px] text-muted-foreground">{s.jumlah_kontribusi || 0} kontribusi tersimpan</p>
                </div>
                <button onClick={() => terbitkanUlang(s.id, 168, { revive: true })} className="h-7 px-2 rounded-md border border-emerald-300 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400 text-[11px] font-semibold flex items-center gap-1 flex-shrink-0 min-w-0 min-h-0" data-testid={`bagikan-terbitkan-ulang-${s.id}`}>
                  <RotateCw className="w-3 h-3" />Terbitkan ulang
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Daftar tak dibiarkan menumpuk: link yang sudah mati lebih dari
            sebulan tak lagi ditampilkan. Jumlahnya disebut supaya daftar yang
            menyusut tidak terbaca sebagai data yang hilang. */}
        {diarsipkan > 0 && (
          <p className="text-[10px] text-muted-foreground leading-snug" data-testid="bagikan-diarsipkan">
            <b>{diarsipkan}</b> link yang sudah mati lebih dari sebulan tidak lagi ditampilkan.
            Kontribusi yang telanjur masuk lewat link itu tetap tersimpan.
          </p>
        )}
        {confirmDialog}
      </DialogContent>
    </Dialog>
  );
}
