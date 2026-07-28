import axios from "axios";
import { Building2, ChevronDown, Check, Globe, GripHorizontal } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  getSatkerAktif,
  isSuperAdminPusat,
  setSatkerAktif,
} from "@/lib/satkerAktif";
import {
  cukupUntukBuka,
  kemajuanTarik,
  majuTarik,
  redamTarik,
} from "@/lib/tarikBerat";

// Keadaan buka/tutup bertahan selama satu sesi tab. SENGAJA sessionStorage,
// bukan localStorage: tiap sesi baru mulai dari keadaan rapi (tertutup), tetapi
// operator yang memang sedang berganti-ganti satker tak dipaksa menarik ulang
// tiap pindah halaman.
const KUNCI_BUKA = "satker_bar_terbuka";

const API = process.env.REACT_APP_BACKEND_URL
  ? `${process.env.REACT_APP_BACKEND_URL}/api`
  : "/api";

/**
 * Bilah "Satker Aktif" — HANYA untuk super-admin pusat.
 *
 * Super-admin tak terikat satker, sehingga tanpa pemilih ini setiap data yang
 * ia input tak jelas milik satker mana. Memilih Satker Aktif membuat SELURUH
 * aplikasi (lihat + input) berperilaku sebagai satker itu — data terisolasi,
 * tak tercampur. "Semua Satker" = tampilan lintas satker seperti biasa.
 *
 * Mengganti satker memuat ulang halaman: cara paling andal memastikan tak ada
 * sisa data satker lain yang menggantung di memori antar modul.
 */
export default function SatkerAktifBar({ user }) {
  const [daftar, setDaftar] = useState([]);
  const [aktif, setAktif] = useState(getSatkerAktif());
  const [buka, setBuka] = useState(false);
  const ref = useRef(null);

  // Bilah TERTUTUP secara bawaan — hanya menyisakan pita tipis berisi cap satker.
  const [terbuka, setTerbuka] = useState(() => {
    try {
      return sessionStorage.getItem(KUNCI_BUKA) === "1";
    } catch {
      return false;                       // storage diblokir → tetap rapi
    }
  });
  const [geser, setGeser] = useState(0);        // px TERLIHAT (sudah teredam)
  const [maju, setMaju] = useState(0);          // 0..1 kemajuan menuju ambang
  const tarikRef = useRef(null);

  const superAdmin = isSuperAdminPusat(user);

  useEffect(() => {
    try {
      sessionStorage.setItem(KUNCI_BUKA, terbuka ? "1" : "0");
    } catch { /* storage diblokir — keadaan cukup hidup di memori */ }
  }, [terbuka]);

  // ── Tarik berat ───────────────────────────────────────────────────────────
  // Pointer Events menyatukan tetikus, sentuh, dan pena dalam SATU jalur, jadi
  // "hanya lewat header, dan berat" berlaku sama di ketiganya tanpa cabang
  // kode terpisah yang gampang menyimpang satu sama lain.
  const mulaiTarik = useCallback((e) => {
    if (e.button !== undefined && e.button > 0) return;   // klik kanan/tengah
    try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch { /* abaikan */ }
    tarikRef.current = { y0: e.clientY, id: e.pointerId };
    setGeser(0);
    setMaju(0);
  }, []);

  const gerakTarik = useCallback((e) => {
    const t = tarikRef.current;
    if (!t || e.pointerId !== t.id) return;
    const m = majuTarik(e.clientY - t.y0, terbuka);
    setGeser(redamTarik(m));
    setMaju(kemajuanTarik(m));
  }, [terbuka]);

  const selesaiTarik = useCallback((e) => {
    const t = tarikRef.current;
    if (!t || e.pointerId !== t.id) return;
    const m = majuTarik(e.clientY - t.y0, terbuka);
    tarikRef.current = null;
    setGeser(0);
    setMaju(0);
    // Ambang dinilai dari jarak MENTAH, bukan yang teredam — yang harus
    // diusahakan adalah gerakannya, bukan hasil animasinya.
    if (cukupUntukBuka(m)) {
      setTerbuka((v) => !v);
      setBuka(false);
    }
  }, [terbuka]);

  const batalTarik = useCallback(() => {
    tarikRef.current = null;
    setGeser(0);
    setMaju(0);
  }, []);

  // Jalan pintas papan ketik. Menarik itu mustahil tanpa penunjuk, dan bilah
  // ini menentukan satker mana yang sedang aktif — menguncinya di balik gestur
  // saja berarti mengunci pengguna papan ketik keluar sepenuhnya. Enter/Space
  // tetap DISENGAJA (fokus dulu, baru tekan), jadi tak melunakkan tujuan
  // "tidak mudah terbuka"; yang dicegah adalah senggolan, bukan niat.
  const tombolTarik = useCallback((e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    setTerbuka((v) => !v);
    setBuka(false);
  }, []);

  useEffect(() => {
    if (!superAdmin) return;
    let batal = false;
    axios
      .get(`${API}/satker`)
      .then((r) => {
        if (batal) return;
        const items = (r.data?.items || []).filter((s) => s.kode_satker);
        setDaftar(items);
      })
      .catch(() => {});
    return () => {
      batal = true;
    };
  }, [superAdmin]);

  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setBuka(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  // Sinkron antar-tab (temuan tinjauan): bila satker aktif diganti di tab lain,
  // localStorage bersama sudah berubah sehingga tiap request tab INI ikut
  // ter-scope satker baru — tetapi bilah & data yang tampil masih satker lama
  // (menyesatkan). `storage` hanya menyala di tab LAIN; muat ulang agar seluruh
  // tampilan konsisten dengan scope yang benar-benar dikirim.
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key !== "satker_aktif") return;
      if ((e.newValue || "") !== (getSatkerAktif() || "")) return; // sudah sinkron
      if ((e.newValue || "") !== aktif) window.location.reload();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [aktif]);

  if (!superAdmin) return null;

  const pilih = (kode) => {
    setBuka(false);
    if (kode === aktif) return;
    setSatkerAktif(kode);
    setAktif(kode);
    // Muat ulang agar seluruh data ter-refetch dengan scope satker baru.
    window.location.reload();
  };

  const namaAktif = aktif
    ? daftar.find((s) => s.kode_satker === aktif)?.nama_satker || aktif
    : "Semua Satker";

  return (
    <div
      ref={ref}
      className="relative z-40 bg-indigo-600 text-white shadow-sm select-none"
      style={{ transform: `translateY(${geser}px)` }}
      data-testid="satker-aktif-bar"
      data-terbuka={terbuka ? "1" : "0"}
    >
      {/* HEADER = SATU-SATUNYA PEGANGAN.
          Penangan tarik menempel HANYA di sini, jadi menyeret di mana pun
          selain pita ini tak berpengaruh — sesuai permintaan "hanya bisa
          ditarik pada saat kursor di posisi header saja", dan berlaku sama di
          layar sentuh karena Pointer Events menyatukan keduanya.

          `touch-action: none` WAJIB pada pegangan: tanpanya peramban seluler
          menafsirkan usapan vertikal sebagai gulir halaman dan pointermove tak
          pernah sampai ke sini — gestur tariknya mati diam-diam di HP. Karena
          yang dimatikan hanya pita setinggi ~24 px, gulir halaman biasa tetap
          utuh di seluruh sisa layar. */}
      <div
        role="button"
        tabIndex={0}
        aria-expanded={terbuka}
        aria-label={terbuka
          ? "Tarik ke atas untuk menyembunyikan pemilih satker"
          : "Tarik ke bawah untuk menampilkan pemilih satker"}
        onPointerDown={mulaiTarik}
        onPointerMove={gerakTarik}
        onPointerUp={selesaiTarik}
        onPointerCancel={batalTarik}
        onKeyDown={tombolTarik}
        style={{ touchAction: "none" }}
        className="relative flex items-center justify-center gap-2 px-3 py-1
                   cursor-grab active:cursor-grabbing text-[11px]
                   focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
        data-testid="satker-aktif-pegangan"
      >
        <Building2 className="w-3 h-3 flex-shrink-0 opacity-90" />
        <span className="opacity-90 hidden sm:inline">Satker aktif:</span>
        <span className="font-semibold truncate max-w-[45vw]">{namaAktif}</span>
        <GripHorizontal
          className={`w-3.5 h-3.5 flex-shrink-0 opacity-60 transition-transform
                      ${terbuka ? "rotate-180" : ""}`}
        />
        {/* Umpan balik kemajuan. Tanpa ini redaman berbalik jadi kejam: operator
            menarik jauh, pita nyaris tak bergerak, lalu menyimpulkan bilahnya
            macet. Garis ini berkata "tarikanmu terbaca" tanpa meringankannya. */}
        <span
          className="absolute left-0 bottom-0 h-0.5 bg-white/80 transition-opacity"
          style={{ width: `${maju * 100}%`, opacity: maju > 0 ? 1 : 0 }}
          data-testid="satker-aktif-kemajuan"
        />
      </div>

      {/* Isi hanya ADA saat terbuka — bukan sekadar tersembunyi — supaya
          tombolnya tak bisa ditab/diklik sewaktu bilah sedang rapi. */}
      {terbuka && (
        <div className="flex items-center justify-center gap-2 px-3 pb-1.5 text-xs
                        border-t border-white/15 pt-1.5">
          <button
            type="button"
            onClick={() => setBuka((v) => !v)}
            className="inline-flex items-center gap-1 font-semibold rounded-md bg-white/15
                       hover:bg-white/25 px-2 py-0.5 max-w-[60vw] transition-colors"
            data-testid="satker-aktif-pilih"
          >
            <span className="truncate">{namaAktif}</span>
            <ChevronDown className="w-3.5 h-3.5 flex-shrink-0" />
          </button>
        </div>
      )}

      {buka && terbuka && (
        <div
          className="absolute top-full mt-1 left-1/2 -translate-x-1/2 w-64 max-h-72 overflow-y-auto
                     rounded-lg border border-border bg-card text-foreground shadow-lg py-1"
        >
          <button
            type="button"
            onClick={() => pilih("")}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-muted"
            data-testid="satker-aktif-semua"
          >
            <Globe className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
            <span className="flex-1">Semua Satker (lintas)</span>
            {!aktif && <Check className="w-3.5 h-3.5 text-indigo-600 flex-shrink-0" />}
          </button>
          <div className="my-1 border-t border-border" />
          {daftar.length === 0 ? (
            <p className="px-3 py-2 text-[11px] text-muted-foreground">
              Belum ada satker di Master Satker.
            </p>
          ) : (
            daftar.map((s) => (
              <button
                key={s.kode_satker}
                type="button"
                onClick={() => pilih(s.kode_satker)}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-muted"
                data-testid={`satker-aktif-opsi-${s.kode_satker}`}
              >
                <Building2 className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                <span className="flex-1 min-w-0">
                  <span className="block truncate">{s.nama_satker || s.kode_satker}</span>
                  <span className="block font-mono text-[10px] text-muted-foreground">
                    {s.kode_satker}
                  </span>
                </span>
                {aktif === s.kode_satker && (
                  <Check className="w-3.5 h-3.5 text-indigo-600 flex-shrink-0" />
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
