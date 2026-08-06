import React, { useState, useEffect, memo } from "react";
import { Image, FileDown } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import axios from "axios";
import { ringkasAktif } from "../../lib/kompresiAktif";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Helper to get color classes based on usage percentage
function getStatusColors(usagePercent) {
  if (usagePercent >= 90) return { bar: "bg-red-500", text: "text-red-600 dark:text-red-400", bg: "bg-red-50 dark:bg-red-900/20" };
  if (usagePercent >= 70) return { bar: "bg-amber-500", text: "text-amber-600 dark:text-amber-400", bg: "bg-amber-50 dark:bg-amber-900/20" };
  return { bar: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-900/20" };
}

// Satu sumber data kuota untuk kedua varian (desktop & HP) — dulu varian HP
// mengambil datanya sendiri dan hasilnya bisa beda dengan varian desktop.
function useKuota() {
  const [imageQuotas, setImageQuotas] = useState([]);
  const [pdfQuotas, setPdfQuotas] = useState([]);
  // Layanan yang AKAN melayani kompresi berikutnya, dihitung server.
  const [aktifGambar, setAktifGambar] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [imgResp, pdfResp] = await Promise.allSettled([
          axios.get(`${API}/compression-quotas`),
          axios.get(`${API}/pdf-compression-quotas`),
        ]);
        if (imgResp.status === "fulfilled") {
          setImageQuotas(imgResp.value.data.quotas || []);
          setAktifGambar(imgResp.value.data.aktif || "");
        }
        if (pdfResp.status === "fulfilled") setPdfQuotas(pdfResp.value.data.quotas || []);
      } catch (e) {
        console.warn("Quota fetch error:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
    const interval = setInterval(fetchAll, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  return { imageQuotas, pdfQuotas, aktifGambar, loading };
}

// Panel rincian kuota — dipakai popover desktop DAN HP supaya informasinya
// identik dari pintu mana pun dibuka.
function PanelKuota({ imageQuotas, pdfQuotas, aktifGambar }) {
  return (
    <div className="p-3 space-y-3">
      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <Image className="w-4 h-4 text-blue-400" />
          <span className="font-medium text-sm">Kompresi Gambar</span>
        </div>
        <div className="space-y-1.5">
          {/* SELURUH mata rantai ditampilkan, termasuk yang kuncinya belum
              dipasang. Dulu daftar ini disaring `available || used > 0`,
              sehingga Uploadcare lenyap dari layar padahal namanya disebut
              di baris "Urutan" tepat di bawah — operator melihat rantai yang
              tak lengkap dan tak tahu MENGAPA satu mata rantai dilewati. */}
          {imageQuotas.map(q => {
            const pct = q.limit > 0 ? (q.used / q.limit) * 100 : 0;
            const colors = getStatusColors(pct);
            const iniAktif = q.service === aktifGambar;
            const belumDisetel = q.terpasang === false;
            return (
              <div key={q.service}
                   className={`flex items-center gap-2 ${belumDisetel ? "opacity-45" : ""}`}
                   data-testid={`kuota-baris-${q.service}`}>
                <span className="text-[11px] text-slate-400 w-20 truncate" title={q.name}>{q.name}</span>
                <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                  <div className={`h-full ${colors.bar}`} style={{ width: `${Math.min(pct, 100)}%` }} />
                </div>
                {iniAktif && (
                  <span className="text-[9px] px-1 py-px rounded bg-emerald-500/20 text-emerald-300 whitespace-nowrap"
                        data-testid="kuota-penanda-aktif">dipakai</span>
                )}
                <span className="text-[11px] font-mono w-16 text-right">
                  {belumDisetel ? (
                    <span className="text-slate-500">belum</span>
                  ) : q.limit < 0 ? (
                    <span className="text-emerald-400">∞</span>
                  ) : (
                    <span className={q.remaining < 50 ? 'text-amber-400' : ''}>{q.remaining}/{q.limit}</span>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {pdfQuotas.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2 pt-2 border-t border-slate-700">
            <FileDown className="w-4 h-4 text-purple-400" />
            <span className="font-medium text-sm">Kompresi PDF</span>
          </div>
          <div className="space-y-1.5">
            {pdfQuotas.filter(q => q.available || q.used > 0).map(q => {
              const pct = q.limit > 0 ? (q.used / q.limit) * 100 : 0;
              const colors = getStatusColors(pct);
              return (
                <div key={q.service} className="flex items-center gap-2">
                  <span className="text-[11px] text-slate-400 w-20 truncate">{q.name}</span>
                  <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                    <div className={`h-full ${colors.bar}`} style={{ width: `${Math.min(pct, 100)}%` }} />
                  </div>
                  <span className="text-[11px] font-mono w-16 text-right">
                    <span className={q.remaining < 10 ? 'text-amber-400' : ''}>{q.remaining}/{q.limit}</span>
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <p className="text-[10px] text-slate-500 leading-tight pt-1 border-t border-slate-700">
        Urutan: Tinify → Compresto → Uploadcare → Lokal. Otomatis beralih jika kuota habis.
      </p>
    </div>
  );
}

// ============================================================================
// INDIKATOR KUOTA KOMPRESI — chip ringkas yang DIKLIK untuk membuka rincian.
//
// Dulu rinciannya hanya hidup di Tooltip (hover) sementara onClick men-toggle
// state `expanded` yang tak pernah dipakai merender apa pun — di tablet & HP
// (tanpa hover) mengetuknya benar-benar tidak menampilkan apa-apa. Popover
// bekerja untuk sentuhan DAN kursor, jadi satu mekanisme untuk semua layar.
//
// `flex-shrink-0` BUKAN hiasan. Chip ini hidup di baris toolbar `flex-nowrap`
// tempat SEMUA saudaranya sudah `flex-shrink-0`; begitu barisnya meluap,
// seluruh kekurangan ruang jatuh ke satu-satunya item yang boleh menyusut —
// chip ini — dan `min-w-0` (dulu ada di sini) membuang lantai lebar min-content
// sehingga ia bisa tergencet sampai nyaris nol: yang tampak di layar tinggal
// serpihan hijau berisi potongan angka. Terukur pada replika toolbar dengan
// CSS produksi: 101px alami → 63px pada 1280px. Karena itu chip TIDAK boleh
// menyusut; kalau baris memang tak muat, `overflow-x-auto` milik toolbar yang
// mengurusnya (itu memang katup pengaman yang sudah dirancang di sana).
// ============================================================================
const TinifyQuotaIndicator = memo(({ className = "" }) => {
  const { imageQuotas, pdfQuotas, aktifGambar, loading } = useKuota();
  if (loading) return null;

  // Angka yang ditampilkan HARUS milik layanan yang benar-benar melayani
  // permintaan berikutnya — bukan Tinify yang kebetulan pertama di daftar.
  // Persentase juga diambil dari layanan itu, bukan dari jumlah SELURUH
  // layanan: "tangki mana yang sedang kita pakai, dan seberapa penuh" adalah
  // pertanyaan yang berguna, sedangkan rata-rata gabungan tak berarti apa-apa
  // (Tinify habis + Uploadcare kosong = "26% terpakai", terlihat sehat).
  const aktif = ringkasAktif(imageQuotas, aktifGambar);
  const imgColors = aktif.takTerbatas
    ? getStatusColors(0)   // Pillow tak berkuota — jangan pernah beralarm merah
    : getStatusColors(aktif.persen);
  const judul = aktif.nama
    ? `Kompresi aktif: ${aktif.nama} — sisa ${aktif.takTerbatas ? "tak terbatas" : aktif.teks}. Ketuk untuk rincian.`
    : "Kuota kompresi — ketuk untuk rincian";

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={judul}
          title={judul}
          className={`flex flex-shrink-0 items-center gap-1.5 px-2 py-1 rounded-md border cursor-pointer transition-all hover:shadow-sm min-h-0 ${imgColors.bg} border-current/10 ${className}`}
          data-testid="kuota-indikator"
        >
          <Image className={`w-3.5 h-3.5 flex-shrink-0 ${imgColors.text}`} />
          <span className={`text-xs font-semibold tabular-nums ${imgColors.text}`}>
            {aktif.teks}
          </span>
          {/* Bar mini hanya di layar SANGAT lebar (2xl+). Di 1280–1535 label
              semua tombol toolbar menyala serentak dan barisnya jadi sesak;
              32px bar ini justru yang mendorongnya meluap. Angkanya tetap
              terbaca, dan bar lengkap tiap layanan ada di dalam popover. */}
          <div className="hidden 2xl:block w-8 h-1.5 bg-muted rounded-full overflow-hidden">
            <div className={`h-full ${imgColors.bar} transition-all`} style={{ width: `${Math.min(aktif.persen, 100)}%` }} />
          </div>
        </button>
      </PopoverTrigger>
      <PopoverContent side="bottom" align="end" className="bg-slate-900 text-white border-slate-700 p-0 w-[320px] max-w-[92vw] shadow-xl">
        <PanelKuota imageQuotas={imageQuotas} pdfQuotas={pdfQuotas} aktifGambar={aktifGambar} />
      </PopoverContent>
    </Popover>
  );
});

TinifyQuotaIndicator.displayName = "TinifyQuotaIndicator";

// Varian HP: angka BERTUMPUK (sisa di atas, batas di bawah) — permintaan
// pemilik: hemat ruang kiri-kanan pada baris toolbar HP yang sudah sesak.
// Tetap tombol: ketukan membuka panel rincian yang sama dengan desktop.
export const TinifyQuotaMobile = memo(({ className = "" }) => {
  const { imageQuotas, pdfQuotas, aktifGambar, loading } = useKuota();
  if (loading || imageQuotas.length === 0) return null;

  const aktif = ringkasAktif(imageQuotas, aktifGambar);
  if (!aktif.entri) return null;

  const colors = aktif.takTerbatas ? getStatusColors(0) : getStatusColors(aktif.persen);
  // Baris bawah = batas layanan aktif. Pillow tak berbatas, jadi yang
  // ditampilkan namanya ("lokal") — angka "‑1" akan membingungkan.
  const barisBawah = aktif.takTerbatas ? "lokal" : String(aktif.entri.limit);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Kompresi aktif: ${aktif.nama} — ketuk untuk rincian`}
          className={`flex flex-col items-center justify-center leading-none px-1 rounded-md min-w-0 min-h-0 ${colors.bg} ${className}`}
          data-testid="kuota-indikator-hp"
        >
          <span className={`text-[10px] font-bold tabular-nums ${colors.text}`}>{aktif.teks}</span>
          <span className="text-[8px] text-muted-foreground tabular-nums border-t border-current/20 w-full text-center">{barisBawah}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent side="bottom" align="end" className="bg-slate-900 text-white border-slate-700 p-0 w-[320px] max-w-[92vw] shadow-xl">
        <PanelKuota imageQuotas={imageQuotas} pdfQuotas={pdfQuotas} aktifGambar={aktifGambar} />
      </PopoverContent>
    </Popover>
  );
});

TinifyQuotaMobile.displayName = "TinifyQuotaMobile";

export default TinifyQuotaIndicator;
