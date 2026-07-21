import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { IdCard, Loader2 } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Dialog "Tap Kartu" (UID e-KTP / kartu NFC) — komponen BERSAMA lintas modul.
 *
 * Jalur baca (riset #489):
 * 1. UTAMA — pembaca NFC USB mode keyboard (keyboard-wedge, umum & murah):
 *    mengetik UID + Enter ke input yang selalu di-fokus ulang di dialog ini.
 *    Jalan di semua perangkat/browser (desktop, laptop, HP via OTG).
 * 2. Web NFC (Android Chrome) — peningkatan progresif; e-KTP umumnya BUKAN
 *    tag NDEF sehingga sering tak terbaca via HP — jangan diandalkan.
 * 3. Cadangan — ketik UID manual lalu Enter.
 *
 * Mode:
 * - "identifikasi" (default): UID → POST /pegawai/kartu/identifikasi →
 *   `onPegawai(pegawai)` (auto-isi form mana pun).
 * - "raw": UID mentah diserahkan ke `onUid(uid)` (dipakai PENDAFTARAN kartu
 *   di Master Pegawai — server yang menyimpan hash-nya).
 */
export default function KartuTapDialog({
  open, onOpenChange, mode = "identifikasi", onPegawai, onUid, judul,
}) {
  const [nilai, setNilai] = useState("");
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState("");
  const inputRef = useRef(null);
  const sibukRef = useRef(false);

  // Fokus ulang berkala supaya keystroke reader selalu jatuh ke input ini
  // (reader wedge mengetik ke elemen yang sedang fokus).
  useEffect(() => {
    if (!open) { setNilai(""); setGalat(""); return undefined; }
    const t = setInterval(() => {
      if (document.activeElement !== inputRef.current) inputRef.current?.focus();
    }, 600);
    return () => clearInterval(t);
  }, [open]);

  const kirim = async (uidRaw) => {
    const uid = String(uidRaw || "").trim();
    if (!uid || sibukRef.current) return;
    if (uid.replace(/[\s:.\-]/g, "").length < 6) {
      setGalat("UID terlalu pendek — tap kartu di pembaca, atau ketik UID lengkap lalu Enter.");
      setNilai("");
      return;
    }
    setGalat("");
    sibukRef.current = true;
    setSibuk(true);
    try {
      if (mode === "raw") {
        onUid?.(uid);
        onOpenChange?.(false);
        return;
      }
      const r = await axios.post(`${API}/pegawai/kartu/identifikasi`, { uid });
      const p = r.data?.pegawai;
      toast.success(`Kartu dikenali: ${p?.nama || "-"}`);
      onPegawai?.(p);
      onOpenChange?.(false);
    } catch (err) {
      const msg = err?.response?.data?.detail;
      setGalat(typeof msg === "string" && msg
        ? msg : "Gagal membaca kartu — periksa koneksi lalu coba lagi");
    } finally {
      sibukRef.current = false;
      setSibuk(false);
      setNilai("");
    }
  };

  // Web NFC bila tersedia (Android Chrome) — best-effort saja.
  useEffect(() => {
    if (!open || typeof window === "undefined" || !("NDEFReader" in window)) return undefined;
    const ctrl = new AbortController();
    (async () => {
      try {
        const reader = new window.NDEFReader();
        await reader.scan({ signal: ctrl.signal });
        reader.addEventListener("reading", (e) => {
          if (e.serialNumber) kirim(e.serialNumber);
        }, { signal: ctrl.signal });
      } catch { /* izin ditolak / tak didukung — jalur wedge tetap jalan */ }
    })();
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm" data-testid="kartu-tap-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <IdCard className="w-5 h-5 text-blue-600" />
            {judul || (mode === "raw" ? "Tap Kartu untuk Didaftarkan" : "Tap Kartu Pegawai")}
          </DialogTitle>
          <DialogDescription>
            Tempelkan e-KTP / kartu NFC pada pembaca kartu — UID terisi
            otomatis. Bisa juga ketik UID manual lalu tekan Enter.
          </DialogDescription>
        </DialogHeader>
        <div className="rounded-xl border-2 border-dashed border-blue-300 dark:border-blue-700 bg-blue-50/50 dark:bg-blue-900/20 p-4 text-center space-y-2">
          {sibuk
            ? <Loader2 className="w-8 h-8 mx-auto animate-spin text-blue-600" />
            : <IdCard className="w-8 h-8 mx-auto text-blue-500" />}
          <Input
            ref={inputRef}
            autoFocus
            value={nilai}
            onChange={(e) => setNilai(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); kirim(nilai); } }}
            placeholder="Menunggu tap kartu…"
            className="text-center font-mono"
            autoComplete="off"
            data-testid="kartu-tap-input"
          />
          <p className="text-[11px] text-muted-foreground">
            Pembaca NFC USB (mode keyboard) akan mengetikkan UID + Enter secara otomatis.
          </p>
        </div>
        {galat && (
          <p className="text-xs text-red-600 dark:text-red-400" data-testid="kartu-tap-galat">{galat}</p>
        )}
        <p className="text-[10px] text-muted-foreground leading-relaxed">
          Keamanan: aplikasi hanya menyimpan sidik (hash) UID — bukan UID asli
          — dan TIDAK membaca data kependudukan di chip. Tap kartu berperan
          sebagai identifikasi cepat, bukan pengganti tanda tangan elektronik.
        </p>
      </DialogContent>
    </Dialog>
  );
}
