import React, { useEffect, useImperativeHandle, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Copy, Loader2, Ticket } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { noAgendaTampil } from "@/lib/nomorAgenda";
import { teksSumberKlasifikasi } from "@/lib/klasifikasiNomor";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Tombol "Booking Nomor" — pesan nomor surat keluar dari halaman modul/laporan
 * mana pun tanpa pindah ke Registrasi Persuratan. Modul, jenis naskah,
 * kegiatan, dan referensi terisi otomatis dari konteks halaman; klasifikasi
 * mengikuti aturan pemetaan persuratan; pratinjau nomor tampil live.
 *
 * Pakai: <BookingNomorButton modul="pelaporan" jenisNaskah="Laporan"
 *          referensi="LHI" kegiatanId={activity?.id} perihal="…" />
 *
 * DIPICU DARI MENU: halaman yang kepalanya padat mengelompokkan aksi
 * sekundernya ke dalam satu menu ⋮. Pasang komponen ini DI LUAR menu dengan
 * `tanpaTombol`, lalu panggil `mulai()` lewat ref dari butir menunya:
 *
 *   const bookingRef = useRef(null);
 *   <DropdownMenuItem onSelect={() => bookingRef.current?.mulai()}>…</…>
 *   <BookingNomorButton ref={bookingRef} tanpaTombol modul="pengadaan" … />
 *
 * DI LUAR menu, bukan di dalamnya: Radix MELEPAS isi `DropdownMenuContent`
 * dari DOM begitu menu tertutup. Komponen ini yang memiliki dialog booking,
 * jadi menaruhnya di dalam menu berarti dialognya ikut lenyap pada saat yang
 * sama butir menunya ditekan — dan tak ada apa pun yang muncul.
 */
const BookingNomorButton = React.forwardRef(function BookingNomorButton({
  modul = "umum", jenisNaskah = "Laporan", referensi = "",
  kegiatanId = "", perihal = "", size = "sm", className = "",
  tanpaTombol = false,
}, ref) {
  const [buka, setBuka] = useState(false);
  const [form, setForm] = useState(null);
  const [pratinjau, setPratinjau] = useState(null);
  const [hasil, setHasil] = useState(null); // surat yang berhasil dibooking
  const [saving, setSaving] = useState(false);
  const [klasifikasi, setKlasifikasi] = useState([]); // master kode arsip
  const timer = useRef(null);

  const mulai = () => {
    setHasil(null);
    setForm({
      perihal: perihal || "", tujuan: "", jenis_naskah: jenisNaskah,
      modul, kegiatan_id: kegiatanId || "", referensi,
      kode_keamanan: "B", tanggal_surat: "", kode_klasifikasi: "",
      sisipan: false,
    });
    setBuka(true);
    // Master kode klasifikasi arsip ikut dimuat: tanpa ini dialog lintas-modul
    // ini SATU-SATUNYA jalur booking yang tak pernah bisa menyentuh klasifikasi
    // — kodenya terkunci "" dan pemakainya tak punya cara melihat, apalagi
    // mengubah, kode arsip yang tercetak pada nomor suratnya.
    axios.get(`${API}/persuratan/klasifikasi`)
      .then((r) => setKlasifikasi(r.data?.items || []))
      .catch(() => setKlasifikasi([]));
  };

  // Satu-satunya pintu imperatif: membuka dialog. Sengaja TIDAK membuka state
  // internal — pemanggil dari menu hanya perlu "mulai", bukan kuasa mengubah
  // form, pratinjau, atau hasil booking dari luar.
  useImperativeHandle(ref, () => ({ mulai }));

  useEffect(() => {
    if (!buka || !form) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          jenis_naskah: form.jenis_naskah || "",
          modul: form.modul || "",
          kode_klasifikasi: form.kode_klasifikasi || "",
          kode_keamanan: form.kode_keamanan || "B",
          tanggal_surat: form.tanggal_surat || "",
        });
        if (form.sisipan) params.append("sisipan", "true");
        const r = await axios.get(`${API}/persuratan/pratinjau-nomor?${params}`);
        setPratinjau(r.data);
      } catch { setPratinjau(null); }
    }, 300);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [buka, form]);

  const booking = async () => {
    if (!form?.perihal?.trim()) { toast.error("Perihal wajib diisi"); return; }
    if (form?.sisipan && !form?.tanggal_surat) {
      toast.error("Nomor sisipan membutuhkan Tanggal Surat (tanggal backdate)"); return;
    }
    setSaving(true);
    try {
      const r = await axios.post(`${API}/persuratan/keluar`, form);
      setHasil(r.data);
      toast.success(`Nomor dibooking: ${r.data.nomor}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal booking nomor");
    } finally {
      setSaving(false);
    }
  };

  const salin = async () => {
    try {
      await navigator.clipboard.writeText(hasil.nomor);
      toast.success("Nomor tersalin — tempel ke field nomor dokumen");
    } catch {
      toast.info(hasil.nomor, { duration: 10000 });
    }
  };

  return (
    <>
      {/* Tombol bawaan bisa DILEPAS (pemicunya pindah ke butir menu), tetapi
          dialog di bawah ini tetap milik komponen ini — tanpa titik sisip itu,
          satu-satunya jalan memasukkan booking ke menu adalah MENYALIN dialog
          beserta pratinjau nomor, master klasifikasi, dan aturan sisipannya;
          salinan kedua pasti menyimpang dari aslinya. */}
      {!tanpaTombol && (
        <Button variant="outline" size={size} className={`gap-1.5 ${className}`}
          onClick={mulai} title="Pesan nomor surat keluar untuk dokumen dari halaman ini"
          data-testid={`booking-nomor-btn-${modul}`}>
          <Ticket className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Booking Nomor</span>
        </Button>
      )}

      <Dialog open={buka} onOpenChange={(o) => { if (!o) setBuka(false); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{hasil ? "Nomor Berhasil Dibooking" : "Booking Nomor Surat"}</DialogTitle>
            <DialogDescription className="text-xs">
              {hasil
                ? "Nomor tercatat di buku agenda. Berita Acara kegiatan ini akan otomatis memakai nomor ini pada PDF-nya (bila field nomor BA kegiatan kosong); untuk dokumen lain salin manual. Sahkan di Registrasi Persuratan setelah ditandatangani."
                : `Modul ${modul} · ${jenisNaskah}${referensi ? ` · ${referensi}` : ""} — nomor tercatat di buku agenda dengan status dibooking.`}
            </DialogDescription>
          </DialogHeader>

          {hasil ? (
            <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-3 text-center space-y-2" data-testid="booking-nomor-hasil">
              <p className="font-mono text-base font-bold text-emerald-700 dark:text-emerald-400 break-all">{hasil.nomor}</p>
              <p className="text-[10px] text-muted-foreground">
                Agenda K-{noAgendaTampil(hasil.no_agenda, hasil.sisipan)}/{hasil.tahun} · status: dibooking
              </p>
              <Button size="sm" variant="outline" className="gap-1.5" onClick={salin} data-testid="booking-nomor-salin">
                <Copy className="w-3.5 h-3.5" />Salin Nomor
              </Button>
            </div>
          ) : form && (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1">Perihal *</label>
                <Input value={form.perihal} onChange={(e) => setForm((f) => ({ ...f, perihal: e.target.value }))}
                  placeholder="cth. Penyampaian LHI Semester I 2026" data-testid="booking-nomor-perihal" />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Kepada / Tujuan</label>
                  <Input value={form.tujuan} onChange={(e) => setForm((f) => ({ ...f, tujuan: e.target.value }))} />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1">Tanggal Surat</label>
                  <Input type="date" value={form.tanggal_surat}
                    onChange={(e) => setForm((f) => ({ ...f, tanggal_surat: e.target.value }))} />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1">
                  Kode Klasifikasi Arsip
                </label>
                <Input value={form.kode_klasifikasi} list="booking-klasifikasi-list"
                  onChange={(e) => setForm((f) => ({ ...f, kode_klasifikasi: e.target.value }))}
                  placeholder={pratinjau?.kode_klasifikasi
                    ? `otomatis: ${pratinjau.kode_klasifikasi}`
                    : "kosongkan = ikut aturan otomatis"}
                  className="font-mono" data-testid="booking-nomor-klasifikasi" />
                <datalist id="booking-klasifikasi-list">
                  {klasifikasi.map((k) => (
                    <option key={k.id} value={k.kode}>{k.uraian}</option>
                  ))}
                </datalist>
              </div>
              <label className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 cursor-pointer">
                <input type="checkbox" checked={!!form.sisipan}
                  onChange={(e) => setForm((f) => ({ ...f, sisipan: e.target.checked }))}
                  className="mt-0.5 w-4 h-4 accent-amber-600 min-w-0 min-h-0 flex-shrink-0"
                  data-testid="booking-nomor-sisipan" />
                <span className="text-[11px] leading-snug text-amber-800 dark:text-amber-300">
                  <b>Nomor sisipan (backdate)</b> — surat lupa dibooking: nomor menempel di belakang
                  nomor terakhir pada tanggal itu (005 → <span className="font-mono">005.01</span>).
                  Wajib mengisi Tanggal Surat.
                </span>
              </label>
              {form.sisipan && pratinjau?.sisipan_galat && (
                <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2" data-testid="booking-nomor-sisipan-galat">
                  <p className="text-[11px] text-red-700 dark:text-red-400">{pratinjau.sisipan_galat}</p>
                </div>
              )}
              {pratinjau?.nomor && (
                <div className="rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-3 py-2" data-testid="booking-nomor-pratinjau">
                  <p className="text-[10px] text-muted-foreground">Perkiraan nomor:</p>
                  <p className="font-mono text-sm font-bold text-cyan-700 dark:text-cyan-400 break-all">{pratinjau.nomor}</p>
                  <p className="text-[10px] text-muted-foreground mt-1"
                    data-testid="booking-nomor-sumber-klasifikasi">
                    Klasifikasi: {teksSumberKlasifikasi(pratinjau)}
                  </p>
                </div>
              )}
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setBuka(false)}>{hasil ? "Tutup" : "Batal"}</Button>
            {!hasil && (
              <Button onClick={booking} disabled={saving} data-testid="booking-nomor-simpan">
                {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Ticket className="w-4 h-4 mr-1.5" />}
                Booking Nomor
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
});

export default BookingNomorButton;
