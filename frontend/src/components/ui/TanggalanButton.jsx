import React, { useImperativeHandle, useRef } from "react";

/**
 * TanggalanButton — kalender mini seukuran tombol kotak header (persegi,
 * gaya sama dengan tombol kembali/Booking Nomor): strip bulan berwarna,
 * angka tanggal besar, tahun kecil. Klik membuka pemilih tanggal native;
 * tampilan langsung mengikuti tanggal terpilih.
 *
 * Props:
 * - value: string "YYYY-MM-DD" (wajib)
 * - onChange(v): dipanggil dengan tanggal baru "YYYY-MM-DD"
 * - warna: kelas Tailwind strip bulan (default biru)
 * - kelasTombol: kelas tambahan untuk TOMBOLNYA saja (mis. "hidden sm:flex")
 * - title, testid: aksesibilitas & uji
 *
 * DIPAKAI DARI MENU: halaman yang meleburkan kepalanya jadi satu menu di HP
 * menyembunyikan tombol ini (`kelasTombol="hidden sm:flex"`) lalu memanggil
 * `buka()` lewat ref dari butir menunya:
 *
 *   <TanggalanButton ref={tanggalanRef} kelasTombol="hidden sm:flex" … />
 *   onSelect={() => tanggalanRef.current?.buka()}
 *
 * Yang disembunyikan HANYA tombolnya — `<input type="date">` di bawah tetap
 * terpasang dan tidak berada di dalam subpohon `display:none`, sehingga
 * `showPicker()` tetap sah dipanggil. Menyembunyikan seluruh komponen akan
 * membuat pemilih tanggalnya ikut lenyap dan butir menu itu jadi tombol mati.
 *
 * KENAPA INPUTNYA DITUMPUK TEPAT DI ATAS TOMBOL (bukan `sr-only`):
 * peramban menambatkan kalender native ke KOTAK inputnya. Semula input itu
 * memakai `sr-only`, yang artinya `position:absolute` + ukuran 1x1 + `clip`.
 * Dua akibatnya, keduanya terlihat di tablet/desktop:
 *
 *   1. Elemen absolut di dalam wadah flex (semua kepala halaman memakai
 *      BARIS_KEPALA = `flex …`) mengambil posisi statiknya di SUDUT AWAL
 *      wadah itu — pojok kiri baris kepala — bukan di tempat tombolnya
 *      berdiri. Kalendernya pun terbit jauh di kiri layar.
 *   2. Kotak 1x1 yang ter-clip bukan tambatan yang masuk akal bagi popup
 *      selebar ~300px, jadi peramban makin bebas menaruhnya sekehendaknya.
 *
 * Perbaikannya: tombol dan input dibungkus satu span `relative`, lalu input
 * ditumpuk persis di atas tombol (`absolute left-0 top-0 h-9 w-9`) dengan
 * `opacity-0 pointer-events-none` — kasatmata tak berubah sedikit pun, tetapi
 * kotak tambatannya kini BERIMPIT dengan tombol yang diklik pengguna.
 */

/** Ukuran tombol; input ditumpuk dengan ukuran yang sama persis. */
const UKURAN = "h-9 w-9";

/**
 * Bungkus untuk ukuran layar yang MENYEMBUNYIKAN tombolnya.
 *
 * Bungkusnya wajib tetap dirender di semua ukuran (lihat catatan di atas —
 * input di dalam subpohon `display:none` membuat `showPicker()` mati), tapi
 * bungkus yang selalu hadir juga menyisakan satu jarak `gap` flex kosong di
 * baris kepala HP. Jalan tengahnya: pada ukuran yang menyembunyikan tombol,
 * bungkusnya DIKELUARKAN DARI ALIRAN (`absolute`) — tetap dirender, tidak
 * memakan tempat — lalu kembali `relative` mulai breakpoint tombolnya muncul.
 *
 * Ditulis sebagai kelas LITERAL, bukan `${bp}:relative`: pemindai Tailwind
 * membaca berkas sumber sebagai teks, jadi kelas yang dirakit lewat template
 * tidak pernah ikut tergenerate dan diam-diam hilang dari CSS.
 */
const BUNGKUS_TERSEMBUNYI = {
  sm: "absolute sm:relative inline-flex flex-shrink-0",
  md: "absolute md:relative inline-flex flex-shrink-0",
  lg: "absolute lg:relative inline-flex flex-shrink-0",
  xl: "absolute xl:relative inline-flex flex-shrink-0",
  "2xl": "absolute 2xl:relative inline-flex flex-shrink-0",
};

/** Bungkus baku: tombolnya tampak di semua ukuran. */
export const BUNGKUS_TAMPAK = "relative inline-flex flex-shrink-0";

/**
 * Kelas pembungkus, diturunkan dari `kelasTombol`.
 * "" → selalu tampak; "hidden sm:flex" → keluar aliran di bawah `sm`.
 */
export function kelasBungkus(kelasTombol = "") {
  const k = String(kelasTombol || "");
  if (!/(^|\s)hidden(\s|$)/.test(k)) return BUNGKUS_TAMPAK;
  const bp = (k.match(/(?:^|\s)(sm|md|lg|xl|2xl):(?:inline-)?flex(?:\s|$)/) || [])[1];
  return BUNGKUS_TERSEMBUNYI[bp] || "absolute inline-flex flex-shrink-0";
}

function TanggalanButton({
  value, onChange, warna = "bg-teal-700", title = "Pilih tanggal",
  testid = "tanggalan", kelasTombol = "",
}, refLuar) {
  const ref = useRef(null);
  const buka = () => {
    const el = ref.current;
    if (!el) return;
    // `showPicker` tak ada di peramban lama dan bisa melempar bila dipanggil
    // tanpa aktivasi pengguna — `click()` pada input tanggal native adalah
    // jalan mundur yang selalu bekerja.
    try {
      if (typeof el.showPicker === "function") el.showPicker();
      else el.click();
    } catch {
      el.click();
    }
  };
  useImperativeHandle(refLuar, () => ({ buka }));
  const v = String(value || "").slice(0, 10);
  const bulan = (() => {
    try {
      return new Date(`${v}T00:00:00`).toLocaleDateString("id-ID", { month: "short" });
    } catch {
      return "";
    }
  })();
  return (
    <span className={kelasBungkus(kelasTombol)} data-testid={`${testid}-bungkus`}>
      <button
        type="button"
        onClick={buka}
        className={`${UKURAN} rounded-lg border border-border bg-background flex flex-col items-stretch overflow-hidden flex-shrink-0 hover:bg-muted ${kelasTombol}`}
        title={title}
        aria-label={title}
        data-testid={testid}
      >
        <span className={`${warna} text-white text-[8px] font-bold uppercase tracking-wide leading-none py-[2px] text-center`}>
          {bulan}
        </span>
        <span className="flex-1 flex items-center justify-center text-[14px] font-bold text-foreground leading-none">
          {v.slice(8, 10)}
        </span>
        <span className="text-[8px] text-muted-foreground leading-none pb-[2px] text-center">
          {v.slice(0, 4)}
        </span>
      </button>
      <input
        ref={ref} type="date" value={v}
        onChange={(e) => e.target.value && onChange?.(e.target.value)}
        className={`absolute left-0 top-0 ${UKURAN} opacity-0 pointer-events-none`}
        tabIndex={-1} aria-hidden="true"
        data-testid={`${testid}-input`}
      />
    </span>
  );
}

export default React.forwardRef(TanggalanButton);
