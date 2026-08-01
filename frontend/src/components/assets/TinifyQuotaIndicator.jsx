import React, { useState, useEffect, memo } from "react";
import { Image, FileDown } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import axios from "axios";

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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [imgResp, pdfResp] = await Promise.allSettled([
          axios.get(`${API}/compression-quotas`),
          axios.get(`${API}/pdf-compression-quotas`),
        ]);
        if (imgResp.status === "fulfilled") setImageQuotas(imgResp.value.data.quotas || []);
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

  return { imageQuotas, pdfQuotas, loading };
}

// Panel rincian kuota — dipakai popover desktop DAN HP supaya informasinya
// identik dari pintu mana pun dibuka.
function PanelKuota({ imageQuotas, pdfQuotas }) {
  return (
    <div className="p-3 space-y-3">
      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <Image className="w-4 h-4 text-blue-400" />
          <span className="font-medium text-sm">Kompresi Gambar</span>
        </div>
        <div className="space-y-1.5">
          {imageQuotas.filter(q => q.available || q.used > 0).map(q => {
            const pct = q.limit > 0 ? (q.used / q.limit) * 100 : 0;
            const colors = getStatusColors(pct);
            return (
              <div key={q.service} className="flex items-center gap-2">
                <span className="text-[11px] text-slate-400 w-20 truncate">{q.name}</span>
                <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                  <div className={`h-full ${colors.bar}`} style={{ width: `${Math.min(pct, 100)}%` }} />
                </div>
                <span className="text-[11px] font-mono w-16 text-right">
                  {q.limit < 0 ? (
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
// ============================================================================
const TinifyQuotaIndicator = memo(({ className = "" }) => {
  const { imageQuotas, pdfQuotas, loading } = useKuota();
  if (loading) return null;

  const activeImg = imageQuotas.find(q => q.available && q.limit > 0 && q.remaining > 0) || imageQuotas[0];
  const totalImgUsed = imageQuotas.filter(q => q.limit > 0).reduce((s, q) => s + q.used, 0);
  const totalImgLimit = imageQuotas.filter(q => q.limit > 0).reduce((s, q) => s + q.limit, 0);
  const imgPercent = totalImgLimit > 0 ? (totalImgUsed / totalImgLimit) * 100 : 0;
  const imgColors = getStatusColors(imgPercent);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Kuota kompresi — ketuk untuk rincian"
          title="Kuota kompresi — ketuk untuk rincian"
          className={`flex items-center gap-1.5 px-2 py-1 rounded-md border cursor-pointer transition-all hover:shadow-sm min-w-0 min-h-0 ${imgColors.bg} border-current/10 ${className}`}
          data-testid="kuota-indikator"
        >
          <Image className={`w-3.5 h-3.5 ${imgColors.text}`} />
          <span className={`text-xs font-semibold tabular-nums ${imgColors.text}`}>
            {activeImg ? `${activeImg.remaining}` : "0"}
          </span>
          {/* Bar mini hanya di layar lebar — di tablet chip harus sesingkat
              mungkin agar toolbar tak pecah baris. */}
          <div className="hidden lg:block w-8 h-1.5 bg-muted rounded-full overflow-hidden">
            <div className={`h-full ${imgColors.bar} transition-all`} style={{ width: `${Math.min(imgPercent, 100)}%` }} />
          </div>
        </button>
      </PopoverTrigger>
      <PopoverContent side="bottom" align="end" className="bg-slate-900 text-white border-slate-700 p-0 w-[320px] max-w-[92vw] shadow-xl">
        <PanelKuota imageQuotas={imageQuotas} pdfQuotas={pdfQuotas} />
      </PopoverContent>
    </Popover>
  );
});

TinifyQuotaIndicator.displayName = "TinifyQuotaIndicator";

// Varian HP: angka BERTUMPUK (sisa di atas, batas di bawah) — permintaan
// pemilik: hemat ruang kiri-kanan pada baris toolbar HP yang sudah sesak.
// Tetap tombol: ketukan membuka panel rincian yang sama dengan desktop.
export const TinifyQuotaMobile = memo(({ className = "" }) => {
  const { imageQuotas, pdfQuotas, loading } = useKuota();
  if (loading || imageQuotas.length === 0) return null;

  const active = imageQuotas.find(q => q.available && q.limit > 0 && q.remaining > 0) || imageQuotas[0];
  if (!active || !(active.limit > 0)) return null;

  const pct = (active.used / active.limit) * 100;
  const colors = getStatusColors(pct);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Kuota kompresi — ketuk untuk rincian"
          className={`flex flex-col items-center justify-center leading-none px-1 rounded-md min-w-0 min-h-0 ${colors.bg} ${className}`}
          data-testid="kuota-indikator-hp"
        >
          <span className={`text-[10px] font-bold tabular-nums ${colors.text}`}>{active.remaining}</span>
          <span className="text-[8px] text-muted-foreground tabular-nums border-t border-current/20 w-full text-center">{active.limit}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent side="bottom" align="end" className="bg-slate-900 text-white border-slate-700 p-0 w-[320px] max-w-[92vw] shadow-xl">
        <PanelKuota imageQuotas={imageQuotas} pdfQuotas={pdfQuotas} />
      </PopoverContent>
    </Popover>
  );
});

TinifyQuotaMobile.displayName = "TinifyQuotaMobile";

export default TinifyQuotaIndicator;
