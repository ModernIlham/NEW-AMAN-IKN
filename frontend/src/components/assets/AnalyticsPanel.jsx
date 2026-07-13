import React, { useState, useEffect, useCallback, useRef, memo } from "react";
import { BarChart3, ChevronUp, ChevronDown, GripHorizontal } from "lucide-react";
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend
} from "recharts";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
  "#14b8a6", "#e11d48", "#a855f7", "#0ea5e9", "#d946ef"
];

const formatRp = (v) => {
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}M`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}jt`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}rb`;
  return String(v);
};

const CustomTooltip = ({ active, payload, label, isValue }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white dark:bg-slate-900 border border-border rounded-lg shadow-lg px-3 py-2 text-xs">
      <p className="font-medium text-slate-900 dark:text-slate-100 mb-1">{label || payload[0]?.name}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || p.fill }} className="font-semibold">
          {p.dataKey === "value" || isValue ? `Rp ${Number(p.value).toLocaleString("id-ID")}` : `${p.value} aset`}
        </p>
      ))}
    </div>
  );
};

// Dark-mode aware axis tick style
const useAxisTick = () => {
  const isDark = typeof document !== 'undefined' && document.documentElement.classList.contains('dark');
  return { fontSize: 10, fill: isDark ? '#94a3b8' : '#64748b' };
};
const useCursorStyle = () => {
  const isDark = typeof document !== 'undefined' && document.documentElement.classList.contains('dark');
  return { fill: isDark ? 'rgba(148,163,184,0.15)' : 'rgba(0,0,0,0.06)' };
};

const DarkAwareBarChart = ({ data, layout, children, yWidth = 60, isValue }) => {
  const tickStyle = useAxisTick();
  const cursorStyle = useCursorStyle();
  const isVertical = layout === "vertical";
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} layout={layout} margin={{ left: isVertical ? 0 : -10, right: 8, top: 4, bottom: 4 }}>
        {isVertical ? (
          <>
            <XAxis type="number" tick={tickStyle} axisLine={false} tickLine={false} tickFormatter={isValue ? formatRp : undefined} />
            <YAxis type="category" dataKey="name" tick={tickStyle} width={yWidth} axisLine={false} tickLine={false} tickFormatter={(v) => v.length > 10 ? v.slice(0, 10) + '..' : v} />
          </>
        ) : (
          <>
            <XAxis dataKey="name" tick={tickStyle} axisLine={false} tickLine={false} tickFormatter={(v) => v.length > 8 ? v.slice(0, 8) + '..' : v} />
            <YAxis tick={tickStyle} axisLine={false} tickLine={false} tickFormatter={isValue ? formatRp : undefined} />
          </>
        )}
        <Tooltip content={<CustomTooltip isValue={isValue} />} cursor={cursorStyle} />
        {children}
      </BarChart>
    </ResponsiveContainer>
  );
};

const PieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
  if (percent < 0.05) return null;
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" className="text-[10px] font-bold">
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

const ChartCard = memo(({ title, children }) => (
  <div className="bg-card rounded-lg border border-border p-3 min-w-0">
    <h3 className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wider">{title}</h3>
    {children}
  </div>
));
ChartCard.displayName = "ChartCard";

const AnalyticsPanel = memo(({ activityId, isOpen, onToggle, panelHeight, onDragStart, embedded = false }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    const fetchAnalytics = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (activityId) params.append("activity_id", activityId);
        const r = await axios.get(`${API}/assets/analytics?${params}`);
        if (!cancelled) setData(r.data);
      } catch (err) {
        console.error("Analytics fetch error:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchAnalytics();
    return () => { cancelled = true; };
  }, [activityId, isOpen]);

  const hasData = data && (
    data.by_category?.length > 0 ||
    data.by_condition?.length > 0 ||
    data.by_status?.length > 0
  );

  const chartsContent = (
    loading && !data ? (
      <div className="flex items-center justify-center py-8">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="ml-2 text-xs text-muted-foreground">Memuat analytics...</span>
      </div>
    ) : !hasData ? (
      <div className="text-center py-6 text-muted-foreground text-xs">Tidak ada data untuk ditampilkan</div>
    ) : (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 p-1">
        {/* 1. Distribusi per Kategori - Donut */}
        {data.by_category?.length > 0 && (
          <ChartCard title="Distribusi per Kategori">
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={data.by_category.slice(0, 8)}
                  cx="50%" cy="50%"
                  innerRadius={35} outerRadius={70}
                  dataKey="count"
                  nameKey="name"
                  labelLine={false}
                  label={PieLabel}
                  stroke="none"
                >
                  {data.by_category.slice(0, 8).map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  layout="vertical" align="right" verticalAlign="middle"
                  iconSize={8} iconType="circle"
                  formatter={(v) => <span className="text-[10px] text-muted-foreground">{v.length > 12 ? v.slice(0, 12) + '...' : v}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {/* 2. Distribusi per Kondisi - Bar */}
        {data.by_condition?.length > 0 && (
          <ChartCard title="Distribusi per Kondisi">
            <DarkAwareBarChart data={data.by_condition} layout="vertical">
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {data.by_condition.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </DarkAwareBarChart>
          </ChartCard>
        )}

        {/* 3. Distribusi per Status - Bar */}
        {data.by_status?.length > 0 && (
          <ChartCard title="Distribusi per Status">
            <DarkAwareBarChart data={data.by_status} layout="vertical">
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {data.by_status.map((_, i) => (
                  <Cell key={i} fill={COLORS[(i + 3) % COLORS.length]} />
                ))}
              </Bar>
            </DarkAwareBarChart>
          </ChartCard>
        )}

        {/* 4. Top 10 Lokasi - Horizontal Bar */}
        {data.by_location?.length > 0 && (
          <ChartCard title="Top 10 Lokasi">
            <DarkAwareBarChart data={data.by_location} layout="vertical" yWidth={90}>
              <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
            </DarkAwareBarChart>
          </ChartCard>
        )}

        {/* 5. Nilai Aset per Kategori - Bar */}
        {data.by_category?.length > 0 && (
          <ChartCard title="Nilai Aset per Kategori (Rp)">
            <DarkAwareBarChart data={data.by_category.slice(0, 8)} layout="horizontal" isValue>
              <Bar dataKey="value" fill="#10b981" radius={[4, 4, 0, 0]}>
                {data.by_category.slice(0, 8).map((_, i) => (
                  <Cell key={i} fill={COLORS[(i + 5) % COLORS.length]} />
                ))}
              </Bar>
            </DarkAwareBarChart>
          </ChartCard>
        )}
      </div>
    )
  );

  // Mode embedded: header sudah jadi segmen di kontrol gabungan; render isi +
  // pegangan geser tinggi di bagian bawah kartu.
  if (embedded) {
    if (!isOpen) return null;
    return (
      <div className="print:hidden select-none mt-1.5 bg-card border border-border rounded-xl shadow-sm overflow-hidden" data-testid="analytics-panel-wrapper">
        <div className="overflow-y-auto overflow-x-hidden" style={{ height: panelHeight }} data-testid="analytics-content">
          {chartsContent}
        </div>
        <div
          className="flex items-center justify-center py-1 border-t border-border cursor-ns-resize hover:bg-muted touch-none"
          onMouseDown={onDragStart}
          onTouchStart={onDragStart}
          data-testid="analytics-drag-handle"
          title="Geser untuk mengubah tinggi"
        >
          <GripHorizontal className="w-4 h-4 text-muted-foreground" />
        </div>
      </div>
    );
  }

  return (
    <div className="print:hidden select-none" data-testid="analytics-panel-wrapper">
      {/* Toggle bar - always visible */}
      <div
        className="flex items-center justify-between bg-card border border-border rounded-xl shadow-sm px-3 py-1.5 cursor-pointer hover:bg-muted transition-colors"
        onClick={onToggle}
        data-testid="analytics-toggle"
      >
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-blue-600" />
          <span className="text-xs font-semibold text-foreground">Dashboard Analytics</span>
          {!isOpen && data && hasData && (
            <span className="text-[10px] text-muted-foreground hidden sm:inline">Klik untuk menampilkan grafik</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isOpen && (
            <div
              className="cursor-grab active:cursor-grabbing p-1 hover:bg-muted rounded touch-none"
              onMouseDown={onDragStart}
              onTouchStart={onDragStart}
              onClick={e => e.stopPropagation()}
              data-testid="analytics-drag-handle"
              title="Geser untuk mengubah ukuran"
            >
              <GripHorizontal className="w-4 h-4 text-muted-foreground" />
            </div>
          )}
          {isOpen ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
        </div>
      </div>

      {/* Expandable content */}
      {isOpen && (
        <div
          className="mt-1 overflow-y-auto overflow-x-hidden transition-all duration-200"
          style={{ height: panelHeight }}
          data-testid="analytics-content"
        >
          {chartsContent}
        </div>
      )}
    </div>
  );
});

AnalyticsPanel.displayName = "AnalyticsPanel";

export default AnalyticsPanel;
