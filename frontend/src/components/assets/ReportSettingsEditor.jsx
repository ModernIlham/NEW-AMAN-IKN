import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Settings, Upload, Trash2, Save, Image as ImageIcon, Loader2
} from "lucide-react";

const API = (process.env.REACT_APP_BACKEND_URL || "http://localhost:8001") + "/api";

export default function ReportSettingsEditor({ onClose }) {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    axios.get(`${API}/report-settings`).then(r => {
      setSettings(r.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const { logo_url, type, ...textFields } = settings;
      const r = await axios.put(`${API}/report-settings`, textFields);
      setSettings(prev => ({ ...prev, ...r.data }));
      toast.success("Pengaturan berhasil disimpan");
    } catch {
      toast.error("Gagal menyimpan pengaturan");
    } finally { setSaving(false); }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) { toast.error("File harus berupa gambar"); return; }
    if (file.size > 5 * 1024 * 1024) { toast.error("Ukuran file maksimal 5MB"); return; }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const r = await axios.post(`${API}/report-settings/logo`, formData);
      setSettings(prev => ({ ...prev, logo_url: r.data.logo_url }));
      toast.success("Logo berhasil diupload");
    } catch {
      toast.error("Gagal upload logo");
    } finally { setUploading(false); }
  };

  const handleDeleteLogo = async () => {
    if (!window.confirm("Hapus logo instansi dari seluruh kop laporan?")) return;
    try {
      await axios.delete(`${API}/report-settings/logo`);
      setSettings(prev => ({ ...prev, logo_url: "" }));
      toast.success("Logo berhasil dihapus");
    } catch { toast.error("Gagal menghapus logo"); }
  };

  const handleChange = (field, value) => {
    setSettings(prev => ({ ...prev, [field]: value }));
  };

  if (loading) return <div className="p-4 text-center text-xs text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin mx-auto" /></div>;

  const fields = [
    { key: "nama_instansi", label: "Nama Instansi (baris 1 kop)", placeholder: "Contoh: OTORITA IBU KOTA NUSANTARA REPUBLIK INDONESIA" },
    { key: "nama_unit_organisasi", label: "Unit Organisasi (baris 2, tebal)", placeholder: "Contoh: KUASA PENGGUNA BARANG" },
    { key: "nama_sub_unit", label: "Sub Unit/Satker (baris 3, tebal)", placeholder: "Contoh: SATUAN KERJA D (PP-THD)" },
    { key: "kode_satker_lengkap", label: "Kode Satker Lengkap (±20 digit — dipakai stiker label)", placeholder: "Contoh: 126011600691778000KP" },
    { key: "alamat_instansi", label: "Alamat Instansi (boleh beberapa baris — tekan Enter)", placeholder: "Gedung Kantor Otorita IKN, Nusantara, Kalimantan\nPerwakilan I: Menara Mandiri II Lantai 5, Jakarta", multiline: true },
    { key: "judul_laporan", label: "Judul Laporan", placeholder: "LAPORAN HASIL INVENTARISASI" },
    { key: "subjudul_laporan", label: "Sub Judul", placeholder: "BARANG MILIK NEGARA (BMN)" },
    { key: "tahun_anggaran", label: "Tahun Anggaran", placeholder: "2025" },
    { key: "tempat_laporan", label: "Tempat Laporan (kota penandatanganan)", placeholder: "Contoh: Nusantara" },
    { key: "tanggal_laporan", label: "Tanggal Laporan (baris ttd surat & sampul)", type: "date" },
    { key: "catatan_kaki", label: "Catatan Kaki", placeholder: "Teks tambahan di bagian bawah sampul" },
    { key: "tembusan_laporan", label: "Tembusan surat/BA (satu per baris — kosongkan bila tidak dipakai)", placeholder: "Kepala Biro Umum\nInspektur\nKepala KPKNL Balikpapan", multiline: true },
  ];

  return (
    <div className="bg-muted border border-border rounded-lg p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
          <Settings className="w-3.5 h-3.5" /> Pengaturan Sampul LHI
        </h4>
        <button onClick={onClose} data-testid="report-settings-close" className="text-[10px] text-muted-foreground hover:text-foreground px-2 py-0.5 rounded hover:bg-muted min-w-0 min-h-0">Tutup</button>
      </div>
      <p className="text-[10px] text-muted-foreground -mt-1.5">
        Berlaku <b>global</b> untuk semua laporan & semua kegiatan (kop, logo, penanda tangan, tembusan) — bukan hanya kegiatan ini.
      </p>

      {/* Logo Section */}
      <div className="bg-card rounded-lg border border-border p-2.5 space-y-2">
        <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Logo Instansi</p>
        <div className="flex items-center gap-3">
          {settings?.logo_url ? (
            <div className="relative">
              <img src={settings.logo_url} alt="Logo" className="w-14 h-14 object-contain rounded border border-border bg-card p-1" />
              <button onClick={handleDeleteLogo} className="absolute -top-1 -right-1 w-4 h-4 min-w-0 min-h-0 bg-red-500 text-white rounded-full flex items-center justify-center hover:bg-red-600" data-testid="delete-logo-btn">
                <Trash2 className="w-2.5 h-2.5" />
              </button>
            </div>
          ) : (
            <div className="w-14 h-14 rounded border-2 border-dashed border-border flex items-center justify-center bg-muted">
              <ImageIcon className="w-5 h-5 text-muted-foreground" />
            </div>
          )}
          <div>
            <input type="file" ref={fileInputRef} onChange={handleLogoUpload} accept="image/*" className="hidden" />
            <button
              data-testid="upload-logo-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 border border-blue-200 text-blue-700 dark:bg-blue-950/40 dark:border-blue-800 dark:text-blue-300 rounded-lg text-[11px] font-medium hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors disabled:opacity-50 min-w-0 min-h-0"
            >
              {uploading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
              {settings?.logo_url ? "Ganti Logo" : "Upload Logo"}
            </button>
            <p className="text-[9px] text-muted-foreground mt-0.5">PNG/JPG, maks 5MB</p>
          </div>
        </div>
      </div>

      {/* Text Fields */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {fields.map(({ key, label, placeholder, multiline, type }) => (
          <div key={key} className={`space-y-0.5 ${multiline ? "sm:col-span-2" : ""}`}>
            <label className="text-[10px] font-medium text-muted-foreground">{label}</label>
            {multiline ? (
              <textarea
                data-testid={`settings-${key}`}
                rows={3}
                value={settings?.[key] || ""}
                onChange={e => handleChange(key, e.target.value)}
                placeholder={placeholder}
                className="w-full px-2 py-1.5 text-xs border border-border rounded-md focus:ring-1 focus:ring-blue-300 focus:border-blue-400 bg-card resize-y"
              />
            ) : (
            <input
              data-testid={`settings-${key}`}
              type={type || "text"}
              value={settings?.[key] || ""}
              onChange={e => handleChange(key, e.target.value)}
              placeholder={placeholder}
              className="w-full px-2 py-1.5 text-xs border border-border rounded-md focus:ring-1 focus:ring-blue-300 focus:border-blue-400 bg-card"
            />
            )}
          </div>
        ))}
      </div>

      <button
        data-testid="save-settings-btn"
        onClick={handleSave}
        disabled={saving}
        className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-lg text-xs font-medium transition-colors"
      >
        {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
        Simpan Pengaturan
      </button>
    </div>
  );
}
