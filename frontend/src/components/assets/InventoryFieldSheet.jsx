import React, { useState } from "react";
import {
  Check, Camera, Images, MapPin, LocateFixed, RefreshCw, Loader2, Copy,
  ChevronDown, ArrowRight, ScanLine,
} from "lucide-react";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../ui/select";

// ============================================================================
// InventoryFieldSheet — tampilan EKSKLUSIF mode inventarisasi lapangan.
// Komponen ini murni presentasional: seluruh state, validasi, dan logika
// simpan tetap berada di AssetForm dan diakses lewat props/handler.
// Dirender di dalam <form onSubmit={handleSubmit}> milik AssetForm sehingga
// tombol type="submit" memakai jalur simpan yang sama persis dengan form penuh.
// ============================================================================

export const STATUS_OPTIONS = [
  { value: "Ditemukan", selected: "bg-emerald-600 border-emerald-600 text-white" },
  { value: "Tidak Ditemukan", selected: "bg-red-600 border-red-600 text-white" },
  { value: "Berlebih", selected: "bg-purple-600 border-purple-600 text-white" },
  { value: "Sengketa", selected: "bg-rose-600 border-rose-600 text-white" },
];

export const CONDITION_OPTIONS = [
  { value: "Baik", selected: "bg-emerald-600 border-emerald-600 text-white" },
  { value: "Rusak Ringan", selected: "bg-amber-500 border-amber-500 text-white" },
  { value: "Rusak Berat", selected: "bg-red-600 border-red-600 text-white" },
];

// Pengguna "melekat ke" — nilai HARUS sama dengan form penuh (AssetForm) dan
// backend (pengguna_melekat_ke). Label input nama menyesuaikan pilihan.
export const PENGGUNA_MELEKAT_OPTIONS = ["Individual", "Jabatan", "Operasional"];
export const PENGGUNA_NAME_LABELS = {
  Individual: "Nama Pengguna",
  Jabatan: "Nama Pejabat",
  Operasional: "Nama Penanggung Jawab",
};
// Sub-opsi bila melekat ke Operasional — nilai HARUS sama dengan backend
// (operasional_jenis). "Ruangan" = barang harus tetap berada di ruang tsb.
export const OPERASIONAL_JENIS_OPTIONS = ["Kegiatan/Acara/Kebutuhan", "Ruangan"];

// Nilai HARUS sama persis dengan opsi Select pada form penuh (AssetForm).
export const SUB_KLASIFIKASI_OPTIONS = {
  "Kesalahan Pencatatan": [
    { value: "Kesalahan Kodefikasi", label: "Kesalahan Kodefikasi" },
    { value: "Pencatatan Ganda", label: "Pencatatan Ganda" },
    { value: "BMN Tercatat di Satker Lain", label: "BMN Tercatat di Satker Lain" },
    { value: "Kegiatan Perencanaan/Pengembangan Dicatat Sebagai BMN Tersendiri", label: "Perencanaan/Pengembangan Dicatat Sebagai BMN" },
    { value: "BMN Objek Alih Status/Pemindahtanganan/Penghapusan", label: "Objek Alih Status/Pemindahtanganan/Penghapusan" },
    { value: "Penggabungan BMN Satu Kesatuan Fungsi", label: "Penggabungan BMN Satu Kesatuan Fungsi" },
    { value: "Kesalahan Pencatatan Pihak Ketiga", label: "Kesalahan Pencatatan Pihak Ketiga" },
  ],
  "Tidak Ditemukan Lainnya": [
    { value: "Tidak Ditemukan Fisiknya", label: "Tidak Ditemukan Fisiknya" },
    { value: "Tidak Dapat Ditelusuri", label: "Tidak Dapat Ditelusuri" },
    { value: "Tertimpa Bangunan Lain/Beralih Fungsi", label: "Tertimpa Bangunan Lain/Beralih Fungsi" },
  ],
};

const SEG_BASE = "h-11 rounded-lg border text-xs font-semibold leading-tight transition-colors flex items-center justify-center gap-1 px-1 text-center";
const SEG_IDLE = "bg-background border-border text-foreground/80 hover:bg-accent";

const SegButton = ({ selected, selectedClass, onClick, children, testId }) => (
  <button
    type="button"
    aria-pressed={selected}
    onClick={onClick}
    data-testid={testId}
    className={`${SEG_BASE} ${selected ? selectedClass : SEG_IDLE}`}
  >
    {selected && <Check className="w-3.5 h-3.5 flex-shrink-0" />}
    <span>{children}</span>
  </button>
);

const CardHeader = ({ badge, title, hint, badgeClass = "bg-blue-600/10 text-blue-600" }) => (
  <div className="flex items-center gap-2 mb-2.5">
    <span className={`w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center flex-shrink-0 ${badgeClass}`}>
      {badge}
    </span>
    <span className="uppercase tracking-wide text-[11px] font-semibold text-muted-foreground flex-1 truncate">
      {title}
    </span>
    {hint}
  </div>
);

const Card = ({ children, accent = false, className = "", testId }) => (
  <section
    data-testid={testId}
    className={`rounded-xl bg-card border border-border shadow-sm p-3 ${accent ? "border-l-2 border-l-amber-500" : ""} ${className}`}
  >
    {children}
  </section>
);

const InventoryFieldSheet = ({
  formData,
  photoItems,
  photoCount,
  isSubmitting,
  gpsLoading,
  lastCtx,
  assetIndex = -1,
  totalAssetsInView = 0,
  canSaveNext = false,
  onInputChange,
  onInventoryStatusChange,
  onConditionChange,
  onKlasifikasiChange,
  onSubKlasifikasiChange,
  onStikerStatusChange,
  onStikerUkuranChange,
  onPenggunaMelekatChange,
  onOperasionalJenisChange,
  onOpenCamera,
  onOpenFullCamera,
  onOpenFullCameraScan,
  onOpenGallery,
  onFetchGPS,
  onApplyLastCtx,
  onQueueNextIntent,
  onShowFullForm,
}) => {
  const [notesOpen, setNotesOpen] = useState(false);

  const hasGps = !!(formData.koordinat_latitude && formData.koordinat_longitude);
  const status = formData.inventory_status;
  const subOptions = SUB_KLASIFIKASI_OPTIONS[formData.klasifikasi_tidak_ditemukan] || [];

  const detailCardClass = "space-y-2 animate-in fade-in slide-in-from-top-2 duration-200";

  return (
    <div className="flex-1 flex flex-col overflow-hidden" data-testid="inventory-field-sheet">
      {/* Area gulir */}
      <div className="flex-1 overflow-y-auto">
        {/* 1. Header identitas aset (read-only, sticky) */}
        <div className="sticky top-0 z-10 bg-background/95 backdrop-blur border-b border-border px-3 py-2 flex items-center gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="font-mono font-bold text-sm truncate">{formData.asset_code || "—"}</span>
              {formData.NUP && (
                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground flex-shrink-0">
                  NUP {formData.NUP}
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground truncate">{formData.asset_name || "—"}</p>
          </div>
          {assetIndex >= 0 && totalAssetsInView > 0 && (
            <span className="flex-shrink-0 rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] font-semibold text-muted-foreground tabular-nums">
              {assetIndex + 1}/{totalAssetsInView}
            </span>
          )}
        </div>

        <div className="p-3 space-y-3">
          {/* Card 1 — Status Inventarisasi */}
          <Card testId="sheet-card-status">
            <CardHeader badge="1" title="Status Inventarisasi" />
            <div className="grid grid-cols-2 gap-1.5">
              {STATUS_OPTIONS.map(o => (
                <SegButton
                  key={o.value}
                  selected={status === o.value}
                  selectedClass={o.selected}
                  onClick={() => onInventoryStatusChange(o.value)}
                  testId={`sheet-status-${o.value}`}
                >
                  {o.value}
                </SegButton>
              ))}
            </div>
          </Card>

          {/* Card 2 — Kondisi Fisik */}
          <Card testId="sheet-card-condition">
            <CardHeader badge="2" title="Kondisi Fisik" />
            <div className="grid grid-cols-3 gap-1.5">
              {CONDITION_OPTIONS.map(o => (
                <SegButton
                  key={o.value}
                  selected={formData.condition === o.value}
                  selectedClass={o.selected}
                  onClick={() => onConditionChange(o.value)}
                  testId={`sheet-condition-${o.value}`}
                >
                  {o.value}
                </SegButton>
              ))}
            </div>
          </Card>

          {/* Card kondisional — detail wajib sesuai status terpilih */}
          {status === "Tidak Ditemukan" && (
            <Card accent testId="sheet-detail-tidak-ditemukan" className={detailCardClass}>
              <CardHeader
                badge="!"
                badgeClass="bg-amber-500/10 text-amber-600"
                title="Detail Tidak Ditemukan"
                hint={<span className="text-[10px] font-medium text-amber-600 flex-shrink-0">Wajib dilengkapi</span>}
              />
              <div className="space-y-1">
                <Label className="text-xs">Klasifikasi</Label>
                <Select value={formData.klasifikasi_tidak_ditemukan || ""} onValueChange={onKlasifikasiChange}>
                  <SelectTrigger className="h-9 text-xs"><SelectValue placeholder="Pilih klasifikasi" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Kesalahan Pencatatan">Kesalahan Pencatatan</SelectItem>
                    <SelectItem value="Tidak Ditemukan Lainnya">Tidak Ditemukan Lainnya</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {formData.klasifikasi_tidak_ditemukan && (
                <div className="space-y-1">
                  <Label className="text-xs">Sub Klasifikasi</Label>
                  <Select value={formData.sub_klasifikasi || ""} onValueChange={onSubKlasifikasiChange}>
                    <SelectTrigger className="h-9 text-xs"><SelectValue placeholder="Pilih sub-kategori" /></SelectTrigger>
                    <SelectContent>
                      {subOptions.map(o => (
                        <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              <div className="space-y-1">
                <Label className="text-xs">Uraian Tidak Ditemukan</Label>
                <Textarea
                  name="uraian_tidak_ditemukan"
                  value={formData.uraian_tidak_ditemukan || ""}
                  onChange={onInputChange}
                  placeholder="Jelaskan detail mengapa BMN tidak ditemukan..."
                  className="min-h-[56px] text-xs resize-none"
                />
              </div>
            </Card>
          )}

          {status === "Berlebih" && (
            <Card accent testId="sheet-detail-berlebih" className={detailCardClass}>
              <CardHeader
                badge="!"
                badgeClass="bg-amber-500/10 text-amber-600"
                title="Detail Berlebih"
                hint={<span className="text-[10px] font-medium text-amber-600 flex-shrink-0">Wajib dilengkapi</span>}
              />
              <div className="space-y-1">
                <Label className="text-xs">Asal Usul BMN Berlebih</Label>
                <Textarea
                  name="asal_usul_berlebih"
                  value={formData.asal_usul_berlebih || ""}
                  onChange={onInputChange}
                  placeholder="Asal usul perolehan BMN (hibah, transfer satker lain, dll)..."
                  className="min-h-[56px] text-xs resize-none"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Keterangan Berlebih</Label>
                <Textarea
                  name="keterangan_berlebih"
                  value={formData.keterangan_berlebih || ""}
                  onChange={onInputChange}
                  placeholder="Jelaskan mengapa BMN dikategorikan berlebih..."
                  className="min-h-[56px] text-xs resize-none"
                />
              </div>
            </Card>
          )}

          {status === "Sengketa" && (
            <Card accent testId="sheet-detail-sengketa" className={detailCardClass}>
              <CardHeader
                badge="!"
                badgeClass="bg-amber-500/10 text-amber-600"
                title="Detail Sengketa"
                hint={<span className="text-[10px] font-medium text-amber-600 flex-shrink-0">Wajib dilengkapi</span>}
              />
              <div className="space-y-1">
                <Label className="text-xs">Nomor Perkara</Label>
                <Input
                  name="nomor_perkara"
                  value={formData.nomor_perkara || ""}
                  onChange={onInputChange}
                  placeholder="Nomor perkara pengadilan..."
                  className="h-9 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Pihak Bersengketa</Label>
                <Input
                  name="pihak_bersengketa"
                  value={formData.pihak_bersengketa || ""}
                  onChange={onInputChange}
                  placeholder="Nama pihak yang bersengketa..."
                  className="h-9 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Keterangan Sengketa</Label>
                <Textarea
                  name="keterangan_sengketa"
                  value={formData.keterangan_sengketa || ""}
                  onChange={onInputChange}
                  placeholder="Jelaskan detail sengketa BMN..."
                  className="min-h-[56px] text-xs resize-none"
                />
              </div>
            </Card>
          )}

          {formData.condition === "Rusak Berat" && (
            <Card accent testId="sheet-detail-rusak-berat" className={detailCardClass}>
              <CardHeader
                badge="!"
                badgeClass="bg-amber-500/10 text-amber-600"
                title="Tindak Lanjut Rusak Berat"
                hint={<span className="text-[10px] font-medium text-amber-600 flex-shrink-0">Wajib dilengkapi</span>}
              />
              <div className="space-y-1">
                <Label className="text-xs">Tindak Lanjut</Label>
                <Textarea
                  name="tindak_lanjut"
                  value={formData.tindak_lanjut || ""}
                  onChange={onInputChange}
                  placeholder="Tindak lanjut yang sudah/akan dilakukan..."
                  className="min-h-[56px] text-xs resize-none"
                />
              </div>
            </Card>
          )}

          {/* Card 3 — Foto */}
          <Card testId="sheet-card-foto">
            <CardHeader
              badge="3"
              title="Foto"
              hint={
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold flex-shrink-0 ${photoCount > 0 ? "bg-blue-600/10 text-blue-600" : "bg-muted text-muted-foreground"}`}>
                  {photoCount}/6
                </span>
              }
            />
            {photoItems.length > 0 && (
              <div className="flex gap-1.5 overflow-x-auto pb-2 mb-1">
                {photoItems.map((item, i) => (
                  <img
                    key={i}
                    src={item.thumbnail}
                    alt={`Foto ${i + 1}`}
                    loading="lazy"
                    className="w-14 h-14 flex-shrink-0 object-cover rounded-lg border border-border bg-muted"
                    data-testid={`sheet-photo-thumb-${i}`}
                  />
                ))}
              </div>
            )}
            {onOpenFullCamera && (
              <button
                type="button"
                onClick={onOpenFullCamera}
                disabled={photoCount >= 6}
                data-testid="sheet-full-camera-btn"
                className="w-full h-11 mb-2 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50 disabled:pointer-events-none"
              >
                <Camera className="w-4 h-4" />Mode Kamera Penuh (Jam + GPS Live)
              </button>
            )}
            {onOpenFullCameraScan && typeof window !== "undefined" && "BarcodeDetector" in window && (
              <button
                type="button"
                onClick={onOpenFullCameraScan}
                data-testid="sheet-full-camera-scan-btn"
                className="w-full h-11 mb-2 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
              >
                <ScanLine className="w-4 h-4" />Kamera + Scan QR (edit cepat antar-aset)
              </button>
            )}
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={onOpenCamera}
                disabled={photoCount >= 6}
                data-testid="sheet-camera-btn"
                className="h-11 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50 disabled:pointer-events-none"
              >
                <Camera className="w-4 h-4" />Kamera
              </button>
              <button
                type="button"
                onClick={onOpenGallery}
                disabled={photoCount >= 6}
                data-testid="sheet-gallery-btn"
                className="h-11 rounded-lg border border-border bg-background text-foreground/80 hover:bg-accent text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50 disabled:pointer-events-none"
              >
                <Images className="w-4 h-4" />Galeri
              </button>
            </div>
          </Card>

          {/* Card 4 — Lokasi & Pengguna */}
          <Card testId="sheet-card-lokasi">
            <CardHeader badge="4" title="Lokasi & Pengguna" />
            <div className="space-y-2">
              <div className="space-y-1">
                <Label className="text-xs">Lokasi</Label>
                <Input name="location" value={formData.location || ""} onChange={onInputChange} className="h-9 text-xs" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Pengguna Melekat ke</Label>
                <div className="grid grid-cols-3 gap-1.5">
                  {PENGGUNA_MELEKAT_OPTIONS.map(o => (
                    <SegButton
                      key={o}
                      selected={formData.pengguna_melekat_ke === o}
                      selectedClass="bg-blue-600 border-blue-600 text-white"
                      onClick={() => onPenggunaMelekatChange(o)}
                      testId={`sheet-melekat-${o}`}
                    >
                      {o}
                    </SegButton>
                  ))}
                </div>
              </div>
              {formData.pengguna_melekat_ke === "Operasional" && (
                <div className="space-y-1">
                  <Label className="text-xs">Jenis Operasional</Label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {OPERASIONAL_JENIS_OPTIONS.map(o => (
                      <SegButton
                        key={o}
                        selected={formData.operasional_jenis === o}
                        selectedClass="bg-blue-600 border-blue-600 text-white"
                        onClick={() => onOperasionalJenisChange(o)}
                        testId={`sheet-operasional-${o}`}
                      >
                        {o}
                      </SegButton>
                    ))}
                  </div>
                  <p className="text-[10px] text-muted-foreground italic">Ruangan = barang harus tetap berada di ruang tersebut.</p>
                </div>
              )}
              <div className="space-y-1">
                <Label className="text-xs">{PENGGUNA_NAME_LABELS[formData.pengguna_melekat_ke] || "Pengguna"}</Label>
                <Input name="user" value={formData.user || ""} onChange={onInputChange} className="h-9 text-xs" data-testid="sheet-pengguna-input" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">NIP/NIK Pegawai</Label>
                <Input name="pengguna_nip" value={formData.pengguna_nip || ""} onChange={onInputChange} placeholder="NIP/NIK pegawai pengguna" className="h-9 text-xs" data-testid="sheet-pengguna-nip" />
              </div>
              {hasGps ? (
                <div className="flex items-center gap-1.5 min-w-0">
                  <MapPin className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                  <span className="text-[11px] font-mono text-muted-foreground truncate flex-1">
                    GPS: {formData.koordinat_latitude}, {formData.koordinat_longitude}
                  </span>
                  <button
                    type="button"
                    onClick={onFetchGPS}
                    disabled={gpsLoading}
                    aria-label="Perbarui koordinat GPS"
                    data-testid="sheet-gps-refresh-btn"
                    className="h-7 w-7 rounded-md flex items-center justify-center flex-shrink-0 text-muted-foreground hover:text-blue-600 hover:bg-accent transition-colors"
                  >
                    {gpsLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={onFetchGPS}
                  disabled={gpsLoading}
                  data-testid="sheet-gps-btn"
                  className="flex items-center gap-1.5 text-[11px] font-medium text-blue-600 hover:text-blue-700 transition-colors"
                >
                  {gpsLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <LocateFixed className="w-3.5 h-3.5" />}
                  {gpsLoading ? "Mencari lokasi..." : "Ambil GPS"}
                </button>
              )}
              {lastCtx && (
                <button
                  type="button"
                  onClick={onApplyLastCtx}
                  data-testid="copy-last-ctx-btn"
                  className="inline-flex items-center gap-1.5 rounded-full px-2.5 h-8 text-[11px] font-medium text-blue-600 hover:bg-blue-600/10 transition-colors"
                >
                  <Copy className="w-3.5 h-3.5" />Salin dari aset sebelumnya
                </button>
              )}
            </div>
          </Card>

          {/* Card 5 — Stiker */}
          <Card testId="sheet-card-stiker">
            <CardHeader badge="5" title="Stiker" />
            <div className="grid grid-cols-2 gap-1.5">
              <SegButton
                selected={formData.stiker_status === "Sudah Terpasang"}
                selectedClass="bg-blue-600 border-blue-600 text-white"
                onClick={() => onStikerStatusChange("Sudah Terpasang")}
                testId="sheet-stiker-sudah"
              >
                Sudah Terpasang
              </SegButton>
              <SegButton
                selected={formData.stiker_status === "Belum Terpasang"}
                selectedClass="bg-blue-600 border-blue-600 text-white"
                onClick={() => onStikerStatusChange("Belum Terpasang")}
                testId="sheet-stiker-belum"
              >
                Belum
              </SegButton>
            </div>
            {formData.stiker_status === "Sudah Terpasang" && (
              <div className="mt-2 space-y-1 animate-in fade-in slide-in-from-top-1 duration-200">
                <Label className="text-xs">Ukuran Stiker</Label>
                <Select value={formData.stiker_ukuran || ""} onValueChange={onStikerUkuranChange}>
                  <SelectTrigger className="h-9 text-xs"><SelectValue placeholder="Pilih ukuran" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Kecil">Kecil (3x1.5cm)</SelectItem>
                    <SelectItem value="Sedang">Sedang (5x3cm)</SelectItem>
                    <SelectItem value="Besar">Besar (8x5cm)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
          </Card>

          {/* Card 6 — Catatan (tertutup secara default) */}
          <section className="rounded-xl bg-card border border-border shadow-sm" data-testid="sheet-card-catatan">
            <button
              type="button"
              onClick={() => setNotesOpen(o => !o)}
              aria-expanded={notesOpen}
              data-testid="sheet-notes-toggle"
              className="w-full flex items-center gap-2 p-3 text-left"
            >
              <span className="w-6 h-6 rounded-full bg-blue-600/10 text-blue-600 text-xs font-bold flex items-center justify-center flex-shrink-0">6</span>
              <span className="uppercase tracking-wide text-[11px] font-semibold text-muted-foreground flex-1 truncate">Catatan</span>
              {!notesOpen && formData.notes && <span className="w-1.5 h-1.5 rounded-full bg-blue-600 flex-shrink-0" aria-hidden="true" />}
              <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform flex-shrink-0 ${notesOpen ? "rotate-180" : ""}`} />
            </button>
            {notesOpen && (
              <div className="px-3 pb-3 animate-in fade-in slide-in-from-top-1 duration-200">
                <Textarea
                  name="notes"
                  value={formData.notes || ""}
                  onChange={onInputChange}
                  placeholder="Catatan tambahan..."
                  className="min-h-[64px] text-xs resize-none"
                />
              </div>
            )}
          </section>
        </div>
      </div>

      {/* Footer sticky — jalur submit sama persis dengan form penuh */}
      <div className="flex-shrink-0 border-t border-border bg-background/95 backdrop-blur p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] space-y-2">
        <button
          type="submit"
          onClick={onQueueNextIntent}
          disabled={isSubmitting}
          data-testid="sheet-submit-next"
          className="w-full h-12 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm flex items-center justify-center gap-2 transition-colors disabled:opacity-60 disabled:pointer-events-none"
        >
          {isSubmitting ? (
            <><Loader2 className="w-4 h-4 animate-spin" />Menyimpan...</>
          ) : canSaveNext ? (
            <>Simpan &amp; Lanjut<ArrowRight className="w-4 h-4" /></>
          ) : (
            <>Simpan</>
          )}
        </button>
        <div className="grid grid-cols-2 gap-2">
          {canSaveNext && (
            <button
              type="submit"
              disabled={isSubmitting}
              data-testid="sheet-submit"
              className="h-9 rounded-lg border border-border bg-background text-foreground/80 hover:bg-accent text-xs font-semibold transition-colors disabled:opacity-50 disabled:pointer-events-none"
            >
              Simpan
            </button>
          )}
          <button
            type="button"
            onClick={onShowFullForm}
            disabled={isSubmitting}
            data-testid="sheet-full-form-btn"
            className={`h-9 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors disabled:opacity-50 disabled:pointer-events-none ${canSaveNext ? "" : "col-span-2"}`}
          >
            Form Lengkap
          </button>
        </div>
      </div>
    </div>
  );
};

export default InventoryFieldSheet;
