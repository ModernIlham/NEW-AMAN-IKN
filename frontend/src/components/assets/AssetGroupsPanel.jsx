import React, { useState, useEffect, memo, useCallback } from "react";
import { ChevronDown, ChevronRight, Layers, MapPin, User, Wrench, ClipboardList, Pen, Calendar, Tag, FileText, Building2, Truck } from "lucide-react";
import { Button } from "../ui/button";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/** Convert an array of NUP strings/numbers into compact ranges like "1-5, 8-10, 15" */
function computeNupRanges(nups) {
  const nums = nups
    .map(n => parseInt(String(n), 10))
    .filter(n => !isNaN(n))
    .sort((a, b) => a - b);
  if (nums.length === 0) return nups.filter(Boolean).join(", ") || "-";
  const ranges = [];
  let start = nums[0], end = nums[0];
  for (let i = 1; i < nums.length; i++) {
    if (nums[i] === end + 1) {
      end = nums[i];
    } else {
      ranges.push(start === end ? `${start}` : `${start}-${end}`);
      start = end = nums[i];
    }
  }
  ranges.push(start === end ? `${start}` : `${start}-${end}`);
  return ranges.join(", ");
}

function extractYear(dateStr) {
  if (!dateStr) return null;
  const match = dateStr.match(/(\d{4})/);
  return match ? match[1] : null;
}

const INV_COLORS = {
  "Ditemukan": "text-emerald-600 dark:text-emerald-400",
  "Tidak Ditemukan": "text-red-600 dark:text-red-400",
  "Berlebih": "text-purple-600 dark:text-purple-400",
  "Sengketa": "text-rose-600 dark:text-rose-400",
};

const AssetGroupsPanel = memo(({ activityId, isOpen, onToggle, onBatchEdit, embedded = false, onCount }) => {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedGroup, setExpandedGroup] = useState(null);

  useEffect(() => {
    if (!activityId || !isOpen) return;
    setLoading(true);
    axios.get(`${API}/assets/groups`, { params: { activity_id: activityId } })
      .then(res => { const g = res.data.groups || []; setGroups(g); onCount?.(g.length); })
      .catch(() => setGroups([]))
      .finally(() => setLoading(false));
  }, [activityId, isOpen, onCount]);

  const formatPrice = (price) => {
    if (!price) return '-';
    const num = typeof price === 'number' ? price : parseFloat(price);
    return isNaN(num) ? '-' : `Rp ${num.toLocaleString('id-ID')}`;
  };

  const handleBatchEditGroup = useCallback((group) => {
    if (onBatchEdit && group.asset_ids) {
      onBatchEdit(group.asset_ids);
    }
  }, [onBatchEdit]);

  const list = (
        <div className="max-h-[400px] overflow-y-auto">
          {loading ? (
            <div className="p-4 text-center text-sm text-muted-foreground">Memuat data grup...</div>
          ) : groups.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">Tidak ada barang serupa ditemukan</div>
          ) : (
            <div className="divide-y divide-border">
              {groups.map((group, idx) => {
                const nupRange = computeNupRanges(group.NUPs || []);
                return (
                  <div key={idx} className="hover:bg-muted/50">
                    <button
                      onClick={() => setExpandedGroup(expandedGroup === idx ? null : idx)}
                      className="w-full text-left px-2 sm:px-4 py-2 flex items-center gap-2 sm:gap-3"
                      data-testid={`group-row-${idx}`}
                    >
                      <div className="w-7 h-7 sm:w-8 sm:h-8 bg-violet-100 dark:bg-violet-900/40 rounded-lg flex items-center justify-center flex-shrink-0">
                        <span className="text-xs sm:text-sm font-bold text-violet-700 dark:text-violet-300">{group.count}</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs sm:text-sm font-medium text-foreground truncate">{group.asset_name || group.asset_code}</div>
                        <div className="text-[10px] sm:text-[11px] text-muted-foreground truncate">
                          {group.asset_code} {group.brand || group.model ? `- ${[group.brand, group.model].filter(Boolean).join(' / ')}` : ''} {group.purchase_price ? `- ${formatPrice(group.purchase_price)}` : ''}
                        </div>
                      </div>
                      <span className="text-[9px] sm:text-[10px] bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300 px-1.5 sm:px-2 py-0.5 rounded-full font-mono font-medium flex-shrink-0 max-w-[80px] sm:max-w-[120px] truncate" title={`NUP: ${nupRange}`}>
                        NUP {nupRange}
                      </span>
                      {expandedGroup === idx ? <ChevronDown className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-muted-foreground flex-shrink-0" /> : <ChevronRight className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-muted-foreground flex-shrink-0" />}
                    </button>

                    {/* Expanded detail view */}
                    {expandedGroup === idx && (
                      <div className="px-2 sm:px-4 pb-3 pl-4 sm:pl-14 space-y-2">
                        {/* Member details */}
                        <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
                          {(group.members || []).map((m, mi) => {
                            const year = extractYear(m.purchase_date);
                            const perolehan = m.perolehan_dari_nama || m.supplier;
                            return (
                              <div key={mi} className="bg-muted/50 rounded-md p-2 text-[11px] border border-border/50" data-testid={`member-detail-${idx}-${mi}`}>
                                <div className="flex items-center gap-2 mb-1 flex-wrap">
                                  <span className="font-bold text-violet-700 dark:text-violet-300">NUP {m.NUP || '-'}</span>
                                  {m.inventory_status && (
                                    <span className={`text-[9px] font-semibold ${INV_COLORS[m.inventory_status] || 'text-muted-foreground'}`}>
                                      <ClipboardList className="w-2.5 h-2.5 inline mr-0.5" />
                                      {m.inventory_status}
                                    </span>
                                  )}
                                  {m.condition && (
                                    <span className="text-[9px] text-muted-foreground">
                                      <Wrench className="w-2.5 h-2.5 inline mr-0.5" />
                                      {m.condition}
                                    </span>
                                  )}
                                  {year && (
                                    <span className="text-[9px] text-blue-600 dark:text-blue-400">
                                      <Calendar className="w-2.5 h-2.5 inline mr-0.5" />
                                      {year}
                                    </span>
                                  )}
                                </div>
                                {/* Row 2: Key identifiers */}
                                <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-muted-foreground">
                                  {m.nomor_spm && <span>SPM: {m.nomor_spm}</span>}
                                  {m.kode_register && (
                                    <span className="break-all" data-testid={`member-kode-register-${idx}-${mi}`}>
                                      Reg: {m.kode_register}
                                    </span>
                                  )}
                                  {m.serial_number && <span>SN: {m.serial_number}</span>}
                                </div>
                                {/* Row 3: Location, user, category, perolehan */}
                                <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-muted-foreground mt-0.5">
                                  {m.location && (
                                    <span className="inline-flex items-center gap-0.5">
                                      <MapPin className="w-2.5 h-2.5 flex-shrink-0" />{m.location}
                                    </span>
                                  )}
                                  {m.user && (
                                    <span className="inline-flex items-center gap-0.5">
                                      <User className="w-2.5 h-2.5 flex-shrink-0" />{m.user}
                                    </span>
                                  )}
                                  {m.category && (
                                    <span className="inline-flex items-center gap-0.5">
                                      <Tag className="w-2.5 h-2.5 flex-shrink-0" />{m.category}
                                    </span>
                                  )}
                                  {perolehan && (
                                    <span className="inline-flex items-center gap-0.5">
                                      <Truck className="w-2.5 h-2.5 flex-shrink-0" />{perolehan}
                                    </span>
                                  )}
                                  {(m.eselon1 || m.eselon2) && (
                                    <span className="inline-flex items-center gap-0.5">
                                      <Building2 className="w-2.5 h-2.5 flex-shrink-0" />
                                      {[m.eselon1, m.eselon2].filter(Boolean).join(' / ')}
                                    </span>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>

                        {/* Batch edit button */}
                        {onBatchEdit && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="w-full h-7 text-xs border-violet-300 text-violet-700 dark:text-violet-300 hover:bg-violet-50 dark:hover:bg-violet-900/30 hover:text-violet-800 dark:hover:text-violet-200"
                            onClick={() => handleBatchEditGroup(group)}
                            data-testid={`group-batch-edit-${idx}`}
                          >
                            <Pen className="w-3 h-3 mr-1" />
                            Ubah Massal ({group.count} item)
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
  );

  // Mode embedded: hanya render isi (header sudah jadi segmen di kontrol gabungan).
  if (embedded) {
    if (!isOpen) return null;
    return (
      <div className="mt-1.5 bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="asset-groups-panel">
        {list}
      </div>
    );
  }

  return (
    <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="asset-groups-panel">
      <button
        onClick={onToggle}
        className="min-h-0 min-w-0 w-full flex items-center justify-between px-3 py-2 bg-gradient-to-r from-violet-50 to-purple-50 hover:from-violet-100 hover:to-purple-100 dark:from-violet-900/30 dark:to-purple-900/30 dark:hover:from-violet-900/50 dark:hover:to-purple-900/50 transition-colors"
        data-testid="asset-groups-toggle"
      >
        <div className="flex items-center gap-2 min-w-0">
          <Layers className="w-4 h-4 text-violet-600 flex-shrink-0" />
          <span className="text-sm font-semibold text-violet-800 dark:text-violet-300">Barang Serupa</span>
          {groups.length > 0 && (
            <span className="text-[10px] bg-violet-200 dark:bg-violet-800/50 text-violet-700 dark:text-violet-300 px-1.5 py-0.5 rounded-full font-medium">{groups.length} grup</span>
          )}
        </div>
        {isOpen ? <ChevronDown className="w-4 h-4 text-violet-500 dark:text-violet-400 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 text-violet-500 dark:text-violet-400 flex-shrink-0" />}
      </button>
      {isOpen && list}
    </div>
  );
});

AssetGroupsPanel.displayName = "AssetGroupsPanel";
export default AssetGroupsPanel;
