// OPNAME RUANGAN LEWAT SCAN STIKER (Spasial Fase 11).
//
// Bentuk layar ini mengikuti cara opname benar-benar dikerjakan: petugas berdiri
// di satu ruangan, memindai barang satu per satu, dan yang paling ingin ia tahu
// bukan "berapa yang sudah" melainkan "APA YANG BELUM" — daftar sisa itulah yang
// menentukan kapan ia boleh pindah ruangan. Karena itu keranjang "Belum
// terpindai" ditaruh paling atas dan terbuka sejak awal.
//
// DUA HAL YANG SENGAJA TIDAK OTOMATIS:
//
// 1. Memindai TIDAK memindahkan catatan lokasi. Barang yang ditemukan di tempat
//    lain muncul di "Ditemukan di sini" dan menunggu tombol Terapkan. Salah
//    pindai (stiker tetangga, barang yang sedang dijinjing) karenanya tak pernah
//    diam-diam menulis ulang custody.
// 2. Kode yang cocok dengan lebih dari satu aset TIDAK ditebak. Layar memunculkan
//    daftar kandidat dan menunggu petugas memilih — persis supaya sebuah
//    pengamatan tak pernah tercatat pada gerbong yang salah.
import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ClipboardCheck, Loader2, X, CheckCircle2, MapPinned, PackageSearch,
  CloudOff, RefreshCw, ArrowRightLeft,
} from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import QrScanButton, { extractScannedCode } from "@/components/assets/QrScanButton";
import {
  buatScanId, simpanTertunda, hapusTertunda, bacaTertunda,
  bersihkanKedaluwarsa,
} from "@/lib/antreanScan";
import { checkReachable } from "@/lib/connectivity";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const LABEL = {
  sesuai: "cocok",
  pindah: "beda lokasi",
  baru: "belum punya lokasi",
  tanpa_lokasi: "tanpa node",
};

export default function OpnameDialog({ node, labelLevel, isWriter, onClose }) {
  const [data, setData] = useState(null);
  const [memuat, setMemuat] = useState(true);
  const [dalam, setDalam] = useState(true);
  const [kodeManual, setKodeManual] = useState("");
  const [sibuk, setSibuk] = useState(false);
  const [kandidat, setKandidat] = useState(null);   // {kode, items, scan_id}
  const [tertunda, setTertunda] = useState([]);
  const [terpilih, setTerpilih] = useState(() => new Set());
  const inputRef = useRef(null);
  const reqRef = useRef(0);          // penjaga urutan respons muat()
  const [galat, setGalat] = useState("");

  const segarkanTertunda = useCallback(() => setTertunda(bacaTertunda()), []);

  const muat = useCallback(async (termasuk) => {
    // PENJAGA URUTAN. Mengetuk saklar "termasuk isi di bawahnya" dua kali cepat
    // melahirkan dua permintaan; yang tiba BELAKANGAN belum tentu yang terakhir
    // diminta, sehingga layar bisa menampilkan lingkup yang tak sesuai dengan
    // posisi centangnya. Hanya respons termuda yang boleh menulis state.
    const seq = (reqRef.current += 1);
    setGalat("");
    setMemuat(true);
    try {
      const r = await axios.get(`${API}/opname/rekonsiliasi`, {
        params: { node_id: node.id, dalam: String(termasuk) }, timeout: 25000,
      });
      if (seq !== reqRef.current) return;
      setData(r.data);
      // Pilihan yang MASIH ADA dipertahankan — mengosongkannya di tiap muat
      // ulang membuat centang Terapkan lenyap setiap kali petugas memindai
      // barang berikutnya, tanpa satu pun pemberitahuan (temuan audit).
      const idAda = new Set((r.data?.pindah_masuk || []).map((x) => x.id));
      setTerpilih((lama) => new Set([...lama].filter((id) => idAda.has(id))));
    } catch (e) {
      if (seq !== reqRef.current) return;
      setData(null);
      setGalat(e?.response?.data?.detail || "Gagal memuat rekonsiliasi opname");
      toast.error(e?.response?.data?.detail || "Gagal memuat rekonsiliasi opname");
    } finally {
      if (seq === reqRef.current) setMemuat(false);
    }
  }, [node.id]);

  useEffect(() => {
    bersihkanKedaluwarsa();
    segarkanTertunda();
  }, [segarkanTertunda]);

  useEffect(() => { muat(dalam); }, [muat, dalam]);

  /**
   * Kirim satu scan. `scanId` dibuat SEKALI oleh pemanggil dan dipakai ulang di
   * setiap percobaan — itulah yang membuat pengiriman ulang aman: server
   * memakainya sebagai kunci idempotensi, sehingga tiga kali coba tetap
   * menghasilkan satu catatan.
   */
  const kirim = useCallback(async (kode, scanId, assetId, nodeId, tsScan,
                                  segarkan = true, dititipPada = undefined) => {
    // NODE & WAKTU DATANG DARI PEMANGGIL, BUKAN DARI DIALOG YANG SEDANG TERBUKA.
    // Ini temuan audit paling serius atas fase ini: dulu `kirim` selalu menulis
    // `node_id: node.id`, sehingga tiga puluh scan yang dilakukan luring di
    // Ruang 305 lalu dikirim ulang saat petugas sudah membuka Ruang 307
    // tercatat SELURUHNYA di Ruang 307. Antrean luring yang dibangun untuk
    // melindungi data justru menjadi jalur data tertukar — persis yang dilarang
    // mandat "satu gerbong satu aset".
    //
    // `ts_scan` mengikuti alasan yang sama: waktu KEJADIAN, bukan waktu tiba.
    // Membuat stempel baru saat kirim ulang membuat bukti opname bertanggal
    // hari sinyal pulih, bukan hari barang benar-benar dilihat petugas.
    const muatan = { kode, node_id: nodeId || node.id, scan_id: scanId,
                     ts_scan: tsScan || new Date().toISOString() };
    if (assetId) muatan.asset_id = assetId;
    try {
      const r = await axios.post(`${API}/opname/scan`, muatan, { timeout: 20000 });
      hapusTertunda(scanId);
      segarkanTertunda();
      const s = r.data?.scan || {};
      if (r.data?.duplikat) toast.info(`${s.asset_name} — sudah tercatat`);
      else toast.success(`${s.asset_name} — ${LABEL[s.status_rekonsiliasi] || s.status_rekonsiliasi}`);
      // Saat MENGOSONGKAN ANTREAN, penyegaran ditunda sampai seluruh baris
      // terkirim: enam puluh scan tertunda dulu berarti enam puluh GET
      // rekonsiliasi berat berurutan, tepat saat sinyal baru pulih.
      if (segarkan) await muat(dalam);
      return true;
    } catch (e) {
      const st = e?.response?.status;
      if (st === 409 && e?.response?.data?.detail?.kandidat) {
        // Ambigu: simpan dulu supaya tak hilang bila petugas menutup layar,
        // lalu minta ia memilih.
        // `dititip_pada` DIBAWA dari entri lama. Tanpa itu tiap penyimpanan
        // ulang me-reset umur entri, sehingga `bersihkanKedaluwarsa` 7 hari tak
        // pernah menggigit selama rekonek terus terjadi — dan sejak pengosongan
        // antrean berjalan OTOMATIS, rekonek memang terjadi terus.
        simpanTertunda({ scan_id: scanId, kode, node_id: muatan.node_id,
                         ts_scan: muatan.ts_scan, dititip_pada: dititipPada });
        segarkanTertunda();
        setKandidat({ ...e.response.data.detail, scan_id: scanId,
                      node_id: muatan.node_id, ts_scan: muatan.ts_scan,
                      dititip_pada: dititipPada });
        return false;
      }
      if (!e?.response) {
        // Tak ada respons sama sekali = jaringan, bukan penolakan server.
        // Barangnya sudah dilihat petugas; yang gagal hanya pengirimannya.
        simpanTertunda({ scan_id: scanId, kode, node_id: muatan.node_id,
                         ts_scan: muatan.ts_scan, asset_id: assetId || "",
                         dititip_pada: dititipPada });
        segarkanTertunda();
        toast.warning("Tak ada sinyal — scan disimpan, kirim ulang nanti");
        return false;
      }
      toast.error(e?.response?.data?.detail || "Scan gagal dicatat");
      return false;
    }
  }, [node.id, dalam, muat, segarkanTertunda]);

  const tanganiKode = useCallback(async (mentah) => {
    const kode = extractScannedCode(mentah || "");
    if (!kode) { toast.error("Kode tidak dikenali"); return; }
    setSibuk(true);
    setKandidat(null);
    try {
      await kirim(kode, buatScanId(), "", node.id, new Date().toISOString());
      setKodeManual("");
      inputRef.current?.focus();
    } finally { setSibuk(false); }
  }, [kirim, node.id]);

  const pilihKandidat = useCallback(async (asetId) => {
    if (!kandidat) return;
    setSibuk(true);
    try {
      const ok = await kirim(kandidat.kode, kandidat.scan_id, asetId,
                             kandidat.node_id, kandidat.ts_scan, true,
                             kandidat.dititip_pada);
      if (ok) setKandidat(null);
    } finally { setSibuk(false); }
  }, [kandidat, kirim]);

  // Penjaga satu-aliran: melindungi dari klik ganda DAN dari pemicu otomatis
  // "online" yang datang saat aliran sebelumnya masih jalan.
  const mengalirRef = useRef(false);

  const kirimUlangSemua = useCallback(async () => {
    if (mengalirRef.current) return;
    const antre = bacaTertunda();
    if (!antre.length) return;
    mengalirRef.current = true;
    setSibuk(true);
    let berhasil = 0;
    try {
      for (const item of antre) {
        // Berurutan, bukan serentak: antrean lapangan biasanya puluhan baris di
        // jaringan yang baru saja pulih — membanjirinya justru memicu gagal lagi.
        if (await kirim(item.kode, item.scan_id, item.asset_id,
                        item.node_id, item.ts_scan, false,
                        item.dititip_pada)) berhasil += 1;
      }
      // NADA MENGIKUTI HASIL. `toast.success` untuk "0 dari 30 scan terkirim"
      // adalah layar sukses untuk kegagalan total: petugas membacanya sebagai
      // "opname sudah masuk" padahal ketiga puluh baris masih di perangkat.
      const pesan = `${berhasil} dari ${antre.length} scan terkirim`;
      if (berhasil === 0) toast.error(pesan);
      else if (berhasil < antre.length) toast.warning(pesan);
      else toast.success(pesan);
      // Menyegarkan rekonsiliasi hanya berguna bila ADA yang berubah di server.
      // Bila nol terkirim, jaringannya memang sedang buruk: GET berat ini akan
      // ikut gagal, dan `catch`-nya menyetel data=null — daftar "Belum
      // terpindai" (satu-satunya penunjuk barang yang belum ditemukan di
      // ruangan ini) LENYAP dari layar tanpa petugas menyentuh apa pun.
      if (berhasil > 0) await muat(dalam);
    } finally { mengalirRef.current = false; setSibuk(false); }
  }, [kirim, dalam, muat]);

  // KOSONGKAN ANTREAN SENDIRI BEGITU SINYAL PULIH.
  //
  // Antrean ini lahir tepat ketika jaringan mati di lapangan. Dulu satu-satunya
  // cara mengosongkannya adalah menekan "Kirim ulang" — artinya petugas harus
  // INGAT melakukannya, sambil dialog ini kebetulan masih terbuka. Yang tak
  // terkirim tak pernah masuk rekonsiliasi: barang tercatat "tidak ditemukan"
  // padahal sudah dipindai.
  //
  // Aman diotomatiskan karena `scan_id` dibuat sekali dan dipakai ulang sebagai
  // kunci idempotensi server (lihat catatan di `kirim`) — terkirim dua kali
  // tetap satu catatan. Lewat ref supaya pemasangan listener tak ikut berganti
  // tiap kali `kirimUlangSemua` dibuat ulang.
  //
  // TAPI EVENT `online` SAJA TAK CUKUP JADI ALASAN MENGIRIM. Peramban
  // memancarkannya begitu antarmuka jaringan naik — captive portal hotel, satu
  // bar sinyal, Wi-Fi yang tersambung tapi tak mengantar apa-apa. Tanpa
  // pemeriksaan, tiga puluh baris antrean berarti tiga puluh POST BERURUTAN yang
  // masing-masing menunggu tenggat 20 dtk: sepuluh menit `sibuk === true`,
  // tombol Catat/Terapkan mati, dan badai tiga puluh toast — semuanya tanpa
  // petugas menyentuh apa pun. Repo ini sudah punya obatnya dan dipakai
  // useOptimisticQueue: `checkReachable()` menembak GET /api/health lebih dulu,
  // plus peredam agar kedip online/offline tak memicu berulang.
  const kirimUlangRef = useRef(kirimUlangSemua);
  kirimUlangRef.current = kirimUlangSemua;
  const redamRef = useRef(false);
  useEffect(() => {
    const pulih = async () => {
      if (redamRef.current || !bacaTertunda().length) return;
      redamRef.current = true;
      setTimeout(() => { redamRef.current = false; }, 3000);
      if (!(await checkReachable())) return;   // sinyal naik ≠ server terjangkau
      kirimUlangRef.current?.();
    };
    window.addEventListener("online", pulih);
    return () => window.removeEventListener("online", pulih);
  }, []);

  const terapkan = useCallback(async () => {
    const ids = [...terpilih];
    if (!ids.length) return;
    setSibuk(true);
    try {
      const r = await axios.post(`${API}/opname/terapkan`, { scan_ids: ids },
                                 { timeout: 25000 });
      toast.success(`${r.data?.jumlah_diterapkan ?? 0} lokasi diperbarui`);
      await muat(dalam);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menerapkan perpindahan");
    } finally { setSibuk(false); }
  }, [terpilih, dalam, muat]);

  const togglePilih = (id) => setTerpilih((s) => {
    const baru = new Set(s);
    if (baru.has(id)) baru.delete(id); else baru.add(id);
    return baru;
  });

  const ringkas = data?.ringkas || {};
  const belum = data?.belum_terpindai || [];
  const sesuai = data?.sesuai || [];
  const masuk = data?.pindah_masuk || [];

  return (
    <Dialog open onOpenChange={(o) => !o && onClose?.()}>
      {/* max-h + overflow-y WAJIB: DialogContent bawaan membawa `overflow-hidden`,
          sehingga di layar HP tombol Terapkan & Tutup terpotong di luar viewport
          dan tak ada cara menggulirnya (temuan audit). */}
      <DialogContent className="max-w-lg"
                     data-testid="opname-dialog">
        <DialogHeader>
          <DialogTitle className="text-sm flex items-center gap-1.5">
            <ClipboardCheck className="w-4 h-4 text-emerald-600" />
            Opname: {node.nama}
          </DialogTitle>
          <DialogDescription className="text-xs">
            {(labelLevel?.[node.tipe] || node.tipe)} — pindai stiker QR untuk
            mengukuhkan keberadaan barang. Memindai TIDAK memindahkan catatan
            lokasi; perpindahan diterapkan terpisah.
          </DialogDescription>
        </DialogHeader>

        {/* Baris pindai — ikon di HP, melebar di layar besar; tak pernah pecah baris. */}
        {!isWriter ? (
          <p className="text-[11px] text-muted-foreground rounded-lg border border-border px-2 py-1.5"
             data-testid="opname-viewer">
            Akun baca-saja: rekonsiliasi boleh dilihat, tetapi memindai butuh
            akses tulis — server akan menolak setiap pindaian dari akun ini.
          </p>
        ) : (
        <div className="flex items-center gap-1.5">
          <QrScanButton onDetected={tanganiKode} />
          <Input
            ref={inputRef}
            value={kodeManual}
            onChange={(e) => setKodeManual(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") tanganiKode(kodeManual); }}
            placeholder="Ketik kode bila stiker rusak…"
            className="h-9 text-xs min-w-0 flex-1"
            data-testid="opname-kode-manual"
          />
          <Button size="sm" className="h-9 px-2.5 text-xs shrink-0"
                  disabled={sibuk || !kodeManual.trim()}
                  onClick={() => tanganiKode(kodeManual)}
                  data-testid="opname-catat">
            {sibuk ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Catat"}
          </Button>
        </div>
        )}

        {kandidat && (
          <div className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-2"
               data-testid="opname-kandidat">
            <p className="text-[11px] font-semibold mb-1.5">
              Kode “{kandidat.kode}” cocok dengan {kandidat.kandidat?.length} aset —
              pilih yang benar:
            </p>
            <ul className="space-y-1">
              {(kandidat.kandidat || []).map((a) => (
                <li key={a.id}>
                  <button type="button" disabled={sibuk}
                          onClick={() => pilihKandidat(a.id)}
                          className="w-full text-left px-2 py-1 rounded bg-background hover:bg-muted text-[11px] disabled:opacity-50"
                          data-testid={`opname-kandidat-${a.id}`}>
                    <span className="font-semibold">{a.asset_name}</span>
                    <span className="text-muted-foreground">
                      {" "}· {a.asset_code}{a.NUP ? ` · NUP ${a.NUP}` : ""}
                      {a.lokasi_spasial?.node_nama ? ` · ${a.lokasi_spasial.node_nama}` : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <button type="button"
                    onClick={() => { hapusTertunda(kandidat.scan_id);
                                     segarkanTertunda(); setKandidat(null); }}
                    className="text-[11px] underline text-muted-foreground mt-1.5"
                    data-testid="opname-kandidat-batal">
              Batalkan scan ini
            </button>
          </div>
        )}

        {tertunda.length > 0 && (
          <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-2 py-1.5"
               data-testid="opname-tertunda">
            <CloudOff className="w-3.5 h-3.5 text-amber-600 shrink-0" />
            <p className="text-[11px] flex-1 min-w-0">
              {tertunda.length} scan menunggu terkirim
            </p>
            <Button variant="outline" size="sm" disabled={sibuk}
                    className="h-7 px-2 text-[11px] shrink-0"
                    onClick={kirimUlangSemua} data-testid="opname-kirim-ulang">
              <RefreshCw className="w-3 h-3 mr-1" />Kirim ulang
            </Button>
          </div>
        )}

        <label className="flex items-center gap-2 text-xs">
          <input type="checkbox" checked={dalam}
                 onChange={(e) => setDalam(e.target.checked)}
                 data-testid="opname-dalam" />
          <span>Termasuk seluruh isi di bawahnya (lantai, ruangan, …)</span>
        </label>

        <div className="grid grid-cols-3 gap-1.5 text-center">
          {[["Tercatat", ringkas.harapan ?? 0],
            ["Dikukuhkan", ringkas.sesuai ?? 0],
            ["Sisa dicari", ringkas.belum_terpindai ?? 0]].map(([l, v]) => (
            <div key={l} className="rounded-lg border border-border py-1.5">
              <p className="text-sm font-bold tabular-nums">{v}</p>
              <p className="text-[10px] text-muted-foreground">{l}</p>
            </div>
          ))}
        </div>
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div className="h-full bg-emerald-500 transition-all"
               style={{ width: `${ringkas.persen_terkonfirmasi ?? 0}%` }}
               data-testid="opname-bar" />
        </div>
        <p className="text-[10px] text-muted-foreground -mt-1">
          {ringkas.persen_terkonfirmasi ?? 0}% aset tercatat sudah dibuktikan fisik
        </p>

        <div className="rounded-lg border border-border max-h-[38vh] overflow-y-auto divide-y divide-border/60">
          {memuat ? (
            <div className="flex items-center justify-center py-10 text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Memuat…
            </div>
          ) : (
            <>
              <Bagian ikon={<PackageSearch className="w-3.5 h-3.5 text-amber-600" />}
                      judul={`Belum terpindai (${belum.length})`}
                      kosong="Semua barang tercatat sudah dikukuhkan."
                      testid="opname-belum">
                {belum.map((a) => (
                  <BarisAset key={a.id} a={a} />
                ))}
              </Bagian>

              <Bagian ikon={<ArrowRightLeft className="w-3.5 h-3.5 text-sky-600" />}
                      judul={`Ditemukan di sini (${masuk.length})`}
                      kosong="Tak ada barang asing yang terpindai di lokasi ini."
                      testid="opname-masuk">
                {masuk.map((s) => (
                  <li key={s.id} className="px-3 py-2 flex items-start gap-2">
                    {isWriter && (
                      <input type="checkbox" className="mt-0.5 shrink-0"
                             checked={terpilih.has(s.id)}
                             onChange={() => togglePilih(s.id)}
                             disabled={s.diterapkan}
                             data-testid={`opname-pilih-${s.id}`} />
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="text-xs font-semibold block truncate">
                        {s.asset_name}
                      </span>
                      <span className="text-[11px] text-muted-foreground block truncate">
                        {[s.asset_code && `${s.asset_code}${s.NUP ? ` · ${s.NUP}` : ""}`,
                          s.lokasi_sebelum?.nama
                            ? `buku: ${s.lokasi_sebelum.nama}`
                            : "belum punya lokasi",
                          s.diterapkan && "sudah diterapkan"]
                          .filter(Boolean).join(" · ")}
                      </span>
                    </span>
                  </li>
                ))}
              </Bagian>

              <Bagian ikon={<CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
                      judul={`Cocok (${sesuai.length})`}
                      kosong="Belum ada yang dikukuhkan."
                      testid="opname-sesuai">
                {sesuai.map((a) => <BarisAset key={a.id} a={a} />)}
              </Bagian>
            </>
          )}
        </div>

        <div className="flex items-center gap-2 pt-1">
          {isWriter && (
            <Button size="sm" className="h-8 text-xs"
                    disabled={sibuk || terpilih.size === 0}
                    onClick={terapkan} data-testid="opname-terapkan">
              <MapPinned className="w-3.5 h-3.5 mr-1" />
              Terapkan {terpilih.size > 0 ? `(${terpilih.size})` : ""}
            </Button>
          )}
          <span className="flex-1" />
          <Button variant="outline" size="sm" className="h-8 text-xs"
                  onClick={() => onClose?.()} data-testid="opname-tutup">
            <X className="w-3.5 h-3.5 mr-1" />Tutup
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Bagian({ ikon, judul, kosong, testid, children }) {
  const isi = React.Children.toArray(children);
  return (
    <div data-testid={testid}>
      <p className="px-3 py-1.5 text-[11px] font-semibold flex items-center gap-1.5 bg-muted/40 sticky top-0">
        {ikon}{judul}
      </p>
      {isi.length === 0
        ? <p className="px-3 py-3 text-[11px] text-muted-foreground">{kosong}</p>
        : <ul className="divide-y divide-border/40">{isi}</ul>}
    </div>
  );
}

function BarisAset({ a }) {
  return (
    <li className="px-3 py-2">
      <p className="text-xs font-semibold truncate">{a.asset_name}</p>
      <p className="text-[11px] text-muted-foreground truncate">
        {[a.asset_code && `${a.asset_code}${a.NUP ? ` · ${a.NUP}` : ""}`,
          a.condition, a.lokasi_spasial?.node_nama]
          .filter(Boolean).join(" · ")}
      </p>
    </li>
  );
}
