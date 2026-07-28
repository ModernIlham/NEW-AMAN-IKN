import axios from "axios";
import { Building2, Check, Globe, GripHorizontal } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  getSatkerAktif,
  isSuperAdminPusat,
  setSatkerAktif,
} from "@/lib/satkerAktif";
import {
  TAHAP_CAP,
  TAHAP_DAFTAR,
  TAHAP_TERSEMBUNYI,
  geserTahap,
  kemajuanTarik,
  majuTahap,
  tahapSetelahTarik,
} from "@/lib/tarikBerat";
import { TENGGAT_BAKA, muatAndal } from "@/lib/muatAndal";

// Tahap tirai bertahan selama satu sesi tab. SENGAJA sessionStorage, bukan
// localStorage: tiap sesi baru mulai dari keadaan rapi (tersembunyi), tetapi
// operator yang memang sedang berganti-ganti satker tak dipaksa menarik ulang
// tiap pindah halaman.
const KUNCI_TAHAP = "satker_bar_tahap";

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
 * BENTUKNYA TIRAI, BUKAN BILAH TETAP. Sebelumnya cap satker selalu memakan satu
 * baris penuh di puncak SETIAP halaman, dan karena ia ikut mengalir bersama
 * dokumen, membukanya di halaman yang sudah tergulir menuntut operator
 * menggulir NAIK dulu — persis kebalikan dari gerakan yang wajar untuk
 * "menurunkan" sesuatu dari tepi atas layar.
 *
 * Kini ia melayang (fixed) di tepi atas dan tersembunyi: yang tersisa hanya
 * pegangan setipis rambut. Menarik TURUN memunculkan capnya; menarik turun
 * sekali lagi memunculkan daftar satker. Tiap lapis punya usahanya sendiri, dan
 * karena daftar itu ikut turun bersama tirainya, ia tak mungkin lagi tertutup
 * header halaman — dulu daftar itu digantung `absolute` di bawah bilah yang
 * ikut tergulir, sehingga sering terpotong.
 *
 * Mengganti satker memuat ulang halaman: cara paling andal memastikan tak ada
 * sisa data satker lain yang menggantung di memori antar modul.
 */
export default function SatkerAktifBar({ user }) {
  const [daftar, setDaftar] = useState([]);
  const [gagalDaftar, setGagalDaftar] = useState(false);
  const [aktif, setAktif] = useState(getSatkerAktif());
  const ref = useRef(null);

  const [tahap, setTahap] = useState(() => {
    try {
      const n = Number(sessionStorage.getItem(KUNCI_TAHAP));
      return n === TAHAP_CAP || n === TAHAP_DAFTAR ? n : TAHAP_TERSEMBUNYI;
    } catch {
      return TAHAP_TERSEMBUNYI;             // storage diblokir → tetap rapi
    }
  });
  const [geser, setGeser] = useState(0);        // px TERLIHAT (sudah teredam)
  const [maju, setMaju] = useState(0);          // 0..1 kemajuan menuju ambang
  const tarikRef = useRef(null);

  const superAdmin = isSuperAdminPusat(user);
  const terbuka = tahap > TAHAP_TERSEMBUNYI;

  useEffect(() => {
    try {
      sessionStorage.setItem(KUNCI_TAHAP, String(tahap));
    } catch { /* storage diblokir — keadaan cukup hidup di memori */ }
  }, [tahap]);

  // ── Tarik berat ───────────────────────────────────────────────────────────
  // Pointer Events menyatukan tetikus, sentuh, dan pena dalam SATU jalur, jadi
  // "hanya lewat pegangan, dan berat" berlaku sama di ketiganya tanpa cabang
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
    const dy = e.clientY - t.y0;
    setGeser(geserTahap(dy, tahap));
    setMaju(kemajuanTarik(majuTahap(dy, tahap)));
  }, [tahap]);

  const selesaiTarik = useCallback((e) => {
    const t = tarikRef.current;
    if (!t || e.pointerId !== t.id) return;
    const dy = e.clientY - t.y0;
    tarikRef.current = null;
    setGeser(0);
    setMaju(0);
    // Ambang dinilai dari jarak MENTAH, bukan yang teredam — yang harus
    // diusahakan adalah gerakannya, bukan hasil animasinya.
    setTahap((lama) => tahapSetelahTarik(lama, dy));
  }, []);

  const batalTarik = useCallback(() => {
    tarikRef.current = null;
    setGeser(0);
    setMaju(0);
  }, []);

  // Jalan pintas papan ketik. Menarik itu mustahil tanpa penunjuk, dan bilah
  // ini menentukan satker mana yang sedang aktif — menguncinya di balik gestur
  // saja berarti mengunci pengguna papan ketik keluar sepenuhnya. Panah
  // atas/bawah memetakan arah yang sama dengan tarikannya; Enter/Space maju
  // satu tahap lalu berputar kembali ke tersembunyi dari ujung.
  const tombolTarik = useCallback((e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setTahap((v) => Math.min(TAHAP_DAFTAR, v + 1));
    } else if (e.key === "ArrowUp" || e.key === "Escape") {
      e.preventDefault();
      setTahap((v) => Math.max(TAHAP_TERSEMBUNYI, v - 1));
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setTahap((v) => (v >= TAHAP_DAFTAR ? TAHAP_TERSEMBUNYI : v + 1));
    }
  }, []);

  useEffect(() => {
    if (!superAdmin) return;
    let batal = false;
    // Kegagalan di sini dulu ditelan `catch(() => {})`, dan daftar kosong itu
    // dirender sebagai "Belum ada satker di Master Satker" — pernyataan yang
    // KELIRU dan menyesatkan: super-admin bisa menyimpulkan master satkernya
    // hilang, padahal jaringannya yang sedang buruk. Kini dibedakan.
    muatAndal(() => axios.get(`${API}/satker`, { timeout: TENGGAT_BAKA }))
      .then((r) => {
        if (batal) return;
        const items = (r.data?.items || []).filter((s) => s.kode_satker);
        setDaftar(items);
        setGagalDaftar(false);
      })
      .catch(() => { if (!batal) setGagalDaftar(true); });
    return () => {
      batal = true;
    };
  }, [superAdmin]);

  // Ketuk di luar tirai → kembali tersembunyi. Tirai ini MELAYANG di atas
  // halaman, jadi membiarkannya terbuka berarti ia terus menutupi isi layar.
  useEffect(() => {
    if (!terbuka) return undefined;
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setTahap(TAHAP_TERSEMBUNYI);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("touchstart", onDoc, { passive: true });
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("touchstart", onDoc);
    };
  }, [terbuka]);

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
    setTahap(TAHAP_TERSEMBUNYI);
    if (kode === aktif) return;
    setSatkerAktif(kode);
    setAktif(kode);
    // Muat ulang agar seluruh data ter-refetch dengan scope satker baru.
    window.location.reload();
  };

  const namaAktif = aktif
    ? daftar.find((s) => s.kode_satker === aktif)?.nama_satker || aktif
    : "Semua Satker";

  const labelTarik = tahap === TAHAP_TERSEMBUNYI
    ? "Tarik ke bawah untuk menampilkan satker aktif"
    : tahap === TAHAP_CAP
      ? "Tarik ke bawah lagi untuk memilih satker, atau ke atas untuk menyembunyikan"
      : "Tarik ke atas untuk menutup daftar satker";

  return (
    <>
      {/* Tirai MELAYANG, tidak ikut mengalir. Inilah yang membuat pegangannya
          selalu ada di tepi atas layar tanpa perlu menggulir halaman naik dulu.
          Ruang yang dulu ia rampas dari setiap halaman kini kembali utuh. */}
      <div
        ref={ref}
        className="fixed top-0 left-0 right-0 z-[60] select-none pointer-events-none"
        data-testid="satker-aktif-bar"
        data-tahap={tahap}
      >
        <div
          className="pointer-events-auto bg-indigo-600 text-white shadow-lg
                     transition-[max-height] duration-200 ease-out overflow-hidden"
          style={{
            transform: `translateY(${geser}px)`,
            // max-height, bukan display: isinya tetap ada di DOM saat menutup
            // sehingga peralihannya teranimasi, bukan berkedip putus.
            maxHeight: tahap === TAHAP_DAFTAR ? "70vh" : tahap === TAHAP_CAP ? "3rem" : "0px",
          }}
        >
          {/* CAP — lapis pertama. */}
          <div className="flex items-center justify-center gap-2 px-3 py-1.5 text-[11px]">
            <Building2 className="w-3 h-3 flex-shrink-0 opacity-90" />
            <span className="opacity-90 hidden sm:inline">Satker aktif:</span>
            <span className="font-semibold truncate max-w-[55vw]">{namaAktif}</span>
          </div>

          {/* DAFTAR — lapis kedua, IKUT TURUN bersama tirai.
              Dulu ini digantung `absolute` di bawah bilah yang ikut tergulir,
              jadi di layar sempit ia rutin tertutup header halaman. Sebagai
              bagian dari tirai, tak ada lagi yang bisa menutupinya. */}
          {tahap >= TAHAP_DAFTAR && (
            <div className="border-t border-white/15 bg-card text-foreground
                            max-h-[calc(70vh-3rem)] overflow-y-auto py-1"
                 data-testid="satker-aktif-daftar">
              <button
                type="button"
                onClick={() => pilih("")}
                className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-muted"
                data-testid="satker-aktif-semua"
              >
                <Globe className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                <span className="flex-1 text-sm">Semua Satker (lintas)</span>
                {!aktif && <Check className="w-4 h-4 text-indigo-600 flex-shrink-0" />}
              </button>
              <div className="my-1 border-t border-border" />
              {daftar.length === 0 ? (
                <p className="px-3 py-2 text-[11px] text-muted-foreground">
                  {gagalDaftar
                    ? "Daftar satker gagal dimuat — periksa sinyal lalu tarik ulang tirai ini."
                    : "Belum ada satker di Master Satker."}
                </p>
              ) : (
                daftar.map((s) => (
                  <button
                    key={s.kode_satker}
                    type="button"
                    onClick={() => pilih(s.kode_satker)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-muted"
                    data-testid={`satker-aktif-opsi-${s.kode_satker}`}
                  >
                    <Building2 className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                    <span className="flex-1 min-w-0">
                      <span className="block truncate text-sm">{s.nama_satker || s.kode_satker}</span>
                      <span className="block font-mono text-[10px] text-muted-foreground">
                        {s.kode_satker}
                      </span>
                    </span>
                    {aktif === s.kode_satker && (
                      <Check className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                    )}
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        {/* PEGANGAN — SATU-SATUNYA tempat tirai bisa ditarik.
            Sengaja sesempit ini: ia melayang di atas halaman, jadi apa pun yang
            lebih lebar akan mencuri ketukan dari isi di bawahnya. Lebarnya
            ~5,5 rem di tengah — cukup untuk ibu jari, terlalu kecil untuk
            tersenggol.

            `touch-action: none` WAJIB: tanpanya peramban seluler menafsirkan
            usapan vertikal sebagai gulir halaman dan pointermove tak pernah
            sampai ke sini — gesturnya mati diam-diam di HP. */}
        <div className="flex justify-center pointer-events-none">
          <div
            role="button"
            tabIndex={0}
            aria-expanded={terbuka}
            aria-label={labelTarik}
            title={labelTarik}
            onPointerDown={mulaiTarik}
            onPointerMove={gerakTarik}
            onPointerUp={selesaiTarik}
            onPointerCancel={batalTarik}
            onKeyDown={tombolTarik}
            style={{ touchAction: "none", transform: `translateY(${geser}px)` }}
            className="pointer-events-auto relative w-[5.5rem] h-5 -mt-px flex items-end justify-center
                       rounded-b-xl bg-indigo-600 text-white shadow-md
                       cursor-grab active:cursor-grabbing min-w-0 min-h-0
                       focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
            data-testid="satker-aktif-pegangan"
          >
            <GripHorizontal
              className={`w-4 h-4 mb-0.5 opacity-70 transition-transform
                          ${terbuka ? "rotate-180" : ""}`}
            />
            {/* Umpan balik kemajuan. Tanpa ini redaman berbalik jadi kejam:
                operator menarik jauh, tirai nyaris tak bergerak, lalu
                menyimpulkan bilahnya macet. Garis ini berkata "tarikanmu
                terbaca" tanpa meringankannya. */}
            <span
              className="absolute left-0 bottom-0 h-0.5 bg-white transition-opacity"
              style={{ width: `${maju * 100}%`, opacity: maju > 0 ? 1 : 0 }}
              data-testid="satker-aktif-kemajuan"
            />
          </div>
        </div>
      </div>
    </>
  );
}
