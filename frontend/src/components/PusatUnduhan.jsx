/**
 * PUSAT UNDUHAN — log unduhan sebagai GELEMBUNG MENGAMBANG global.
 *
 * Log semua unduhan berat yang diproses sebagai job latar server
 * (lib/pusatUnduhan.js): tiap entri tampil dengan progres tersendiri;
 * begitu selesai, hasilnya bisa diunduh KAPAN SAJA dari sini tanpa
 * men-generate ulang (tersimpan 30 hari di server, lalu terhapus otomatis).
 *
 * Pintu masuknya berupa gelembung bulat yang menempel & menyelinap di dinding
 * kiri/kanan layar (lihat GelembungMengambang) — bebas digeser, dibuka dengan
 * ketukan atau swipe ke arah tengah, sama di HP, tablet, maupun desktop.
 *
 * Pola muat data mengikuti BackgroundTaskBar (widget backup): polling adaptif
 * (2,5 dtk saat ada job berjalan; 15 dtk saat panel terbuka; berhenti saat
 * tertutup tanpa job), berhenti total setelah 401, unduh via anchor native
 * ber-?token= agar file besar andal melewati ingress.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import axios from "axios";
import {
  AlertCircle, CheckCircle2, Clock, Download, FolderDown, Loader2,
  RefreshCw, Trash2, X,
} from "lucide-react";
import { toast } from "sonner";

import GelembungMengambang from "./GelembungMengambang";
import { authMediaUrl } from "../lib/mediaUrl";
import { EVENT_UNDUHAN_BARU, mulaiUnduhanPusat } from "../lib/pusatUnduhan";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function formatUkuran(bytes) {
  const kb = (bytes || 0) / 1024;
  if (kb < 1024) return `${Math.max(1, Math.round(kb))} KB`;
  return `${(kb / 1024).toFixed(1).replace(".", ",")} MB`;
}

function formatTanggal(nilai) {
  try {
    return new Date(nilai).toLocaleDateString("id-ID",
      { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return "";
  }
}

function unduhNative(url) {
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export default function PusatUnduhan({ aktif = true }) {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [versi, setVersi] = useState(0);      // dinaikkan tiap unduhan baru
  const autoRef = useRef(new Set());          // id yang menunggu auto-unduh
  const stop401Ref = useRef(false);
  const timerRef = useRef(null);

  useEffect(() => { stop401Ref.current = false; }, [aktif]);

  // Identitas stabil: dipakai gelembung sebagai dependensi efek geser —
  // fungsi baru tiap render akan memasang-lepas pendengar pointer terus-menerus.
  const ubahTerbuka = useCallback((nilai) => {
    setOpen(nilai);
    if (nilai) setVersi((v) => v + 1);   // bangunkan polling saat dibuka
  }, []);

  const muat = useCallback(async () => {
    if (stop401Ref.current) return null;
    try {
      const r = await axios.get(`${API}/unduhan`);
      const list = r.data?.items || [];
      setItems(list);
      list.forEach((it) => {
        if (!autoRef.current.has(it.unduhan_id)) return;
        if (it.status === "done") {
          autoRef.current.delete(it.unduhan_id);
          unduhNative(authMediaUrl(`${API}/unduhan/${it.unduhan_id}/file`));
          toast.success(`${it.label}: selesai — file diunduh`);
        } else if (it.status === "error") {
          autoRef.current.delete(it.unduhan_id);
          toast.error(`${it.label}: ${it.error_message || "gagal"}`);
        }
      });
      return list;
    } catch (e) {
      if (e?.response?.status === 401) stop401Ref.current = true;
      return null;
    }
  }, []);

  // Unduhan baru (dari tombol mana pun / fallback timeout): buka panel,
  // tandai auto-unduh, dan bangunkan polling.
  useEffect(() => {
    const onBaru = (e) => {
      const id = e?.detail?.id;
      if (id) autoRef.current.add(id);
      setOpen(true);
      setVersi((v) => v + 1);
    };
    window.addEventListener(EVENT_UNDUHAN_BARU, onBaru);
    return () => window.removeEventListener(EVENT_UNDUHAN_BARU, onBaru);
  }, []);

  // Polling adaptif — hemat: cepat hanya saat ada job berjalan.
  useEffect(() => {
    if (!aktif) return undefined;
    let hidup = true;
    const tick = async () => {
      if (!hidup) return;
      const list = await muat();
      if (list === null) {
        // Gagal fetch (BUKAN 401): jangan berhenti permanen — job yang sedang
        // berjalan tetap perlu dipantau agar auto-unduh saat selesai tak hilang.
        if (!stop401Ref.current) timerRef.current = setTimeout(tick, 15000);
        return;
      }
      const adaAktif = list.some(
        (i) => i.status === "queued" || i.status === "running");
      const delay = adaAktif ? 2500 : (open ? 15000 : null);
      if (delay) timerRef.current = setTimeout(tick, delay);
    };
    tick();
    return () => { hidup = false; clearTimeout(timerRef.current); };
  }, [aktif, open, versi, muat]);

  const hapus = async (it) => {
    try {
      await axios.delete(`${API}/unduhan/${it.unduhan_id}`);
      setItems((prev) => prev.filter((x) => x.unduhan_id !== it.unduhan_id));
    } catch {
      toast.error("Gagal menghapus entri unduhan");
    }
  };

  const cobaLagi = async (it) => {
    try {
      await mulaiUnduhanPusat(
        { path: it.path, namaFile: it.nama_file, label: it.label });
      await axios.delete(`${API}/unduhan/${it.unduhan_id}`).catch(() => {});
    } catch (e) {
      toast.error(`Gagal memulai ulang: ${
        e?.response?.data?.detail || e.message}`);
    }
  };

  if (!aktif) return null;
  const jumlahAktif = items.filter(
    (i) => i.status === "queued" || i.status === "running").length;

  // Belum pernah ada unduhan: layar tetap bersih — gelembung baru muncul
  // begitu ada entri (log unduhan bertahan 30 hari, jadi sekali dipakai ia
  // selalu tersedia).
  if (items.length === 0 && !open) return null;

  const panel = (
    <div data-testid="pusat-unduhan-panel"
      className="w-80 max-w-[calc(100vw-1.25rem)] bg-card border border-border rounded-xl shadow-2xl overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-border bg-muted/50">
        <FolderDown className="w-4 h-4 text-blue-500 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground leading-tight">Pusat Unduhan</p>
          <p className="text-[10px] text-muted-foreground leading-tight">
            Hasil tersimpan 30 hari — unduh ulang tanpa proses ulang
          </p>
        </div>
        <button type="button" onClick={() => setOpen(false)}
          data-testid="pusat-unduhan-tutup" aria-label="Tutup Pusat Unduhan"
          className="min-w-0 min-h-0 h-7 w-7 flex items-center justify-center rounded hover:bg-muted text-muted-foreground">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="max-h-72 overflow-y-auto divide-y divide-border">
        {items.length === 0 && (
          <p className="px-3 py-6 text-xs text-muted-foreground text-center">
            Belum ada unduhan. Unduhan laporan besar akan otomatis
            berpindah ke sini bila butuh waktu lama.
          </p>
        )}
        {items.map((it) => (
          <div key={it.unduhan_id} className="px-3 py-2.5"
            data-testid={`pusat-unduhan-item-${it.unduhan_id}`}>
            <div className="flex items-center gap-2">
              {it.status === "done" && <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />}
              {it.status === "error" && <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />}
              {it.status === "running" && <Loader2 className="w-4 h-4 animate-spin text-blue-500 shrink-0" />}
              {it.status === "queued" && <Clock className="w-4 h-4 text-amber-500 shrink-0" />}
              <p className="flex-1 min-w-0 text-xs font-semibold text-foreground truncate"
                title={it.nama_file}>{it.label || it.nama_file}</p>
              <div className="flex items-center gap-0.5 shrink-0">
                {it.status === "done" && (
                  <button type="button"
                    onClick={() => unduhNative(authMediaUrl(`${API}/unduhan/${it.unduhan_id}/file`))}
                    title="Unduh" aria-label={`Unduh ${it.label || it.nama_file}`}
                    className="min-w-0 min-h-0 h-7 w-7 flex items-center justify-center rounded hover:bg-blue-50 dark:hover:bg-blue-900/30">
                    <Download className="w-3.5 h-3.5 text-blue-500" />
                  </button>
                )}
                {it.status === "error" && it.path && (
                  <button type="button" onClick={() => cobaLagi(it)}
                    title="Coba lagi" aria-label={`Coba lagi ${it.label || it.nama_file}`}
                    className="min-w-0 min-h-0 h-7 w-7 flex items-center justify-center rounded hover:bg-amber-50 dark:hover:bg-amber-900/30">
                    <RefreshCw className="w-3.5 h-3.5 text-amber-500" />
                  </button>
                )}
                {(it.status === "done" || it.status === "error") && (
                  <button type="button" onClick={() => hapus(it)}
                    title="Hapus" aria-label={`Hapus ${it.label || it.nama_file}`}
                    className="min-w-0 min-h-0 h-7 w-7 flex items-center justify-center rounded hover:bg-red-50 dark:hover:bg-red-900/30">
                    <Trash2 className="w-3.5 h-3.5 text-red-500" />
                  </button>
                )}
              </div>
            </div>
            <p className={`mt-0.5 pl-6 text-[10px] leading-tight truncate ${
              it.status === "error" ? "text-red-500" : "text-muted-foreground"}`}>
              {it.status === "queued" && (it.message || "Menunggu giliran")}
              {it.status === "running" && (it.message || "Diproses di server…")}
              {it.status === "done" && `${formatUkuran(it.ukuran)} · tersimpan s.d. ${formatTanggal(it.hapus_pada)}`}
              {it.status === "error" && (it.error_message || "Gagal")}
            </p>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <GelembungMengambang
      idPenyimpanan="aman_gelembung_unduhan"
      terbuka={open}
      onTerbukaChange={ubahTerbuka}
      label="Pusat Unduhan"
      lencana={jumlahAktif}
      testId="pusat-unduhan"
      panel={panel}
    >
      {jumlahAktif > 0
        ? <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
        : <FolderDown className="w-6 h-6 text-blue-500" />}
    </GelembungMengambang>
  );
}
