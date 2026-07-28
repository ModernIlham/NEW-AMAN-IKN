// Batas galat render (React error boundary) + pembungkus halaman lazy.
//
// MASALAH YANG DITUTUP. Seluruh halaman aplikasi ini dimuat dengan
// `React.lazy(() => import(...))`. Bila berkas potongan (chunk) itu GAGAL
// diunduh — luring, sinyal putus di tengah, atau versi baru sudah ter-deploy
// sehingga nama berkas ber-hash yang lama TAK ADA LAGI di server — `import()`
// menolak, Suspense melempar galat itu ke atas, dan React (sejak v16) MELEPAS
// SELURUH POHON KOMPONEN. Tanpa satu pun error boundary di aplikasi ini,
// hasilnya adalah LAYAR PUTIH POLOS: tanpa pesan, tanpa tombol, tanpa jejak di
// layar. Operator lapangan membacanya sebagai "aplikasinya rusak".
//
// Boundary ini mengubahnya jadi layar yang mengatakan apa yang terjadi berikut
// jalan pulih yang BENAR-BENAR bekerja untuk jenis galatnya — lihat catatan di
// tombol: untuk potongan yang gagal diunduh, memuat ulang halaman adalah
// satu-satunya obat, dan menawarkan "Coba lagi" di situ hanya akan berbohong.
import React from "react";
import { AlertTriangle, RefreshCw, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
// Klasifikasi galat dipisah ke lib/ agar bisa diuji tanpa DOM & tanpa JSX.
import { galatUnduhPotongan, pesanGalatRender } from "@/lib/galatRender";

export default class BatasGalat extends React.Component {
  constructor(props) {
    super(props);
    this.state = { err: null, kunci: 0 };
  }

  static getDerivedStateFromError(err) {
    // DINORMALKAN, karena nilai galatnya juga dipakai sebagai PENANDA "sedang
    // gagal" di render(). Melempar nilai falsy itu sah dalam JavaScript
    // (`throw undefined`, `throw null`, `throw ""` — mudah terjadi pada
    // `throw e` di dalam catch yang menerima undefined, atau dari pustaka pihak
    // ketiga). Tanpa normalisasi, state jadi { err: undefined }, `if (!err)`
    // merender ULANG anaknya, anaknya melempar lagi, dan boundary ini berputar
    // sampai React menyerah pada batas kedalaman pembaruan — galat ITU dilempar
    // DI ATAS boundary sehingga seluruh pohon lepas: layar putih polos, persis
    // yang komponen ini ada untuk mencegahnya.
    return { err: err || new Error("Galat tanpa keterangan") };
  }

  componentDidCatch(err, info) {
    // Console SAJA — tak ada pelaporan ke server di sini dengan sengaja: galat
    // ini sering justru terjadi ketika jaringan sedang mati.
    console.error("[BatasGalat]", err, info?.componentStack);
  }

  render() {
    const { err, kunci } = this.state;
    if (!err) {
      // `key` dinaikkan saat "Coba lagi" agar anaknya benar-benar DIPASANG
      // ULANG (state lama yang membuatnya jatuh ikut terbuang), bukan sekadar
      // dirender ulang dengan instans yang sama.
      return <React.Fragment key={kunci}>{this.props.children}</React.Fragment>;
    }
    const potongan = galatUnduhPotongan(err);
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3 px-6 text-center"
           data-testid="batas-galat">
        <AlertTriangle className="w-8 h-8 text-amber-500" />
        <p className="text-sm font-semibold text-foreground">Halaman gagal ditampilkan</p>
        <p className="text-xs text-muted-foreground max-w-md break-words">
          {pesanGalatRender(err)}
        </p>
        <div className="flex flex-wrap gap-2 justify-center mt-1">
          <Button size="sm" variant={potongan ? "default" : "outline"}
                  className="h-8 text-xs"
                  onClick={() => window.location.reload()}
                  data-testid="batas-galat-muat-ulang">
            <RotateCcw className="w-3.5 h-3.5 mr-1" />Muat ulang halaman
          </Button>
          {/* "Coba lagi" SENGAJA TIDAK ditawarkan untuk kegagalan unduh
              potongan. `React.lazy` mengingat penolakan `import()` di objek
              lazy tingkat-modul dan MELEMPAR GALAT YANG SAMA selamanya —
              memasang ulang anaknya tak mengulang unduhan. Tombol itu akan
              gagal seketika setiap kali ditekan; memuat ulang halaman adalah
              satu-satunya obat yang benar (ia juga mengambil index.html baru
              berikut nama berkas ber-hash yang baru pasca-deploy). */}
          {!potongan && (
            <Button size="sm" className="h-8 text-xs"
                    onClick={() => this.setState((s) => ({ err: null, kunci: s.kunci + 1 }))}
                    data-testid="batas-galat-coba-lagi">
              <RefreshCw className="w-3.5 h-3.5 mr-1" />Coba lagi
            </Button>
          )}
        </div>
        {/* Janji durabilitas SENGAJA TIDAK MUTLAK. Antrean tulis luring hanya
            ada di useOptimisticQueue, dan hook itu dipakai satu halaman saja
            (Inventarisasi). Menjanjikan "data Anda tersimpan" pada 32 halaman
            berarti berbohong di 31 di antaranya — dan lebih buruk lagi, ia
            MENDORONG operator menekan Muat ulang yang justru membuang isian
            formulir yang tak pernah tersimpan di mana pun. */}
        <p className="text-[10px] text-muted-foreground max-w-md">
          Pemindaian dan simpanan Inventarisasi yang belum terkirim tetap
          tersimpan di perangkat ini. <b>Isian formulir yang belum disimpan akan
          hilang</b> bila halaman dimuat ulang.
        </p>
      </div>
    );
  }
}

/**
 * Pembungkus baku halaman lazy: boundary DI LUAR Suspense.
 *
 * Urutannya penting. `import()` yang menolak dilempar saat Suspense mencoba
 * membaca hasilnya, jadi boundary harus berada DI ATAS Suspense untuk
 * menangkapnya — bila dipasang di dalam, galatnya lewat begitu saja.
 */
export function HalamanLazy({ fallback, children }) {
  return (
    <BatasGalat>
      <React.Suspense fallback={fallback}>{children}</React.Suspense>
    </BatasGalat>
  );
}
