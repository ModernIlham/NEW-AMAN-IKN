import React, { useState, useEffect, memo } from "react";
import { Image, AlertTriangle, CheckCircle2, FileDown, X, ChevronDown, ChevronUp } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "../ui/tooltip";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Helper to get color classes based on usage percentage
function getStatusColors(usagePercent) {
  if (usagePercent >= 90) return { bar: "bg-red-500", text: "text-red-600 dark:text-red-400", bg: "bg-red-50 dark:bg-red-900/20" };
  if (usagePercent >= 70) return { bar: "bg-amber-500", text: "text-amber-600 dark:text-amber-400", bg: "bg-amber-50 dark:bg-amber-900/20" };
  return { bar: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-900/20" };
}

// ============================================================================
// COMPRESSION QUOTA INDICATOR - Shows ALL service quotas
// ============================================================================
const TinifyQuotaIndicator = memo(({ className = "" }) => {
  const [imageQuotas, setImageQuotas] = useState([]);
  const [pdfQuotas, setPdfQuotas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [dismissed, setDismissed] = useState(false);

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

  if (dismissed || loading) return null;

  // Find the active image service (first one with available quota)
  const activeImg = imageQuotas.find(q => q.available && q.limit > 0 && q.remaining > 0) || imageQuotas[0];
  const totalImgUsed = imageQuotas.filter(q => q.limit > 0).reduce((s, q) => s + q.used, 0);
  const totalImgLimit = imageQuotas.filter(q => q.limit > 0).reduce((s, q) => s + q.limit, 0);
  const imgPercent = totalImgLimit > 0 ? (totalImgUsed / totalImgLimit) * 100 : 0;
  const imgColors = getStatusColors(imgPercent);

  return (
    <TooltipProvider>
      <Tooltip delayDuration={200}>
        <TooltipTrigger asChild>
          <div 
            className={`flex items-center gap-1.5 px-2 py-1 rounded-md border cursor-help transition-all hover:shadow-sm ${imgColors.bg} border-current/10 ${className}`}
            onClick={(e) => { e.preventDefault(); setExpanded(v => !v); }}
          >
            <Image className={`w-3.5 h-3.5 ${imgColors.text}`} />
            <span className={`text-xs font-semibold ${imgColors.text}`}>
              {activeImg ? `${activeImg.remaining}` : "0"}
            </span>
            <div className="w-8 h-1.5 bg-muted rounded-full overflow-hidden">
              <div className={`h-full ${imgColors.bar} transition-all`} style={{ width: `${Math.min(imgPercent, 100)}%` }} />
            </div>
            <ChevronDown className={`w-3 h-3 text-muted-foreground transition-transform ${expanded ? 'rotate-180' : ''}`} />
            {imgPercent >= 80 && (
              <button onClick={(e) => { e.stopPropagation(); setDismissed(true); }} className="ml-0.5 p-0.5 hover:bg-white/50 rounded">
                <X className="w-3 h-3 text-muted-foreground" />
              </button>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" align="end" className="bg-slate-900 text-white p-0 max-w-[320px] shadow-xl">
          <div className="p-3 space-y-3">
            {/* Image Compression Quotas */}
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Image className="w-4 h-4 text-blue-400" />
                <span className="font-medium text-sm">Kompresi Gambar</span>
              </div>
              <div className="space-y-1.5">
                {imageQuotas.filter(q => q.available).map(q => {
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

            {/* PDF Compression Quotas */}
            {pdfQuotas.length > 0 && (
              <div>
                <div className="flex items-center gap-1.5 mb-2 pt-2 border-t border-slate-700">
                  <FileDown className="w-4 h-4 text-purple-400" />
                  <span className="font-medium text-sm">Kompresi PDF</span>
                </div>
                <div className="space-y-1.5">
                  {pdfQuotas.filter(q => q.available).map(q => {
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
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
});

TinifyQuotaIndicator.displayName = "TinifyQuotaIndicator";

// Mobile version - compact
export const TinifyQuotaMobile = memo(({ className = "" }) => {
  const [quotas, setQuotas] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API}/compression-quotas`)
      .then(r => setQuotas(r.data.quotas || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading || quotas.length === 0) return null;

  const active = quotas.find(q => q.available && q.limit > 0 && q.remaining > 0);
  if (!active) return null;

  const pct = (active.used / active.limit) * 100;
  const colors = getStatusColors(pct);

  return (
    <div className={`flex items-center gap-1 ${className}`}>
      <Image className={`w-3 h-3 ${colors.text}`} />
      <span className={`text-[10px] font-medium ${colors.text}`}>{active.remaining}/{active.limit}</span>
    </div>
  );
});

TinifyQuotaMobile.displayName = "TinifyQuotaMobile";

export default TinifyQuotaIndicator;
