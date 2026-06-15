import React from "react";

const segments = [
  { key: "ditemukan", color: "emerald", label: "Ditemukan" },
  { key: "tidak_ditemukan", color: "red", label: "Tidak Ditemukan" },
  { key: "berlebih", color: "purple", label: "Berlebih" },
  { key: "sengketa", color: "rose", label: "Sengketa" },
];

export default function InventoryProgress({ data, total }) {
  if (total <= 0) return null;

  const processed = (data.ditemukan?.count || 0) + (data.tidak_ditemukan?.count || 0) +
                    (data.berlebih?.count || 0) + (data.sengketa?.count || 0);
  const pct = Math.round((processed / total) * 100);

  return (
    <div className="space-y-1" data-testid="inventory-progress">
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>Progres Inventarisasi</span>
        <span>{pct}% selesai</span>
      </div>
      <div className="h-2.5 bg-muted rounded-full overflow-hidden flex">
        {segments.map(({ key, color }) => {
          const count = data[key]?.count || 0;
          if (count <= 0) return null;
          return (
            <div key={key} className={`bg-${color}-500 h-full transition-all`}
              style={{ width: `${(count / total) * 100}%` }}
              title={`${key}: ${count}`}
            />
          );
        })}
      </div>
      <div className="flex flex-wrap gap-3 text-[10px]">
        {segments.map(({ color, label }) => (
          <span key={label} className="flex items-center gap-1">
            <span className={`w-2 h-2 bg-${color}-500 rounded-full`} />{label}
          </span>
        ))}
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 bg-muted rounded-full" />Belum
        </span>
      </div>
    </div>
  );
}
