import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Tags } from "lucide-react";
import {
  CAKUPAN, cakupanAwal, idsCakupanStiker, jumlahCakupanStiker,
} from "@/lib/cakupanCetak";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { makeDownloadProgress } from "@/lib/downloadFile";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Kapasitas & dimensi tiap ukuran, DIPISAH per kertas. Dulu satu baris memuat
 * angka A4 dan A3 sekaligus ("A4: 12/hal (±98×46) · A3: 27/hal (±94×44)") —
 * separuhnya selalu mubazir karena kertasnya toh sudah dipilih. Kini pilihan
 * kertas dinaikkan ke atas dan tiap ukuran hanya menampilkan angka kertas yang
 * sedang aktif.
 */
const UKURAN = [
  { k: "besar", nama: "Besar", A4: ["12/hal", "±98×46 mm"], A3: ["27/hal", "±94×44 mm"] },
  { k: "sedang", nama: "Sedang", A4: ["27/hal", "±65×30 mm"], A3: ["65/hal", "±56×30 mm"] },
  { k: "kecil", nama: "Kecil", A4: ["48/hal", "±48×22 mm"], A3: ["102/hal", "±46×23 mm"] },
];

const angka = (n) => Number(n || 0).toLocaleString("id-ID");

/** Chip pilihan: radio asli (sr-only) agar tetap bisa dipakai keyboard &
 *  pembaca layar, tampilannya kotak padat yang muat berdampingan. */
function Chip({ nama, nilai, aktif, onPilih, testId, children, className = "" }) {
  return (
    <label className={`relative flex flex-col justify-center rounded-lg border px-2.5 py-1.5 cursor-pointer transition-colors ${
      aktif ? "border-teal-600 bg-teal-600/10 text-foreground"
            : "border-border text-muted-foreground hover:bg-muted"} ${className}`}>
      <input type="radio" name={nama} value={nilai} checked={aktif} onChange={onPilih}
        className="sr-only" data-testid={testId} />
      {children}
    </label>
  );
}

/** Lipatan penjelasan — isinya tetap ada, tapi tak lagi memakan layar HP. */
function Lipatan({ judul, children, testId }) {
  return (
    <details className="text-[11px] text-muted-foreground" data-testid={testId}>
      <summary className="cursor-pointer select-none underline decoration-dotted underline-offset-2">
        {judul}
      </summary>
      <p className="mt-1 leading-snug">{children}</p>
    </details>
  );
}

/**
 * Dialog Cetak Stiker Label BMN — 3 ukuran × kertas A4/A3. Cakupan: aset yang
 * SEDANG DISELEKSI (bila mode seleksi aktif — ini yang dipilih otomatis),
 * seluruh hasil filter aktif, atau halaman yang sedang tampil.
 *
 * Tata letak sengaja PADAT: di HP dialog ini pernah memenuhi satu layar penuh
 * hanya oleh teks penjelasan, sehingga tombol "Buat PDF" tak terlihat tanpa
 * menggulir. Penjelasan panjang kini dilipat (`Lipatan`), pilihan dijadikan
 * chip berdampingan, dan angka kapasitas hanya untuk kertas yang aktif.
 */
export default function CetakStikerDialog({ open, onOpenChange, buildParams, totalItems, pageAssets, selectedIds }) {
  const [ukuran, setUkuran] = useState("sedang");
  const [kertas, setKertas] = useState("A4");
  const [cakupan, setCakupan] = useState(CAKUPAN.FILTER); // terpilih | filter | halaman
  const [headerInfo, setHeaderInfo] = useState("nama"); // nama | kode (20 digit)
  const [sampelUkuran, setSampelUkuran] = useState(true); // stiker contoh berdimensi
  const [rekap, setRekap] = useState(null); // rincian pilihan ukuran per aset
  const [sibuk, setSibuk] = useState(false);

  const jmlTerpilih = (selectedIds || []).length;

  // Dibuka dengan seleksi aktif → langsung berdiri di cakupan "terpilih".
  // Tanpa ini, menandai 3 aset lalu menekan Cetak Stiker diam-diam mencetak
  // seluruh hasil filter.
  useEffect(() => {
    if (open) setCakupan(cakupanAwal(jmlTerpilih));
  }, [open, jmlTerpilih]);

  // Satu sumber parameter untuk rekap & cetak — dua penyusun terpisah pernah
  // membuat rekap dan hasil PDF menghitung aset yang berbeda.
  const paramsCakupan = useCallback(() => {
    if (cakupan === CAKUPAN.FILTER) return buildParams?.() || new URLSearchParams();
    const ids = idsCakupanStiker(cakupan, selectedIds, pageAssets);
    return new URLSearchParams({ asset_ids: ids.join(",") });
  }, [cakupan, selectedIds, pageAssets, buildParams]);

  // Rekap pilihan ukuran per aset — dimuat saat mode per_aset dipilih agar
  // pengguna tahu berapa stiker per ukuran & berapa yang BELUM terisi.
  useEffect(() => {
    if (!open || ukuran !== "per_aset") return;
    const params = paramsCakupan();
    setRekap(null);
    axios.get(`${API}/stiker/rekap-ukuran?${params.toString()}`)
      .then((r) => setRekap(r.data))
      .catch(() => setRekap(null));
  }, [open, ukuran, paramsCakupan]);

  const cetak = async () => {
    setSibuk(true);
    const progress = makeDownloadProgress("Stiker label BMN (PDF)");
    try {
      const params = paramsCakupan();
      params.set("ukuran", ukuran);
      params.set("kertas", kertas);
      params.set("header_info", headerInfo);
      params.set("sampel_ukuran", sampelUkuran ? "true" : "false");
      const r = await axios.get(`${API}/stiker/label?${params.toString()}`, {
        responseType: "blob", timeout: 180000,
        onDownloadProgress: progress.onDownloadProgress,
      });
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const win = window.open(url, "_blank");
      if (!win) {
        const a = document.createElement("a");
        a.href = url; a.download = `stiker_label_${ukuran}_${kertas}.pdf`;
        document.body.appendChild(a); a.click(); a.remove();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      progress.success(`Stiker ${ukuran} (${kertas}) siap dicetak`);
      onOpenChange(false);
    } catch (err) {
      // Blob error → baca detail JSON bila ada.
      let detail = "Gagal membuat stiker";
      try {
        const teks = await err?.response?.data?.text?.();
        detail = JSON.parse(teks || "{}").detail || detail;
      } catch { /* biarkan pesan default */ }
      progress.error(detail);
      toast.error(detail);
    } finally {
      setSibuk(false);
    }
  };

  const jumlah = jumlahCakupanStiker(cakupan, {
    idsTerpilih: selectedIds, asetHalaman: pageAssets, totalFilter: totalItems,
  });

  // Pilihan "aset terpilih" hanya ada saat memang ada yang diseleksi.
  const PILIHAN_CAKUPAN = [
    ...(jmlTerpilih > 0 ? [[CAKUPAN.TERPILIH, "Terpilih", jmlTerpilih]] : []),
    [CAKUPAN.FILTER, "Hasil filter", totalItems || 0],
    [CAKUPAN.HALAMAN, "Halaman ini", (pageAssets || []).length],
  ];

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!sibuk) onOpenChange(o); }}>
      <DialogContent className="max-w-md max-h-[88vh] overflow-y-auto p-4 sm:p-6">
        <DialogHeader className="space-y-1">
          <DialogTitle className="flex items-center gap-2 text-base">
            <Tags className="w-4 h-4 flex-shrink-0" />Cetak Stiker Label BMN
          </DialogTitle>
          <DialogDescription className="text-[11px] leading-snug">
            Label resmi satker + QR yang dikenali pemindai aplikasi.
          </DialogDescription>
        </DialogHeader>

        <Lipatan judul="Rincian desain label" testId="stiker-info-desain">
          Logo + nama instansi + nama satker, lalu kode barang &amp; NUP, nama barang,
          dan sub-sub kelompok. Nama panjang otomatis lanjut ke baris berikutnya; nama
          instansi panjang menyusut lalu pecah dua baris. Grid otomatis memenuhi seluruh
          ruang kertas — sisa hanya margin &amp; celah potong.
        </Lipatan>

        <div className="space-y-2.5">
          {/* Cakupan — chip berdampingan; nama di atas, jumlah di bawah. */}
          <div>
            <p className="text-[11px] font-semibold text-foreground mb-1">Cakupan aset</p>
            <div className="flex flex-wrap gap-1.5">
              {PILIHAN_CAKUPAN.map(([k, label, n]) => (
                <Chip key={k} nama="stiker-cakupan" nilai={k} aktif={cakupan === k}
                  onPilih={() => setCakupan(k)} testId={`stiker-cakupan-${k}`}>
                  <span className="text-[11px] font-semibold leading-tight">{label}</span>
                  <span className="text-[10px] leading-tight opacity-80">{angka(n)} aset</span>
                </Chip>
              ))}
            </div>
          </div>

          {/* Kertas dinaikkan: menentukan angka yang tampil di daftar ukuran. */}
          <div className="flex items-center gap-2">
            <p className="text-[11px] font-semibold text-foreground">Kertas</p>
            <div className="flex gap-1.5">
              {["A4", "A3"].map((k) => (
                <Chip key={k} nama="stiker-kertas" nilai={k} aktif={kertas === k}
                  onPilih={() => setKertas(k)} testId={`stiker-kertas-${k}`}
                  className="py-1">
                  <span className="text-[11px] font-semibold leading-tight">{k}</span>
                </Chip>
              ))}
            </div>
          </div>

          {/* Ukuran — dua kolom, hanya angka kertas yang aktif. */}
          <div>
            <p className="text-[11px] font-semibold text-foreground mb-1">
              Ukuran stiker <span className="font-normal text-muted-foreground">· per lembar {kertas}</span>
            </p>
            <div className="grid grid-cols-2 gap-1.5">
              {UKURAN.map((u) => (
                <Chip key={u.k} nama="stiker-ukuran" nilai={u.k} aktif={ukuran === u.k}
                  onPilih={() => setUkuran(u.k)} testId={`stiker-ukuran-${u.k}`}>
                  <span className="text-[11px] font-semibold leading-tight">{u.nama}</span>
                  <span className="text-[10px] leading-tight opacity-80">
                    {u[kertas][0]} · {u[kertas][1]}
                  </span>
                </Chip>
              ))}
              <Chip nama="stiker-ukuran" nilai="per_aset" aktif={ukuran === "per_aset"}
                onPilih={() => setUkuran("per_aset")} testId="stiker-ukuran-per_aset"
                className="col-span-2">
                <span className="text-[11px] font-semibold leading-tight">Sesuai pilihan tiap aset</span>
                <span className="text-[10px] leading-tight opacity-80">
                  ikut field &quot;Ukuran Stiker&quot; · dikelompokkan besar → sedang → kecil
                </span>
              </Chip>
            </div>
          </div>

          {ukuran === "per_aset" && (
            <div className="rounded-lg border border-border bg-muted/40 p-2" data-testid="stiker-rekap-ukuran">
              {!rekap ? (
                <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                  <Loader2 className="w-3 h-3 animate-spin" />Menghitung rincian ukuran…
                </p>
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
                    <span className="font-semibold text-foreground text-[11px]">{angka(rekap.total)} stiker:</span>
                    <span className="px-1.5 py-0.5 rounded-full bg-card border border-border">Besar <b>{rekap.besar}</b></span>
                    <span className="px-1.5 py-0.5 rounded-full bg-card border border-border">Sedang <b>{rekap.sedang}</b></span>
                    <span className="px-1.5 py-0.5 rounded-full bg-card border border-border">Kecil <b>{rekap.kecil}</b></span>
                    {rekap.belum_terisi > 0 && (
                      <span className="px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/40 font-semibold">
                        Kosong {rekap.belum_terisi}
                      </span>
                    )}
                  </div>
                  {rekap.belum_terisi > 0 && (
                    <p className="text-[10px] text-amber-700 dark:text-amber-400 mt-1 leading-snug">
                      {rekap.belum_terisi} aset belum punya Ukuran Stiker → dicetak <b>Sedang</b>.
                      Isi lewat form aset, edit cepat, atau <b>Ubah Massal</b>.
                    </p>
                  )}
                </>
              )}
            </div>
          )}

          {/* Header baris kedua — hint panjang hanya muncul saat relevan. */}
          <div>
            <p className="text-[11px] font-semibold text-foreground mb-1">Baris kedua header</p>
            <div className="flex flex-wrap gap-1.5">
              {[["nama", "Nama satker"], ["kode", "Kode 20 digit"]].map(([k, label]) => (
                <Chip key={k} nama="stiker-header" nilai={k} aktif={headerInfo === k}
                  onPilih={() => setHeaderInfo(k)} testId={`stiker-header-${k}`} className="py-1">
                  <span className="text-[11px] font-semibold leading-tight">{label}</span>
                </Chip>
              ))}
            </div>
            {headerInfo === "kode" && (
              <p className="text-[10px] text-muted-foreground mt-1 leading-snug" data-testid="stiker-hint-kode">
                Contoh 126011600691778000KP — isi dulu di Pengaturan → Master Satker.
              </p>
            )}
          </div>

          {/* Stiker contoh — satu baris; alasan panjangnya dilipat. */}
          <div className="rounded-lg border border-border bg-muted/30 p-2 space-y-1">
            <label className="flex items-center gap-2 text-[11px] text-foreground cursor-pointer">
              <input type="checkbox" checked={sampelUkuran}
                onChange={(e) => setSampelUkuran(e.target.checked)}
                data-testid="stiker-sampel-ukuran" />
              <b>Sertakan stiker contoh berukuran</b>
            </label>
            <Lipatan judul="Untuk apa?" testId="stiker-info-sampel">
              Satu kotak terakhir tiap ukuran diisi panjang × lebar sebenarnya
              (mis. 98,3 × 46,3 mm) lengkap dengan garis ukur — patokan saat memesan
              bahan stiker. Bertanda putus-putus &amp; bertulisan &quot;bukan untuk ditempel&quot;.
            </Lipatan>
          </div>

          {jumlah > 2000 && (
            <p className="text-[11px] text-amber-700 dark:text-amber-400 leading-snug">
              {angka(jumlah)} aset melebihi batas 2000 stiker per unduhan — persempit
              cakupan atau cetak bertahap.
            </p>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" disabled={sibuk} onClick={() => onOpenChange(false)}>Batal</Button>
          <Button onClick={cetak} disabled={sibuk || jumlah === 0} data-testid="stiker-cetak">
            {sibuk ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Tags className="w-4 h-4 mr-1.5" />}
            Buat PDF ({angka(jumlah)})
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
