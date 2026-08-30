import React, { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { perluPeriksaAkhir, ringkasPembubuhan } from "@/lib/ringkasPembubuhan";
import {
  ChevronLeft, ChevronRight, Loader2, MapPin, Maximize2, Plus, QrCode, X,
} from "lucide-react";

/**
 * AturPosisiTtd — memilih LETAK & UKURAN satu kotak di atas pratinjau halaman
 * dokumen (gambar PNG yang dirender server per halaman — tanpa unduh PDF).
 *
 * Dipakai dua peran dengan komponen yang SAMA supaya koordinat, jepitan, dan
 * rasa geser/ubah-ukurannya identik:
 *  - `jenis="ttd"` — PENANDA TANGAN memilih letak tanda tangannya (halaman
 *    publik e-sign).
 *  - `jenis="qr"`  — PEMILIK dokumen memilih letak QR verifikasi SEKALI di
 *    akhir, saat semua pihak sudah meneken dan dokumen hendak diunduh
 *    (mandat pemilik: bukan lagi diatur per penanda tangan).
 *
 * - Geser kotak: drag/sentuh di dalam kotak.
 * - Ubah ukuran: pegangan pojok kanan-bawah (drag) atau penggeser ukuran.
 * - Pindah halaman: tombol ◀ ▶ (default halaman terakhir).
 * - Penempatan WAJIB — tak ada jalan pintas "otomatis" (dulu: slot bawaan; QR: pojok
 *   kanan-bawah halaman terakhir).
 *
 * Rasio halaman dibaca dari DIMENSI GAMBAR yang termuat (bukan
 * getBoundingClientRect — wadah bisa kolaps saat gambar belum ada), dan
 * posisi DIJEPIT ULANG tiap rasio kotak/halaman berubah sehingga kotak tidak
 * pernah keluar halaman (termasuk halaman landscape / ttd tinggi).
 *
 * onKirim(posisi, posisiLain): {halaman 1-based, x, y, lebar} — fraksi
 * terhadap lebar/tinggi halaman, (x,y) pojok kiri-atas kotak.
 *
 * ALUR PERAN TTD — DUA LANGKAH, dan itu disengaja:
 *   1. arahkan kotak (klik di halaman / seret / ubah ukuran),
 *   2. "Bubuhkan di Posisi Ini" MENEMPELKAN — bisa diulang berkali-kali, di
 *      halaman mana pun,
 *   3. "Selesai" mengirim semuanya dan menutup tautan sekali-pakai.
 *
 * Sebelumnya tombol berbunyi "Bubuhkan di Posisi Ini" tetapi FUNGSINYA
 * mengirim, sementara yang menempel bernama "Tanda tangan lagi" — kata dan
 * fungsi bertukar tempat, dan orang yang baru menaruh satu dari tiga tanda
 * tangan mengirim dokumennya dengan dua lembar kosong.
 *
 * `banyak`/`wajib` (khusus peran ttd): satu orang kerap harus meneken LEBIH
 * DARI SEKALI pada dokumen yang sama — BAST operasional punya blok tanda
 * tangan Berita Acara DAN lembar Surat Pernyataan Tanggung Jawab di halaman
 * berikutnya. `posisiLain` membawa tempelan kedua dan seterusnya. Tanpanya
 * lembar kedua terbit KOSONG — dokumen resmi yang tampak lengkap padahal
 * belum diteken.
 *
 * Peran QR tetap SATU langkah: labelnya "Simpan & Unduh" sudah menyebut
 * fungsinya dengan tepat, dan untuk satu kotak tak ada kebingungan yang
 * dihapus oleh langkah tambahan.
 */
export default function AturPosisiTtd({
  jenis = "ttd", bangunUrlHalaman, jumlahHalaman = 1, pngTtd,
  nilaiAwal = null, onKirim, onBatal, mengirim = false,
  labelKirim, banyak = false, wajib = 1,
  izinkanDeklarasiKurang = false, deklarasiKurang = false,
  onDeklarasiKurang,
}) {
  const qr = jenis === "qr";
  const MIN = qr ? 0.10 : 0.08;
  const MAKS = qr ? 0.40 : 0.6;
  const total = Math.max(1, jumlahHalaman || 1);
  const [halaman, setHalaman] = useState(
    Math.min(total, Math.max(1, nilaiAwal?.halaman || total)));
  const [muatHal, setMuatHal] = useState(true);
  const [gagalHal, setGagalHal] = useState(false);
  const [cobaKe, setCobaKe] = useState(0);
  // Posisi & ukuran kotak sebagai FRAKSI halaman (tahan zoom/rotasi).
  const [pos, setPos] = useState(() => ({
    x: nilaiAwal?.x ?? (qr ? 0.76 : 0.55),
    y: nilaiAwal?.y ?? (qr ? 0.84 : 0.72),
    lebar: nilaiAwal?.lebar ?? (qr ? 0.14 : 0.28),
  }));
  // rasio = tinggi/lebar ISI kotak. QR selalu persegi (1); ttd ikut gambarnya.
  // Pembubuhan yang SUDAH ditetapkan pada halaman lain — satu orang kerap
  // harus meneken lebih dari sekali pada dokumen yang sama (mis. BAST
  // operasional: blok tanda tangan Berita Acara + lembar Surat Pernyataan
  // Tanggung Jawab di halaman berikutnya).
  const [tetap, setTetap] = useState([]);
  // Halaman yang pratinjaunya sudah pernah dimuat (lihat onLoad <img>).
  const [dilihat, setDilihat] = useState(() => new Set());
  // Pemeriksaan akhir: null = tertutup; objek ringkasan = sedang ditampilkan.
  const [periksa, setPeriksa] = useState(null);
  // Berapa tempat yang WAJIB diteken orang ini (deklarasi pemilik dokumen).
  //
  // Kotak yang sedang diatur TIDAK lagi ikut terhitung. Dulu ia terhitung
  // karena tombol "Bubuhkan" sekaligus mengirim — jadi kotak aktif otomatis
  // ikut terkirim. Kini "Bubuhkan di Posisi Ini" MENEMPELKAN dan "Selesai"
  // yang mengirim, sehingga yang belum ditempel memang belum terhitung.
  const wajibN = Math.max(1, Number(wajib) || 1);
  // Peran QR TIDAK ikut penahanan ini. `tetap` selalu kosong untuk QR, jadi
  // rumus yang sama akan membuat tombol "Simpan & Unduh" terkunci selamanya —
  // regresi yang sempat terjadi dan ditangkap KelengkapanPembubuhan.test.jsx.
  const kurang = qr ? 0 : Math.max(0, wajibN - tetap.length);
  const semuaHalamanDilihat = dilihat.size >= total;
  const kurangMenghalangi = kurang > 0 && !deklarasiKurang;
  // Peringatan "sudah ada di titik ini" — dinyalakan saat orang menekan
  // Bubuhkan dua kali tanpa memindahkan kotaknya sama sekali.
  const [rangkap, setRangkap] = useState(false);
  const [rasio, setRasio] = useState(qr ? 1 : 0.45);
  const [rasioHal, setRasioHal] = useState(1.414); // tinggi/lebar halaman
  const wadahRef = useRef(null);
  const dragRef = useRef(null); // {jenis:'geser'|'ukur', px, py, awal:{...}}
  // Menandai bahwa seretan BARU SAJA selesai, supaya `click` yang menyusul
  // pelepasan tak dianggap perintah "taruh di sini".
  const baruSeret = useRef(false);

  useEffect(() => {
    if (qr || !pngTtd) return;
    const img = new Image();
    img.onload = () => {
      if (img.naturalWidth > 0) setRasio(img.naturalHeight / img.naturalWidth);
    };
    img.src = pngTtd;
  }, [pngTtd, qr]);

  useEffect(() => { setMuatHal(true); setGagalHal(false); }, [halaman, cobaKe]);

  const urlHalaman = bangunUrlHalaman(halaman, cobaKe);

  // Jepit agar kotak SELALU utuh di dalam halaman: kecilkan lebar dulu bila
  // kotak terlalu tinggi untuk halaman (isi tinggi / halaman landscape),
  // baru jepit x/y terhadap tepi.
  const jepit = useCallback((p) => {
    const batasTinggi = qr ? 0.9 : 0.85;
    let lebar = Math.min(MAKS, Math.max(MIN, p.lebar));
    let tinggiFrak = (lebar * rasio) / rasioHal;
    if (tinggiFrak > batasTinggi) {
      lebar = Math.max(MIN, (batasTinggi * rasioHal) / rasio);
      tinggiFrak = (lebar * rasio) / rasioHal;
    }
    return {
      lebar,
      x: Math.min(1 - lebar, Math.max(0, p.x)),
      y: Math.min(Math.max(0, 1 - tinggiFrak - 0.005), Math.max(0, p.y)),
    };
  }, [rasio, rasioHal, qr, MIN, MAKS]);

  // Rasio isi/halaman berubah (gambar termuat, pindah halaman landscape…)
  // → jepit ulang posisi yang ada; nilai awal pun ikut terjepit di sini.
  useEffect(() => { setPos((p) => jepit(p)); }, [jepit]);

  const titik = (e) => (e.touches ? e.touches[0] : e);

  const mulai = (aksi) => (e) => {
    if (!e.touches) e.preventDefault(); // touchstart React = pasif; cukup mouse
    e.stopPropagation();
    const t = titik(e);
    dragRef.current = { jenis: aksi, px: t.clientX, py: t.clientY, awal: { ...pos } };
  };
  const gerak = (e) => {
    const d = dragRef.current;
    const rect = wadahRef.current?.getBoundingClientRect();
    if (!d || !rect || rect.width < 40 || rect.height < 40) return;
    const t = titik(e);
    const dx = (t.clientX - d.px) / rect.width;
    const dy = (t.clientY - d.py) / rect.height;
    if (d.jenis === "geser") setPos(jepit({ ...d.awal, x: d.awal.x + dx, y: d.awal.y + dy }));
    else setPos(jepit({ ...d.awal, lebar: d.awal.lebar + dx }));
  };
  const selesaiDrag = () => {
    // Tandai HANYA bila memang ada seretan; klik biasa tak boleh
    // menyalakan penjaganya dan menelan perintah berikutnya.
    if (dragRef.current) baruSeret.current = true;
    dragRef.current = null;
  };

  /**
   * KLIK DI PRATINJAU = "bubuhkan di sini" — kotaknya langsung pindah ke titik
   * itu, berpusat pada jari/kursor.
   *
   * Permintaan pemilik: *"buat agar ttd tampil ketika diklik posisi bubuhkan
   * di sini."* Sebelumnya letak hanya bisa diubah dengan MENYERET kotak yang
   * sudah ada — orang yang tak sadar kotaknya bisa diseret akan mengira
   * letaknya tak bisa diubah sama sekali.
   *
   * Klik SESUDAH menyeret diabaikan: melepas seretan menghasilkan `click` pada
   * wadah, dan tanpa penjaga ini kotak akan melompat sekali lagi ke titik
   * lepas — persis membatalkan penempatan yang baru saja dikerjakan tangan.
   */
  const klikTaruh = (e) => {
    if (gagalHal || muatHal || baruSeret.current) { baruSeret.current = false; return; }
    const rect = wadahRef.current?.getBoundingClientRect();
    if (!rect || !rect.width || !rect.height) return;
    setPos((p) => jepit({
      ...p,
      x: (e.clientX - rect.left) / rect.width - p.lebar / 2,
      y: (e.clientY - rect.top) / rect.height - ((p.lebar * rasio) / rasioHal) / 2,
    }));
  };

  // Kotak pengarah berpindah / ganti halaman => peringatan rangkap tak
  // relevan lagi. `pos` selalu objek baru saat berubah, jadi identitasnya
  // cukup sebagai pemicu.
  useEffect(() => { setRangkap(false); }, [pos, halaman]);

  /**
   * "BUBUHKAN DI POSISI INI" — menempelkan, BUKAN mengirim.
   *
   * Permintaan pemilik: *"hilangkan bagian '+ tanda tangan lagi', otomatiskan;
   * jika sudah mengklik 'bubuhkan di posisi ini', jika diklik lagi maka akan
   * tertempel lagi. Dan pastikan ketika sudah selesai bubuhkan bisa memencet
   * tombol 'Selesai' agar tidak terjadi kesalahan mis-konsepsi alur akibat
   * bias makna kata dan fungsi tombol."*
   *
   * Itu menamai cacat yang nyata. Sebelumnya tombol berbunyi "Bubuhkan di
   * Posisi Ini" tetapi FUNGSINYA mengirim seluruh pembubuhan dan menutup
   * tautan sekali-pakai — sementara tombol yang benar-benar menempel bernama
   * "Tanda tangan lagi". Kata dan fungsinya bertukar tempat: orang yang baru
   * menaruh SATU tanda tangan dari tiga yang diminta membaca "Bubuhkan di
   * Posisi Ini" sebagai "tempelkan yang ini", menekannya, dan dokumennya
   * terkirim dengan dua lembar kosong.
   *
   * Kini kata dan fungsi sejalan: yang berbunyi "bubuhkan" menempelkan, yang
   * berbunyi "Selesai" mengakhiri.
   */
  const bubuhkanDiSini = () => {
    if (gagalHal || muatHal || mengirim) return;
    const baru = { halaman, ...pos };
    // Dua tekanan tanpa memindahkan kotak = tanda tangan tertumpuk persis di
    // atas dirinya sendiri pada dokumen resmi. Itu selalu salah tekan, tak
    // pernah maksud; penempatan bersebelahan tetap lolos karena koordinatnya
    // berbeda.
    const sudahAda = tetap.some((t) =>
      t.halaman === baru.halaman && t.x === baru.x && t.y === baru.y);
    if (sudahAda) { setRangkap(true); return; }
    setTetap((d) => [...d, baru]);
  };

  // Yang akan dikirim. Peran QR tetap satu langkah: labelnya "Simpan &
  // Unduh" sudah menyebut fungsinya dengan tepat, dan menambah langkah
  // "tempel dulu" untuk SATU kotak hanya menambah klik tanpa menghapus
  // kebingungan apa pun.
  const akanDikirim = qr ? [{ halaman, ...pos }] : tetap;

  const tinggiKotak = (pos.lebar * rasio) / rasioHal;
  const warna = qr
    ? { border: "border-emerald-500", bg: "bg-emerald-500/10", pegangan: "bg-emerald-600", accent: "accent-emerald-600", teks: "text-emerald-600" }
    : { border: "border-blue-500", bg: "bg-blue-500/10", pegangan: "bg-teal-700", accent: "accent-blue-600", teks: "text-blue-600" };

  // PEMERIKSAAN AKHIR — layar tersendiri, bukan dialog kecil di atas peta.
  //
  // Laporan pemilik: penanda tangan "tidak memperhatikan dan langsung
  // mengklik membubuhkan tanpa mengecek ulang". Yang menyembuhkannya bukan
  // peringatan tambahan di layar yang sama — mata sudah terbiasa
  // melewatinya — melainkan MENGGANTI layarnya, sehingga daftar halaman
  // menjadi satu-satunya yang terlihat pada detik keputusan diambil.
  if (periksa) {
    const { ditandatangani, tanpaTtd, belumDibuka } = periksa;
    return (
      <div className="space-y-3" data-testid="periksa-akhir">
        <p className="text-xs font-bold">Periksa sebelum membubuhkan</p>
        <div className="rounded-xl border border-border divide-y divide-border text-[12px]">
          <div className="px-3 py-2">
            <p className="font-semibold text-emerald-700 dark:text-emerald-400">
              Akan tertanda tangan — halaman {ditandatangani.join(", ")}
            </p>
          </div>
          {tanpaTtd.length > 0 && (
            <div className="px-3 py-2" data-testid="periksa-tanpa-ttd">
              <p className="font-semibold text-muted-foreground">
                TIDAK akan tertanda tangan — halaman {tanpaTtd.join(", ")}
              </p>
              <p className="text-[11px] text-muted-foreground leading-snug mt-0.5">
                Bila salah satunya memuat blok tanda tangan Anda, lembar itu
                akan terbit kosong.
              </p>
            </div>
          )}
          {belumDibuka.length > 0 && (
            <div className="px-3 py-2 bg-amber-500/10" data-testid="periksa-belum-dibuka">
              <p className="font-semibold text-amber-700 dark:text-amber-300">
                Belum pernah Anda buka — halaman {belumDibuka.join(", ")}
              </p>
              <p className="text-[11px] text-amber-800 dark:text-amber-200 leading-snug mt-0.5">
                Buka dulu untuk memastikan tak ada blok tanda tangan Anda di
                sana. Sekali dibubuhkan, tautan ini tertutup.
              </p>
            </div>
          )}
        </div>
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
          <Button type="button" variant="outline" size="sm" className="h-9 text-xs"
            disabled={mengirim} onClick={() => setPeriksa(null)}
            data-testid="periksa-kembali">
            Periksa lagi
          </Button>
          <Button type="button" size="sm" className="h-9 text-xs" disabled={mengirim}
            onClick={() => onKirim(akanDikirim[0], akanDikirim.slice(1))}
            data-testid="periksa-lanjut">
            {mengirim ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
            Ya, bubuhkan sekarang
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid={qr ? "atur-posisi-qr" : "atur-posisi-ttd"}>
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-xs font-bold flex items-center gap-1.5">
          {qr ? <QrCode className="w-3.5 h-3.5 text-emerald-600" />
              : <MapPin className="w-3.5 h-3.5 text-blue-600" />}
          {qr ? "Atur letak QR verifikasi" : "Atur letak tanda tangan di dokumen"}
        </p>
        {/* NAVIGASI ◀ ▶ PINDAH KE BAWAH, mengapit tombol Bubuhkan (permintaan
            pemilik). Di sini tersisa LOMPATAN LANGSUNG lewat ketikan: pada
            dokumen berhalaman banyak, menekan panah belasan kali untuk sampai
            ke halaman 17 adalah pekerjaan yang angka bisa selesaikan sekali
            ketik. Dua tempat untuk pekerjaan yang sama hanya membuat mata
            memilih, jadi panahnya tak digandakan di sini. */}
        {total > 1 && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold whitespace-nowrap"
              data-testid="posisi-halaman">Hal.</span>
            <input
              type="number" min={1} max={total} value={halaman}
              onChange={(e) => {
                const n = parseInt(e.target.value, 10);
                if (Number.isFinite(n)) setHalaman(Math.min(total, Math.max(1, n)));
              }}
              className="w-14 h-9 rounded-lg border border-border bg-background px-2 text-xs text-center"
              aria-label="Nomor halaman"
              data-testid="posisi-halaman-input" />
            <span className="text-xs font-semibold whitespace-nowrap text-muted-foreground">
              / {total}
            </span>
          </div>
        )}
      </div>

      <div
        ref={wadahRef}
        className="relative w-full rounded-xl border border-border overflow-hidden bg-white select-none touch-none"
        style={muatHal || gagalHal ? { aspectRatio: `1 / ${rasioHal}` } : undefined}
        onMouseMove={gerak} onMouseUp={selesaiDrag} onMouseLeave={selesaiDrag}
        onTouchMove={gerak} onTouchEnd={selesaiDrag} onTouchCancel={selesaiDrag}
        onClick={klikTaruh}
        data-testid="posisi-wadah"
      >
        {gagalHal ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-muted-foreground">
            <p className="text-xs">Gagal memuat pratinjau halaman.</p>
            <Button type="button" variant="outline" size="sm" className="h-8 text-xs min-w-0 min-h-0"
              onClick={() => setCobaKe((c) => c + 1)}>
              Coba lagi
            </Button>
          </div>
        ) : (
          <img
            key={urlHalaman}
            src={urlHalaman}
            alt={`Pratinjau halaman ${halaman}`}
            className="w-full block"
            draggable={false}
            onLoad={(e) => {
              setMuatHal(false);
              // Halaman ini BENAR-BENAR tampil di layar. Inilah satu-satunya
              // fakta pasti tentang "sudah dilihat" yang dimiliki layar —
              // dipakai pemeriksaan akhir untuk menyebut halaman mana yang
              // belum pernah dibuka penanda tangan.
              setDilihat((d) => (d.has(halaman) ? d : new Set(d).add(halaman)));
              if (e.target.naturalWidth > 0) {
                setRasioHal(e.target.naturalHeight / e.target.naturalWidth);
              }
            }}
            onError={() => { setMuatHal(false); setGagalHal(true); }}
          />
        )}
        {muatHal && !gagalHal && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/60">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* PEMBUBUHAN YANG SUDAH TERSIMPAN pada halaman ini.
            Laporan pemilik: setelah menetapkan letak lalu berpindah halaman
            dan kembali lagi, letak & ukurannya tak terlihat lagi — sehingga
            tak ada cara memastikan setiap halaman sudah tervisualisasi sesuai
            pengaturan. Kini digambar kembali sebagai bayangan bergaris putus.

            `pointer-events-none` WAJIB: bayangan yang menumpuk kotak aktif
            akan merampas gesernya, dan orangnya mendadak tak bisa memindahkan
            tanda tangan yang sedang diatur tanpa tahu sebabnya.

            Tingginya dihitung ulang dari `rasioHal` HALAMAN INI — bukan
            disimpan — karena halaman landscape punya rasio berbeda; memakai
            tinggi beku akan menggambar kotak yang tak sesuai hasil cetaknya. */}
        {!gagalHal && !muatHal && tetap.map((t, i) => (
          t.halaman === halaman ? (
            <div key={`tetap-${i}`}
              className={`absolute z-10 border-2 border-dashed ${warna.border} rounded-md pointer-events-none opacity-70`}
              style={{
                left: `${t.x * 100}%`, top: `${t.y * 100}%`,
                width: `${t.lebar * 100}%`,
                height: `${((t.lebar * rasio) / rasioHal) * 100}%`,
              }}
              data-testid={`posisi-tetap-${i}`}
              data-halaman={t.halaman}>
              <img src={pngTtd} alt="" draggable={false}
                className="w-full h-full object-contain" />
              {/* Label DI DALAM kotak: wadah pratinjau ber-`overflow-hidden`,
                  jadi label di atas garisnya akan terpotong habis begitu
                  kotaknya menempel tepi atas halaman. */}
              <span className="absolute top-0 left-0 text-[9px] px-1 rounded-br bg-blue-600 text-white whitespace-nowrap">
                Tersimpan
              </span>
            </div>
          ) : null
        ))}

        {/* Kotak — geser untuk memindah, pegangan untuk ukuran. Pegangan DI
            DALAM kotak agar tak terpotong overflow saat menempel tepi. */}
        {!gagalHal && !muatHal && (
          <div
            className={`absolute z-20 border-2 ${warna.border} ${warna.bg} rounded-md cursor-move ${qr ? "" : "shadow-[0_0_0_9999px_rgba(0,0,0,0.06)]"}`}
            style={{
              left: `${pos.x * 100}%`, top: `${pos.y * 100}%`,
              width: `${pos.lebar * 100}%`, height: `${tinggiKotak * 100}%`,
            }}
            onMouseDown={mulai("geser")} onTouchStart={mulai("geser")}
            data-testid={qr ? "posisi-qr-kotak" : "posisi-kotak"}
          >
            {qr ? (
              <div className={`w-full h-full flex items-center justify-center ${warna.teks} pointer-events-none`}>
                <QrCode className="w-2/3 h-2/3" />
              </div>
            ) : (
              <img src={pngTtd} alt="Tanda tangan" draggable={false}
                className="w-full h-full object-contain pointer-events-none" />
            )}
            <span
              className={`absolute right-0 bottom-0 w-7 h-7 rounded-tl-lg rounded-br-md ${warna.pegangan} text-white flex items-center justify-center cursor-nwse-resize shadow-md`}
              onMouseDown={mulai("ukur")} onTouchStart={mulai("ukur")}
              aria-label={qr ? "Ubah ukuran QR verifikasi" : "Ubah ukuran tanda tangan"}
              data-testid={qr ? "posisi-qr-pegangan" : "posisi-pegangan"}
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 px-0.5">
        <span className="text-[11px] text-muted-foreground whitespace-nowrap">
          {qr ? "Ukuran QR" : "Ukuran TTD"}
        </span>
        <input
          type="range" min={MIN} max={MAKS} step="0.01" value={pos.lebar}
          onChange={(e) => setPos((p) => jepit({ ...p, lebar: parseFloat(e.target.value) }))}
          className={`flex-1 ${warna.accent} min-w-0`}
          data-testid={qr ? "posisi-qr-ukuran" : "posisi-ukuran"}
        />
      </div>
      <p className="text-[11px] text-muted-foreground">
        {qr
          ? "Geser kotak hijau ke tempat kosong (hindari kaki halaman), tarik pegangan untuk mengubah ukuran — jaga cukup besar agar mudah dipindai."
          : "Arahkan kotak biru ke tempat tanda tangan — klik di halaman, seret kotaknya, atau tarik pegangan untuk mengubah ukuran. Lalu tekan Bubuhkan di Posisi Ini."}
      </p>

      {rangkap && (
        <p className="text-[11px] rounded-lg border border-amber-500/50 bg-amber-500/10 px-2.5 py-1.5 text-amber-800 dark:text-amber-200 leading-snug"
          data-testid="posisi-rangkap">
          Titik ini sudah dibubuhkan. Pindahkan dulu kotaknya bila ingin
          menambah tanda tangan kedua — dua tanda tangan bertumpuk persis akan
          tercetak sebagai satu coretan tebal.
        </p>
      )}

      {/* Panel ini tampil SEJAK AWAL bila pemilik dokumen mendeklarasikan
          lebih dari satu tempat — bukan menunggu orangnya menekan "Tanda
          tangan lagi" lebih dulu. Justru orang yang TIDAK TAHU dirinya harus
          meneken di beberapa tempat itulah yang perlu diberi tahu; yang sudah
          tahu tak butuh diingatkan. */}
      {!qr && (tetap.length > 0 || wajibN > 1) && (
        <div className={`rounded-lg border px-2.5 py-1.5 space-y-1 ${
          kurang > 0 ? "border-amber-500/50 bg-amber-500/10"
            : "border-border bg-muted/40"}`}
          data-testid="posisi-daftar">
          <p className="text-[11px] font-semibold">
            {kurang > 0
              ? `Dokumen ini menuntut ${wajibN} tanda tangan dari Anda — kurang ${kurang} lagi`
              : `${tetap.length} tanda tangan akan dibubuhkan`}
          </p>
          {kurang > 0 && (
            <p className="text-[11px] text-amber-800 dark:text-amber-200 leading-snug"
              data-testid="posisi-kurang">
              Arahkan kotak, tekan <b>Bubuhkan di Posisi Ini</b>, lalu pindah
              halaman dan ulangi untuk sisanya. Baru setelah itu tekan
              <b>Selesai</b> — sekali selesai, tautan ini tertutup dan lembar
              yang terlewat tak bisa ditambahkan lagi.
            </p>
          )}
          <div className="flex flex-wrap gap-1">
            {tetap.map((t, i) => (
              <span key={i} className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border border-border bg-background">
                {/* Label MENJADI TOMBOL LONCAT ke halamannya. Memastikan
                    "semua halaman sudah tervisualisasi sesuai pengaturan"
                    menuntut orangnya bisa MELIHAT tiap letak, dan menyuruhnya
                    menekan ◀ ▶ berkali-kali untuk itu adalah pekerjaan yang
                    komputer bisa lakukan sekali tekan. */}
                <button type="button"
                  className={`min-w-0 min-h-0 underline-offset-2 ${
                    t.halaman === halaman ? "font-semibold text-blue-600 dark:text-blue-400"
                      : "hover:underline"}`}
                  title={`Lihat letak pembubuhan di halaman ${t.halaman}`}
                  data-testid={`posisi-lihat-${i}`}
                  onClick={() => setHalaman(t.halaman)}>
                  Halaman {t.halaman}
                </button>
                <button type="button" aria-label={`Batalkan pembubuhan halaman ${t.halaman}`}
                  className="text-red-500 min-w-0 min-h-0"
                  data-testid={`posisi-hapus-${i}`}
                  onClick={() => setTetap((d) => d.filter((_, j) => j !== i))}>
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
            <span className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-blue-500/50 bg-blue-500/10"
              data-testid="posisi-belum">
              Halaman {halaman} — belum dibubuhkan
            </span>
          </div>
        </div>
      )}

      {!qr && izinkanDeklarasiKurang && kurang > 0 && (
        <div className="rounded-lg border border-violet-500/35 bg-violet-500/5 px-2.5 py-2 space-y-1.5"
          data-testid="posisi-deklarasi-kurang">
          <label className={`flex items-start gap-2 text-[11px] leading-snug ${
            semuaHalamanDilihat ? "cursor-pointer" : "text-muted-foreground"}`}>
            <input type="checkbox" className="mt-0.5 accent-violet-600"
              checked={!!deklarasiKurang}
              disabled={!semuaHalamanDilihat || mengirim}
              onChange={(e) => onDeklarasiKurang?.(e.target.checked)}
              data-testid="posisi-deklarasi-checkbox" />
            <span>
              Saya sudah membuka dan memeriksa <b>seluruh {total} halaman</b>.
              Tidak ada area tanda tangan saya lagi meskipun permintaan mencatat
              {` ${wajibN} tempat`}. Hasil ini akan diperiksa operator/admin satker.
            </span>
          </label>
          {!semuaHalamanDilihat && (
            <p className="text-[10px] text-amber-700 dark:text-amber-300 pl-5"
              data-testid="posisi-deklarasi-belum-bisa">
              Buka seluruh halaman terlebih dahulu sebelum membuat deklarasi ini.
            </p>
          )}
        </div>
      )}

      {/* TATA LETAK TOMBOL — DUA BARIS, dan itu memperbaiki cacat nyata.
          Empat tombol dalam SATU baris (Bubuhkan, ◀, Selesai, ▶) saling
          menghimpit di layar ponsel: `Button` membawa `whitespace-nowrap`,
          jadi labelnya tidak melipat melainkan TERPOTONG — "Selesai — kirim 1
          tanda tanga" — dan "Kembali" terlempar ke baris sendiri.

          Sekarang: baris ATAS untuk pekerjaan yang diulang-ulang (◀ Bubuhkan
          ▶), baris BAWAH untuk yang sekali saja (Kembali · Selesai). Tak ada
          baris yang memuat lebih dari tiga hal, jadi tak ada yang terpotong. */}
      <div className="space-y-2 pt-0.5">
        {!qr && (
          /* BARIS AKSI BERULANG. Tombol Bubuhkan dibuat PALING MENONJOL
             (permintaan pemilik) — dan itu juga yang lebih aman: ia bisa
             diulang dan dibatalkan, sedangkan "Selesai" menutup tautan
             sekali-pakai untuk selamanya. Aksi yang tak bisa ditarik kembali
             tidak pantas jadi tombol paling mencolok di layar.

             ◀ ▶ tetap MENGAPITNYA (permintaan pemilik terdahulu): navigasi
             ada tepat di tempat tangan sudah berada, sehingga alurnya
             "atur → bubuhkan → maju" tanpa memindahkan pandangan. */
          <div className="flex items-center gap-1.5 sm:gap-2 sm:justify-end">
            {total > 1 && (
              <Button type="button" variant="outline" size="sm"
                className="h-11 w-10 sm:w-11 p-0 min-w-0 min-h-0 shrink-0"
                disabled={halaman <= 1 || mengirim}
                onClick={() => setHalaman((h) => Math.max(1, h - 1))}
                aria-label="Halaman sebelumnya" data-testid="posisi-prev">
                <ChevronLeft className="w-5 h-5" />
              </Button>
            )}
            <Button type="button" size="sm"
              className="h-11 flex-1 sm:flex-none sm:min-w-[16rem] px-2.5 sm:px-3 text-sm font-semibold min-w-0"
              disabled={mengirim || gagalHal || muatHal}
              onClick={bubuhkanDiSini}
              data-testid="posisi-bubuh">
              <Plus className="w-4 h-4 mr-1 shrink-0" />
              <span className="truncate">Bubuhkan di Posisi Ini</span>
            </Button>
            {total > 1 && (
              <Button type="button" variant="outline" size="sm"
                className="h-11 w-10 sm:w-11 p-0 min-w-0 min-h-0 shrink-0"
                disabled={halaman >= total || mengirim}
                onClick={() => setHalaman((h) => Math.min(total, h + 1))}
                aria-label="Halaman berikutnya" data-testid="posisi-next">
                <ChevronRight className="w-5 h-5" />
              </Button>
            )}
          </div>
        )}

        <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-2">
          <Button type="button" variant="outline" size="sm"
            className="h-9 text-xs w-full sm:w-auto shrink-0" disabled={mengirim} onClick={onBatal}>
            Kembali
          </Button>
          {/* "Otomatis saja" DICABUT (mandat pemilik): admin WAJIB menempatkan
              QR verifikasi sendiri. Penempatan otomatis di pojok kanan-bawah
              halaman terakhir kerap menimpa blok tanda tangan atau kaki
              halaman, dan karena tombolnya adalah jalan tercepat, itulah yang
              paling sering dipakai. */}
          <div className="flex items-center gap-2 min-w-0 w-full sm:w-auto">
            {/* Peran QR tetap satu langkah, jadi ◀ ▶ mengapit tombol simpannya
                di sini — tak ada baris aksi berulang untuknya. */}
            {qr && total > 1 && (
              <Button type="button" variant="outline" size="sm"
                className="h-9 w-9 p-0 min-w-0 min-h-0 shrink-0"
                disabled={halaman <= 1 || mengirim}
                onClick={() => setHalaman((h) => Math.max(1, h - 1))}
                aria-label="Halaman sebelumnya" data-testid="posisi-prev">
                <ChevronLeft className="w-4 h-4" />
              </Button>
            )}
            {/* SELESAI MENUTUP TAUTAN SEKALI-PAKAI. Lembar yang terlewat TIDAK
                bisa ditambahkan lagi — satu-satunya pemulihan adalah
                membatalkan permintaan lalu meminta SEMUA orang meneken ulang.
                Karena itu ia ditahan selama masih kurang, bukan sekadar
                diperingatkan; dan karena itu pula ia TIDAK dibuat semencolok
                tombol Bubuhkan. */}
            <Button type="button" size="sm"
              variant={qr ? "default" : "outline"}
              className={`h-9 text-xs min-w-0 flex-1 sm:flex-none ${
                qr ? "" : "border-emerald-600/60 text-emerald-700 dark:text-emerald-400 font-semibold"}`}
              disabled={mengirim || gagalHal || muatHal || kurangMenghalangi
                || akanDikirim.length === 0}
              onClick={() => {
                const semuaTtd = akanDikirim.map((t) => t.halaman);
                // PEMERIKSAAN AKHIR, bukan pengiriman langsung. Penahanan
                // jumlah hanya bekerja bila pemilik dokumen mendeklarasikannya;
                // bila ia lupa, tak ada apa pun yang menahan dan orang menekan
                // Selesai atas dokumen yang belum ia lihat seluruhnya.
                if (!qr && perluPeriksaAkhir(total)) {
                  setPeriksa(ringkasPembubuhan({
                    jumlahHalaman: total, halamanTtd: semuaTtd,
                    halamanDilihat: [...dilihat],
                  }));
                  return;
                }
                onKirim(akanDikirim[0], akanDikirim.slice(1));
              }} data-testid="posisi-kirim">
              {mengirim ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5 shrink-0" /> : null}
              {/* Label peran ttd BERHENTI memakai kata "bubuhkan": kata itu
                  kini milik tombol yang menempel. Tak ada cabang "belum ada
                  yang dibubuhkan": `wajibN` minimal 1, jadi selama belum ada
                  tempelan `kurang` pasti > 0 dan cabang itu tak terlihat. */}
              <span className="truncate">
                {labelKirim || (qr ? "Simpan & Unduh"
                  : kurangMenghalangi ? `Kurang ${kurang} tanda tangan lagi`
                    : deklarasiKurang ? `Selesai — kirim ${tetap.length} (deklarasi)`
                    : `Selesai — kirim ${tetap.length} tanda tangan`)}
              </span>
            </Button>
            {qr && total > 1 && (
              <Button type="button" variant="outline" size="sm"
                className="h-9 w-9 p-0 min-w-0 min-h-0 shrink-0"
                disabled={halaman >= total || mengirim}
                onClick={() => setHalaman((h) => Math.min(total, h + 1))}
                aria-label="Halaman berikutnya" data-testid="posisi-next">
                <ChevronRight className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
