import React, { useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import { FileDown, FileSignature, Loader2, Search } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Dialog pemilihan barang untuk Nota Dinas persediaan — stok kritis/habis
 * MAUPUN kedaluwarsa.
 *
 * Permintaan pemilik: tidak semua yang habis/kritis harus diusulkan pengadaan
 * ulang, dan hal yang sama berlaku untuk nota kedaluwarsa — jadi SETIAP nota
 * dinas memilih barangnya sendiri. Default semua tercentang (perilaku lama =
 * satu klik lagi), dan server tetap memvalidasi pilihan terhadap daftar
 * peringatan aslinya: id di luar daftar diabaikan, bukan disisipkan.
 *
 * SATU HAL YANG MENENTUKAN BENTUK LAYAR INI: pada nota kedaluwarsa, satu
 * barang bisa punya BEBERAPA baris — tiap layer (batch) punya tanggal
 * kedaluwarsa sendiri — sementara penyaring server bekerja per `id` BARANG.
 * Maka pilihannya disajikan per barang, bukan per layer; mencentang satu
 * barang berarti seluruh layer-nya ikut. Menyajikan per layer akan menipu:
 * melepas satu layer diam-diam melepas layer lain milik barang yang sama.
 */

/** Ringkas baris peringatan → satu entri per BARANG (layer digabung). */
export function kelompokkanPerBarang(rows) {
  const peta = new Map();
  for (const r of rows || []) {
    if (!r || !r.id) continue;
    const ada = peta.get(r.id);
    const qty = Number(r.qty) || 0;
    if (!ada) {
      peta.set(r.id, {
        ...r, n_layer: 1, total_qty: qty,
        // Tanggal terdekat = yang paling mendesak; itulah yang pantas
        // ditampilkan saat beberapa layer diringkas jadi satu baris.
        expired_terdekat: r.expired || "",
      });
      continue;
    }
    ada.n_layer += 1;
    ada.total_qty += qty;
    if (r.expired && (!ada.expired_terdekat || r.expired < ada.expired_terdekat)) {
      ada.expired_terdekat = r.expired;
    }
  }
  return [...peta.values()];
}

const JUDUL = {
  kritis: "NOTA DINAS — Usulan Pengadaan (Stok Kritis/Habis)",
  kedaluwarsa: "NOTA DINAS — Persediaan Kedaluwarsa",
};
const LABEL_TOMBOL = {
  kritis: "Nota Dinas Kritis",
  kedaluwarsa: "Nota Dinas Kedaluwarsa",
};
const NAMA_BERKAS = {
  kritis: "Nota_Dinas_Stok_Kritis.pdf",
  kedaluwarsa: "Nota_Dinas_Kedaluwarsa.pdf",
};

/**
 * Saring daftar barang menurut kata kunci — nama ATAU kode.
 *
 * Kata kunci dipecah per kata dan SELURUHNYA harus ada, boleh pada field yang
 * berbeda: "tinta hitam" menemukan "Tinta Printer Hitam", dan "K002 tinta"
 * menemukan barang yang sama lewat kodenya. Pencocokan satu frasa utuh akan
 * gagal pada keduanya, padahal itulah cara orang mengetik saat mencari.
 */
export function saringBarang(daftar, kata) {
  const kunci = String(kata || "").trim().toLowerCase().split(/\s+/)
    .filter(Boolean);
  if (!kunci.length) return daftar || [];
  return (daftar || []).filter((it) => {
    const teks = `${it.nama_barang || ""} ${it.kode_barang || ""}`.toLowerCase();
    return kunci.every((k) => teks.includes(k));
  });
}

/**
 * Daftar barang terpilih → entri `ids` untuk server.
 *
 * Satu format untuk dua jalur (pratinjau lewat kueri, penerbitan lewat JSON):
 * `"<id>"` bila jumlahnya belum diisi, `"<id>:<jumlah>"` bila diisi. Jumlah
 * yang tak masuk akal (kosong, nol, negatif, bukan angka) sengaja DIBUANG,
 * bukan dikirim sebagai nol: nol yang tercetak di naskah resmi terbaca sebagai
 * permintaan nol unit, sementara "-" jujur menyatakan belum ditentukan.
 */
export function entriPilihan(items, jumlah) {
  const peta = jumlah || {};
  return (items || []).map((it) => {
    const n = parseInt(String(peta[it.id] ?? "").trim(), 10);
    return Number.isFinite(n) && n > 0 ? `${it.id}:${n}` : String(it.id);
  });
}

/** Total unit yang diusulkan dari peta jumlah — 0 bila belum ada yang diisi. */
export function totalDiusulkan(items, jumlah) {
  const peta = jumlah || {};
  return (items || []).reduce((jml, it) => {
    const n = parseInt(String(peta[it.id] ?? "").trim(), 10);
    return jml + (Number.isFinite(n) && n > 0 ? n : 0);
  }, 0);
}

export default function NotaDinasDialog({ items, jenis = "kritis", onTerbit }) {
  const [open, setOpen] = useState(false);
  const [cari, setCari] = useState("");
  const [terbitLoading, setTerbitLoading] = useState(false);
  // {id: teks jumlah usulan}. Disimpan sebagai TEKS, bukan angka: mengubahnya
  // jadi angka saat diketik membuat isian yang sedang dikosongkan melompat
  // kembali ke 0 di tengah pengetikan.
  const [jumlah, setJumlah] = useState({});
  // Set id yang TIDAK dicentang — default kosong berarti semua terpilih,
  // dan pilihan tak perlu diinisialisasi ulang saat daftar peringatan segar.
  const [batal, setBatal] = useState(() => new Set());

  const daftar = useMemo(
    () => (jenis === "kedaluwarsa" ? kelompokkanPerBarang(items) : (items || [])),
    [items, jenis]);
  const terpilih = useMemo(
    () => daftar.filter((it) => !batal.has(it.id)), [daftar, batal]);
  // Yang TAMPIL menyusut mengikuti pencarian; yang TERPILIH tidak. Barang yang
  // tersembunyi oleh kata kunci tetap ikut ke nota dinas — daftar yang
  // menyaring sekaligus melepas centang akan membuang pilihan yang sudah
  // dibuat, tanpa satu pun tanda.
  const tampil = useMemo(() => saringBarang(daftar, cari), [daftar, cari]);

  const toggle = (id) => setBatal((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  // Daftar id dikirim HANYA saat sebagian dipilih. Mengirimnya selalu membuat
  // server memperlakukan nota lengkap sebagai nota tersaring, dan naskahnya
  // lalu memuat kalimat "sengaja tidak disertakan" pada daftar yang utuh.
  const sebagian = terpilih.length !== daftar.length;
  // Jumlah usulan menumpang parameter yang sama. Karena itu `ids` juga harus
  // dikirim saat SELURUH barang terpilih tetapi jumlahnya sudah diisi —
  // tanpa itu, angka yang baru saja diketik petugas hilang tanpa satu pun
  // tanda. Server menentukan "tersaring" dari panjang daftarnya, bukan dari
  // ada-tidaknya `ids`, sehingga nota lengkap tetap tak mengaku tersaring.
  const entri = entriPilihan(terpilih, jumlah);
  const adaJumlah = entri.some((e) => e.includes(":"));
  const kirimIds = sebagian || adaJumlah;
  const total = totalDiusulkan(terpilih, jumlah);

  const unduh = () => {
    const param = kirimIds
      ? `&ids=${encodeURIComponent(entri.join(","))}` : "";
    downloadFileWithProgress(
      `${API}/persediaan/nota-dinas?jenis=${jenis}${param}`,
      NAMA_BERKAS[jenis],
      { label: `Pratinjau ${LABEL_TOMBOL[jenis]}` }).catch(() => {});
    setOpen(false);
  };

  // Terbitkan = booking nomor + bekukan daftarnya di register, lalu unduh
  // naskah yang benar-benar terbit. Unduhan tak pernah membooking nomor
  // sendiri: tombol unduh ditekan berkali-kali, dan tiap nomor surat yang
  // terpesan tak pernah dipakai ulang.
  const terbitkan = async () => {
    setTerbitLoading(true);
    try {
      const { data } = await axios.post(`${API}/persediaan/nota-dinas/terbitkan`, {
        jenis, ids: kirimIds ? entri : [],
      });
      toast.success(data?.message || "Nota dinas terbit");
      setOpen(false);
      onTerbit?.(data);
      downloadFileWithProgress(
        `${API}/persediaan/nota-dinas/${data.id}/pdf`,
        `${NAMA_BERKAS[jenis].replace(/\.pdf$/, "")}_${data.nomor || data.id.slice(0, 8)}.pdf`,
        { label: LABEL_TOMBOL[jenis] }).catch(() => {});
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menerbitkan nota dinas");
    } finally {
      setTerbitLoading(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="h-8 px-2.5 rounded-lg border border-amber-400 dark:border-amber-600 text-[11px] font-semibold text-amber-800 dark:text-amber-300 flex items-center gap-1 hover:bg-amber-100 dark:hover:bg-amber-900/40 min-w-0 min-h-0"
        data-testid={`persediaan-nota-${jenis}`}
      >
        <FileDown className="w-3.5 h-3.5" />{LABEL_TOMBOL[jenis]}
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Pilih Barang untuk {JUDUL[jenis]}</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-muted-foreground">
            {jenis === "kedaluwarsa"
              ? "Centang barang yang akan dimasukkan ke nota dinas. Satu barang bisa punya beberapa layer bertanggal berbeda — memilih barang berarti SELURUH layer-nya ikut."
              : "Centang barang yang akan diusulkan pengadaannya — yang tidak dicentang tidak masuk nota dinas. Isi kolom jumlah bila banyaknya sudah ditentukan; yang dikosongkan tercetak \u201c-\u201d pada naskah."}
          </p>
          {/* Pencarian: daftar peringatan bisa memuat ratusan barang, dan
              mencentang satu di antaranya berarti menggulir mencarinya. */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            <Input value={cari} onChange={(e) => setCari(e.target.value)}
              placeholder="Cari nama atau kode barang…"
              className="h-9 pl-8 text-xs"
              data-testid={`nota-${jenis}-cari`} />
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {/* Kedua tombol bekerja pada yang SEDANG TAMPIL. Bekerja pada
                seluruh daftar sementara layarnya tersaring membuat satu klik
                menyentuh barang yang tak terlihat sama sekali. */}
            <Button size="sm" variant="outline"
              onClick={() => setBatal((prev) => {
                const next = new Set(prev);
                tampil.forEach((it) => next.delete(it.id));
                return next;
              })}
              data-testid={`nota-${jenis}-semua`}>
              Pilih semua{cari ? " (tampil)" : ""}
            </Button>
            <Button size="sm" variant="outline"
              onClick={() => setBatal((prev) => {
                const next = new Set(prev);
                tampil.forEach((it) => next.add(it.id));
                return next;
              })}
              data-testid={`nota-${jenis}-kosongkan`}>
              Kosongkan{cari ? " (tampil)" : ""}
            </Button>
            {/* Cacahnya menyebut SELURUH daftar, bukan yang tampil: dengan
                pencarian aktif, yang menentukan isi nota dinas tetap
                keseluruhannya. */}
            <span className="text-[11px] text-muted-foreground ml-auto"
              data-testid={`nota-${jenis}-cacah`}>
              {terpilih.length} dari {daftar.length} dipilih
              {total > 0 ? ` · ${total} unit diusulkan` : ""}
              {cari ? ` · menampilkan ${tampil.length}` : ""}
            </span>
          </div>
          <ul className="divide-y divide-border">
            {cari && tampil.length === 0 && (
              <li className="py-3 text-center text-xs text-muted-foreground"
                data-testid={`nota-${jenis}-nihil`}>
                Tak ada barang yang cocok dengan &ldquo;{cari}&rdquo;.
                Pilihan yang sudah dibuat tetap tersimpan.
              </li>
            )}
            {tampil.map((it) => (
              <li key={it.id}>
                <label className="flex items-center gap-2.5 py-2 cursor-pointer">
                  <input type="checkbox" checked={!batal.has(it.id)}
                    onChange={() => toggle(it.id)}
                    className="min-w-0 min-h-0"
                    data-testid={`nota-${jenis}-item-${it.id}`} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm text-foreground truncate">
                      {it.nama_barang}
                    </span>
                    <span className="block text-[11px] text-muted-foreground">
                      {jenis === "kedaluwarsa" ? (
                        <>
                          {it.kode_barang} · {it.total_qty} {it.satuan || ""}
                          {it.n_layer > 1 ? ` · ${it.n_layer} layer` : ""}
                          {it.expired_terdekat ? ` · terdekat ${it.expired_terdekat}` : ""}
                        </>
                      ) : (
                        <>
                          {it.kode_barang} · stok {it.stok}
                          {" "}/ batas {it.batas_kritis || 0} {it.satuan || ""}
                        </>
                      )}
                    </span>
                  </span>
                  {/* Jumlah yang ingin diadakan — hanya pada nota usulan
                      pengadaan. Nota kedaluwarsa tidak meminta pengadaan;
                      jumlahnya sudah ditentukan isi layer yang kedaluwarsa.

                      Sengaja TIDAK diisi nilai tebakan (mis. batas kritis
                      dikurangi stok): angka yang terisi sendiri akan lolos
                      tanpa dibaca, lalu tercetak sebagai permintaan resmi
                      yang tak pernah diketik siapa pun. Kosong tercetak "-". */}
                  {jenis === "kritis" && (
                    <span className="flex-shrink-0" onClick={(e) => e.preventDefault()}>
                      <input type="number" min="1" step="1" placeholder="jml"
                        value={jumlah[it.id] ?? ""}
                        onChange={(e) => setJumlah((prev) => ({
                          ...prev, [it.id]: e.target.value }))}
                        aria-label={`Jumlah diusulkan untuk ${it.nama_barang}`}
                        className="w-16 h-8 px-2 rounded-lg border border-border bg-background text-xs text-right min-w-0 min-h-0"
                        data-testid={`nota-${jenis}-jumlah-${it.id}`} />
                    </span>
                  )}
                  <span className={`px-2 py-0.5 rounded-full text-[11px] flex-shrink-0 ${
                    (jenis === "kedaluwarsa" ? it.lewat : it.stok <= 0)
                      ? "bg-red-500/15 text-red-600 dark:text-red-400"
                      : "bg-amber-500/15 text-amber-600 dark:text-amber-400"}`}>
                    {jenis === "kedaluwarsa"
                      ? (it.lewat ? "kedaluwarsa" : "segera")
                      : (it.stok <= 0 ? "habis" : "kritis")}
                  </span>
                </label>
              </li>
            ))}
          </ul>
          {/* DUA tindakan yang sengaja dibedakan: pratinjau tak bernomor dan
              tak meninggalkan jejak; menerbitkan memesan nomor surat yang tak
              pernah dipakai ulang. Satu tombol untuk keduanya akan membuat
              orang memesan nomor hanya karena ingin melihat dokumennya. */}
          <div className="flex flex-col gap-1.5">
            <Button disabled={terpilih.length === 0 || terbitLoading}
              onClick={terbitkan}
              data-testid={`nota-${jenis}-terbitkan`}>
              {terbitLoading
                ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                : <FileSignature className="w-4 h-4 mr-1.5" />}
              Terbitkan &amp; Unduh ({terpilih.length} barang)
            </Button>
            <Button variant="outline" disabled={terpilih.length === 0}
              onClick={unduh}
              data-testid={`nota-${jenis}-unduh`}>
              <FileDown className="w-4 h-4 mr-1.5" />
              Unduh pratinjau (tanpa nomor)
            </Button>
            <p className="text-[11px] text-muted-foreground">
              Menerbitkan memesan nomor surat dari Registrasi Persuratan dan
              membekukan daftar barangnya — naskahnya tidak lagi berubah
              meski stok bergerak. Pratinjau tidak memesan nomor.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
