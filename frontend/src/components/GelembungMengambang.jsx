/**
 * GELEMBUNG MENGAMBANG — tombol bulat melayang gaya pintasan "chat head".
 *
 * Perilaku identik di HP, tablet, dan desktop karena SEMUA masukan lewat satu
 * jalur Pointer Events (jari, pena, dan tetikus sama saja):
 *
 * - Menempel di dinding kiri/kanan layar dan MENYELINAP separuh ke balik
 *   dinding saat diam, jadi tidak menutupi konten halaman.
 * - Bebas digeser ke mana pun; begitu dilepas ia melompat ke dinding terdekat
 *   (kiri atau kanan, mengikuti posisi terakhir jari).
 * - Diketuk → panel terbuka. Digeser ke arah tengah layar (swipe) → panel juga
 *   terbuka, tanpa perlu ketukan terpisah.
 * - Saat panel terbuka gelembungnya menghilang; menutup panel mengembalikannya
 *   ke dinding lalu ia menyelinap lagi setelah beberapa detik diam.
 *
 * Posisi disimpan di localStorage sebagai SISI + RASIO tinggi (bukan piksel)
 * supaya tetap benar setelah layar diputar atau jendela diubah ukurannya —
 * inilah kenapa satu setelan cukup untuk semua ukuran layar.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

const UKURAN = 56;            // diameter gelembung (px)
const MARGIN = 10;            // jarak dari tepi layar saat menempel
const AMBANG_KETUKAN = 8;     // gerak < ini dianggap ketukan, bukan geseran
/* Swipe pembuka HARUS dibedakan dari geser-pindah: menarik gelembung dari
   dinding kanan jauh ke kiri adalah MEMINDAHKAN, bukan membuka. Karena itu
   swipe dibatasi tiga-tiganya — sentakan pendek, mendatar, dan cepat. */
const SWIPE_MIN = 48;         // tarikan ke dalam minimal agar dianggap swipe
const SWIPE_MAKS = 200;       // lebih jauh dari ini = pengguna memindahkan
const SWIPE_DURASI = 500;     // ms — sentakan, bukan seretan pelan
const JEDA_SELINAP = 2200;    // diam selama ini → menyelinap ke balik dinding
const PORSI_SELINAP = 0.42;   // bagian badan yang masuk ke balik dinding

const jepit = (n, min, max) => Math.min(Math.max(n, min), max);

function bacaPosisi(kunci) {
  try {
    const v = JSON.parse(window.localStorage.getItem(kunci) || "null");
    if (v && (v.sisi === "kiri" || v.sisi === "kanan") && Number.isFinite(v.rasioY)) {
      return { sisi: v.sisi, rasioY: jepit(v.rasioY, 0, 1) };
    }
  } catch {
    // localStorage bisa diblokir (mode privat) — jatuh ke posisi default.
  }
  return { sisi: "kanan", rasioY: 0.58 };
}

function simpanPosisi(kunci, pos) {
  try {
    window.localStorage.setItem(kunci, JSON.stringify(pos));
  } catch {
    // Penyimpanan penuh/diblokir: posisi tetap berlaku untuk sesi ini.
  }
}

export default function GelembungMengambang({
  idPenyimpanan,
  terbuka,
  onTerbukaChange,
  label,
  lencana = 0,
  panel,
  testId = "gelembung",
  children,
}) {
  const [posisi, setPosisi] = useState(() => bacaPosisi(idPenyimpanan));
  const [seret, setSeret] = useState(null);   // {x,y} kiri-atas selama digeser
  const [selinap, setSelinap] = useState(true);
  const [layar, setLayar] = useState(
    () => ({ w: window.innerWidth, h: window.innerHeight }));
  const [panelAtas, setPanelAtas] = useState(MARGIN);

  const seretRef = useRef(null);
  const layarRef = useRef(layar);
  const posisiRef = useRef(posisi);
  const terbukaRef = useRef(terbuka);
  const tombolRef = useRef(null);
  const panelRef = useRef(null);
  const jamRef = useRef(null);
  const abaikanKlikRef = useRef(false);
  const halusRef = useRef(
    !window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches);

  layarRef.current = layar;
  posisiRef.current = posisi;
  terbukaRef.current = terbuka;

  // Layar berubah ukuran/orientasi: hitung ulang: posisi disimpan sebagai
  // rasio, jadi gelembung tetap di ketinggian yang sama secara proporsional.
  useEffect(() => {
    const ubah = () => setLayar({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", ubah);
    window.addEventListener("orientationchange", ubah);
    return () => {
      window.removeEventListener("resize", ubah);
      window.removeEventListener("orientationchange", ubah);
    };
  }, []);

  const simpan = useCallback((p) => {
    setPosisi(p);
    simpanPosisi(idPenyimpanan, p);
  }, [idPenyimpanan]);

  const tundaSelinap = useCallback(() => {
    clearTimeout(jamRef.current);
    setSelinap(false);
    jamRef.current = setTimeout(() => setSelinap(true), JEDA_SELINAP);
  }, []);

  useEffect(() => () => clearTimeout(jamRef.current), []);

  useEffect(() => {
    if (terbuka) {
      clearTimeout(jamRef.current);
      setSelinap(false);
    } else {
      tundaSelinap();
    }
  }, [terbuka, tundaSelinap]);

  const mulaiSeret = useCallback((e) => {
    if (e.button != null && e.button > 0) return;   // abaikan klik kanan/tengah
    const kotak = e.currentTarget.getBoundingClientRect();
    seretRef.current = {
      dx: e.clientX - kotak.left, dy: e.clientY - kotak.top,
      x0: e.clientX, y0: e.clientY, t0: Date.now(),
      akhirX: e.clientX, akhirY: e.clientY, jauh: 0,
    };
    clearTimeout(jamRef.current);
    abaikanKlikRef.current = false;
    setSelinap(false);
    setSeret({ x: kotak.left, y: kotak.top });
  }, []);

  // Buka/tutup ditangani di onClick — BUKAN di pointerup — supaya pengguna
  // keyboard (Tab lalu Enter/Spasi) juga bisa membukanya. Klik sintetis yang
  // menyusul sebuah geseran/swipe ditandai untuk diabaikan agar tidak
  // membatalkan aksi yang baru saja dilakukan.
  const klik = useCallback(() => {
    if (abaikanKlikRef.current) {
      abaikanKlikRef.current = false;
      return;
    }
    onTerbukaChange(!terbukaRef.current);
    tundaSelinap();
  }, [onTerbukaChange, tundaSelinap]);

  // Pendengar dipasang di window (bukan di tombol) supaya jari/kursor yang
  // keluar dari gelembung saat menggeser tidak memutus geseran.
  const sedangSeret = seret !== null;
  useEffect(() => {
    if (!sedangSeret) return undefined;

    const gerak = (e) => {
      const s = seretRef.current;
      if (!s) return;
      s.akhirX = e.clientX;
      s.akhirY = e.clientY;
      s.jauh = Math.max(s.jauh, Math.hypot(e.clientX - s.x0, e.clientY - s.y0));
      const { w, h } = layarRef.current;
      setSeret({
        x: jepit(e.clientX - s.dx, -UKURAN / 2, w - UKURAN / 2),
        y: jepit(e.clientY - s.dy, MARGIN, Math.max(MARGIN, h - UKURAN - MARGIN)),
      });
    };

    const lepas = () => {
      const s = seretRef.current;
      seretRef.current = null;
      setSeret(null);
      if (!s) return;

      const { w, h } = layarRef.current;
      const { sisi } = posisiRef.current;
      const atas = jepit(s.akhirY - s.dy, MARGIN, Math.max(MARGIN, h - UKURAN - MARGIN));
      const rasioY = h > UKURAN ? jepit(atas / (h - UKURAN), 0, 1) : 0;

      if (s.jauh < AMBANG_KETUKAN) {   // ketukan → biarkan onClick yang bekerja
        tundaSelinap();
        return;
      }
      // Geseran/swipe: telan klik sintetis yang menyusul. Bila peramban tak
      // mengirimkannya (pointer lepas di luar tombol), tanda ini luruh sendiri
      // agar tidak menelan ketukan berikutnya.
      abaikanKlikRef.current = true;
      setTimeout(() => { abaikanKlikRef.current = false; }, 400);

      const dx = s.akhirX - s.x0;
      const dy = s.akhirY - s.y0;
      const keDalam = sisi === "kanan" ? -dx : dx;   // menjauh dari dinding
      const mendatar = Math.abs(dx) > Math.abs(dy) * 1.2;
      const sentakan = Date.now() - s.t0 <= SWIPE_DURASI;
      if (!terbukaRef.current && mendatar && sentakan
          && keDalam >= SWIPE_MIN && keDalam <= SWIPE_MAKS) {
        // Sentakan pendek ke arah tengah layar = buka panel; gelembung TETAP
        // di dindingnya (tarikan sesaat tak boleh memindahkan sisi).
        simpan({ sisi, rasioY });
        onTerbukaChange(true);
        return;
      }

      const pusatX = s.akhirX - s.dx + UKURAN / 2;
      simpan({ sisi: pusatX < w / 2 ? "kiri" : "kanan", rasioY });
      tundaSelinap();
    };

    window.addEventListener("pointermove", gerak);
    window.addEventListener("pointerup", lepas);
    window.addEventListener("pointercancel", lepas);
    return () => {
      window.removeEventListener("pointermove", gerak);
      window.removeEventListener("pointerup", lepas);
      window.removeEventListener("pointercancel", lepas);
    };
  }, [sedangSeret, onTerbukaChange, tundaSelinap, simpan]);

  // Sentuhan di luar panel / Escape menutup panel — gelembung kembali menempel.
  useEffect(() => {
    if (!terbuka) return undefined;
    const diLuar = (e) => {
      if (panelRef.current?.contains(e.target)) return;
      if (tombolRef.current?.contains(e.target)) return;
      onTerbukaChange(false);
    };
    const tekanTuts = (e) => { if (e.key === "Escape") onTerbukaChange(false); };
    document.addEventListener("pointerdown", diLuar, true);
    document.addEventListener("keydown", tekanTuts);
    return () => {
      document.removeEventListener("pointerdown", diLuar, true);
      document.removeEventListener("keydown", tekanTuts);
    };
  }, [terbuka, onTerbukaChange]);

  // Panel dipusatkan pada ketinggian gelembung, lalu dijepit ke dalam layar
  // (di HP panel bisa lebih tinggi dari sisa ruang — jepitan mencegahnya
  // menggantung di luar viewport).
  useLayoutEffect(() => {
    if (!terbuka || !panelRef.current) return;
    const tinggi = panelRef.current.offsetHeight;
    const y = posisi.rasioY * Math.max(0, layar.h - UKURAN);
    setPanelAtas(Math.max(
      MARGIN, Math.min(y + UKURAN / 2 - tinggi / 2, layar.h - tinggi - MARGIN)));
  }, [terbuka, posisi, layar]);

  const { sisi, rasioY } = posisi;
  const x = seret ? seret.x
    : (sisi === "kanan" ? layar.w - UKURAN - MARGIN : MARGIN);
  const y = seret ? seret.y
    : jepit(rasioY * Math.max(0, layar.h - UKURAN),
            MARGIN, Math.max(MARGIN, layar.h - UKURAN - MARGIN));

  const tersembunyi = selinap && !seret && !terbuka;
  const dorong = tersembunyi
    ? (sisi === "kanan" ? PORSI_SELINAP : -PORSI_SELINAP) * UKURAN : 0;
  const transisi = (seret || !halusRef.current) ? "none"
    : "left .24s cubic-bezier(.22,1,.36,1), top .24s cubic-bezier(.22,1,.36,1),"
      + " transform .24s ease, opacity .24s ease";

  return (
    <>
      <button
        ref={tombolRef}
        type="button"
        data-testid={`${testId}-gelembung`}
        data-tersembunyi={tersembunyi ? "1" : "0"}
        data-sisi={sisi}
        aria-label={label}
        aria-expanded={terbuka}
        title={label}
        onPointerDown={mulaiSeret}
        onClick={klik}
        onContextMenu={(e) => e.preventDefault()}
        style={{
          position: "fixed",
          left: x,
          top: y,
          width: UKURAN,
          height: UKURAN,
          zIndex: 90,
          touchAction: "none",
          userSelect: "none",
          transition: transisi,
          transform: `translateX(${dorong}px) scale(${terbuka ? 0.6 : 1})`,
          opacity: terbuka ? 0 : (tersembunyi ? 0.62 : 1),
          pointerEvents: terbuka ? "none" : "auto",
          cursor: seret ? "grabbing" : "grab",
        }}
        className="min-w-0 min-h-0 flex items-center justify-center rounded-full bg-card border border-border shadow-lg hover:shadow-xl text-foreground"
      >
        {children}
        {lencana > 0 && (
          <span
            style={{ [sisi === "kanan" ? "left" : "right"]: -3, top: -3 }}
            className="absolute min-w-[1.15rem] h-[1.15rem] px-1 rounded-full bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center shadow"
          >
            {lencana}
          </span>
        )}
      </button>

      {terbuka && (
        <div
          ref={panelRef}
          data-testid={`${testId}-panel-jangkar`}
          style={{
            position: "fixed",
            top: panelAtas,
            [sisi === "kanan" ? "right" : "left"]: MARGIN,
            zIndex: 91,
          }}
        >
          {panel}
        </div>
      )}
    </>
  );
}
