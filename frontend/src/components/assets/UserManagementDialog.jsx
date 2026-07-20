import React, { useState, useEffect, useCallback } from "react";
import { 
  Users, ShieldCheck, Loader2, KeyRound, Trash2, Eye, EyeOff, 
  Mail, UserPlus, Edit3, Check, X, Send, RefreshCw, 
  Copy, ChevronDown
} from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Switch } from "../ui/switch";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription
} from "../ui/dialog";
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger
} from "../ui/tooltip";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "../../lib/utils";
import { useConfirm } from "../ui/ConfirmDialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ROLES = {
  admin: { label: "Admin", dot: "bg-amber-400" },
  operator: { label: "Operator", dot: "bg-blue-400" },
  viewer: { label: "Viewer", dot: "bg-slate-300" },
};

const isValidEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

// Clean Minimal User Row
const UserRow = ({ user, isSelf, adminId, onRefresh, onUpdateLocalUser, satkerList = [] }) => {
  const [expanded, setExpanded] = useState(false);
  const [editName, setEditName] = useState(false);
  const [nameVal, setNameVal] = useState(user.name || '');
  const [pwForm, setPwForm] = useState(false);
  const [newPw, setNewPw] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const { confirm, confirmDialog } = useConfirm();

  const role = user.role || 'operator';
  const cfg = ROLES[role] || ROLES.viewer;
  const inactive = user.is_active === false;

  const toggle = async () => {
    if (isSelf) return;
    setBusy(true);
    try {
      await axios.put(`${API}/users/${user.id}/toggle-active?admin_id=${adminId}`);
      toast.success(inactive ? "Diaktifkan" : "Dinonaktifkan");
      onRefresh();
    } catch { toast.error("Gagal"); }
    setBusy(false);
  };

  const chgRole = async (r) => {
    if (isSelf) return;
    try {
      await axios.put(`${API}/users/${user.id}/change-role`, { new_role: r });
      toast.success(`Role → ${ROLES[r]?.label}`);
      onRefresh();
    } catch { toast.error("Gagal"); }
  };

  const chgSatker = async (kode) => {
    try {
      const v = kode === "__semua__" ? "" : kode;
      await axios.put(`${API}/users/${user.id}/satker`, { kode_satker: v });
      toast.success(v ? `Terikat ke satker ${v}` : "Lintas-satker (semua)");
      onRefresh();
    } catch (e) { toast.error(getApiError(e, "Gagal mengubah satker")); }
  };

  const saveName = async () => {
    if (!nameVal.trim()) return;
    try {
      await axios.put(`${API}/users/${user.id}/update-name?admin_id=${adminId}`, { name: nameVal.trim() });
      toast.success("Tersimpan");
      setEditName(false);
      onRefresh();
      if (isSelf && onUpdateLocalUser) {
        onUpdateLocalUser({ ...user, name: nameVal.trim() });
      }
    } catch { toast.error("Gagal"); }
  };

  const chgPw = async () => {
    if (newPw.length < 4) { toast.error("Min 4 karakter"); return; }
    try {
      await axios.put(`${API}/users/${user.id}/change-password`, { new_password: newPw });
      toast.success("Password diubah");
      setPwForm(false); setNewPw('');
    } catch { toast.error("Gagal"); }
  };

  const del = async () => {
    if (isSelf) return;
    const ok = await confirm({
      title: "Hapus Pengguna",
      description: `Pengguna "${user.name || user.username}" akan dihapus dari sistem. Lanjutkan?`,
      confirmLabel: "Hapus",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/users/${user.id}?admin_id=${adminId}`);
      toast.success("Dihapus");
      onRefresh();
    } catch { toast.error("Gagal"); }
  };

  return (
    <div className={`border-b border-border last:border-0 ${inactive ? 'opacity-40' : ''}`}>
      {confirmDialog}
      {/* Main Row */}
      <div className={`flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-2 hover:bg-muted/50 transition-colors ${isSelf ? 'bg-blue-50/30 dark:bg-blue-900/20' : ''}`}>
        {/* Avatar */}
        <div className="relative flex-shrink-0" title={user.is_online ? "Online" : `Offline${user.last_active ? ` - Terakhir aktif: ${new Date(user.last_active).toLocaleString('id-ID')}` : ''}`}>
          <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-xs font-medium text-muted-foreground">
            {(user.name || user.username || "?")[0].toUpperCase()}
          </div>
          <div data-testid={`user-status-${user.id}`} className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-card ${user.is_online ? 'bg-emerald-400' : inactive ? 'bg-slate-300 dark:bg-slate-600' : 'bg-slate-400 dark:bg-slate-500'}`} />
        </div>

        {/* Name & Email */}
        <div className="flex-1 min-w-0">
          {editName ? (
            <div className="flex items-center gap-1">
              <input
                value={nameVal}
                onChange={e => setNameVal(e.target.value)}
                className="flex-1 h-6 px-2 text-xs border border-border rounded focus:outline-none focus:border-blue-400 bg-background text-foreground"
                autoFocus
                onKeyDown={e => e.key === 'Enter' && saveName()}
              />
              <button onClick={saveName} className="p-0.5 text-emerald-500 hover:text-emerald-600"><Check className="w-3.5 h-3.5" /></button>
              <button onClick={() => setEditName(false)} className="p-0.5 text-muted-foreground hover:text-muted-foreground"><X className="w-3.5 h-3.5" /></button>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-1.5">
                <span className="text-[13px] font-medium text-foreground truncate">{user.name || user.username}</span>
                {isSelf && <span className="text-[9px] font-medium text-blue-500 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/30 px-1 py-0.5 rounded">You</span>}
              </div>
              <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                <span className="truncate">{user.username}</span>
                <span className={`inline-flex items-center gap-0.5 text-[9px] font-medium px-1 py-0.5 rounded-full ${user.is_online ? 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400' : 'bg-muted text-muted-foreground'}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${user.is_online ? 'bg-emerald-400' : 'bg-slate-300 dark:bg-slate-600'}`} />
                  {user.is_online ? 'Online' : 'Offline'}
                </span>
              </div>
            </>
          )}
        </div>

        {/* Role indicator */}
        <div className="flex items-center gap-1">
          <div className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
          <span className="text-[11px] text-muted-foreground">{cfg.label}</span>
        </div>

        {/* Toggle - small & consistent */}
        {!isSelf && (
          <Switch 
            checked={!inactive} 
            onCheckedChange={toggle}
            disabled={busy}
            className="data-[state=checked]:bg-emerald-400 h-4 w-7"
          />
        )}

        {/* Expand */}
        <button 
          onClick={() => setExpanded(!expanded)}
          className={`p-1 rounded transition-colors ${expanded ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}`}
        >
          <ChevronDown className={`w-3.5 h-3.5 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* Expanded Actions */}
      {expanded && (
        <div className="px-3 pb-2 pt-1 bg-muted/50">
          <div className="flex flex-wrap items-center gap-1.5">
            {/* Edit Name - Icon only on mobile with tooltip */}
            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button 
                    onClick={() => { setEditName(true); setNameVal(user.name || ''); setExpanded(false); }}
                    className="flex items-center justify-center h-6 w-6 sm:w-auto sm:px-2 text-[10px] bg-card border border-border rounded text-muted-foreground hover:border-border"
                  >
                    <Edit3 className="w-3 h-3 sm:mr-1" />
                    <span className="hidden sm:inline">Nama</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="sm:hidden">
                  <p>Edit Nama</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            
            {/* Role Select - Keep text */}
            {!isSelf && (
              <Select value={role} onValueChange={chgRole}>
                <SelectTrigger className="h-6 w-[70px] text-[10px] bg-card border-border">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin" className="text-xs">Admin</SelectItem>
                  <SelectItem value="operator" className="text-xs">Operator</SelectItem>
                  <SelectItem value="viewer" className="text-xs">Viewer</SelectItem>
                </SelectContent>
              </Select>
            )}

            {/* Ikatan satker (multi-satker DB bersama): kosong = lintas-satker.
                Admin lintas-satker berperan super-admin. */}
            {satkerList.length > 0 && (
              <Select value={user.kode_satker || "__semua__"} onValueChange={chgSatker}>
                <SelectTrigger className="h-6 w-[130px] text-[10px] bg-card border-border" data-testid={`user-satker-${user.id}`}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__semua__" className="text-xs">Semua satker</SelectItem>
                  {satkerList.map(s => (
                    <SelectItem key={s.kode_satker} value={s.kode_satker} className="text-xs">
                      {s.kode_satker} — {s.nama_satker}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            
            {/* Password - Icon only on mobile with tooltip */}
            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button 
                    onClick={() => setPwForm(!pwForm)}
                    className="flex items-center justify-center h-6 w-6 sm:w-auto sm:px-2 text-[10px] bg-card border border-border rounded text-muted-foreground hover:border-border"
                  >
                    <KeyRound className="w-3 h-3 sm:mr-1" />
                    <span className="hidden sm:inline">Password</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="sm:hidden">
                  <p>Ubah Password</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            
            {/* Copy Email - Keep text */}
            <button 
              onClick={() => { navigator.clipboard.writeText(user.username); toast.success("Email disalin"); }}
              className="flex items-center gap-1 h-6 px-2 text-[10px] bg-card border border-border rounded text-muted-foreground hover:border-border"
              title="Salin Email"
            >
              <Copy className="w-3 h-3" />
              <span>Email</span>
            </button>
            
            {/* Delete - Icon only on mobile with tooltip */}
            {!isSelf && (
              <TooltipProvider delayDuration={100}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button 
                      onClick={del}
                      className="flex items-center justify-center h-6 w-6 sm:w-auto sm:px-2 text-[10px] bg-card border border-red-200 dark:border-red-800 rounded text-red-500 hover:border-red-300 dark:hover:border-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                    >
                      <Trash2 className="w-3 h-3 sm:mr-1" />
                      <span className="hidden sm:inline">Hapus</span>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" className="sm:hidden">
                    <p>Hapus User</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>

          {/* Password Form */}
          {pwForm && (
            <div className="flex items-center gap-1.5 mt-2">
              <div className="relative flex-1">
                <input
                  type={showPw ? "text" : "password"}
                  value={newPw}
                  onChange={e => setNewPw(e.target.value)}
                  placeholder="Password baru"
                  className="w-full h-7 px-2 pr-8 text-xs border border-border rounded focus:outline-none focus:border-blue-400 bg-background text-foreground"
                  onKeyDown={e => e.key === 'Enter' && chgPw()}
                />
                <button 
                  type="button"
                  onClick={() => setShowPw(!showPw)} 
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-muted-foreground"
                >
                  {showPw ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
              <button onClick={chgPw} className="h-7 px-3 text-[10px] font-medium bg-slate-800 text-white rounded hover:bg-slate-700">Simpan</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// Main Dialog
function UserManagementDialog({ open, onClose, currentUser }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [pw, setPw] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState('');
  const [otpLoading, setOtpLoading] = useState(false);
  const [debugOtp, setDebugOtp] = useState(null);

  const isAdmin = currentUser?.role === 'admin';
  const adminId = currentUser?.id || '';

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/users?admin_id=${adminId}`);
      setUsers(r.data);
    } catch {}
    setLoading(false);
  }, [adminId]);

  // Master satker utk ikatan user→satker (multi-satker DB bersama);
  // gagal senyap — dropdown satker cukup tak muncul.
  const [satkerList, setSatkerList] = useState([]);
  useEffect(() => {
    if (!open) return;
    axios.get(`${API}/satker`)
      .then(r => setSatkerList((r.data?.items || []).filter(s => s.terdaftar)))
      .catch(() => {});
  }, [open]);

  useEffect(() => { if (open) fetchUsers(); }, [open, fetchUsers]);

  const handleUpdateLocalUser = (updatedUser) => {
    try {
      const stored = localStorage.getItem('user');
      if (stored) {
        const current = JSON.parse(stored);
        if (current.id === updatedUser.id) {
          localStorage.setItem('user', JSON.stringify({ ...current, name: updatedUser.name }));
        }
      }
    } catch {}
  };

  const sendOtp = async () => {
    if (!isValidEmail(email)) { toast.error("Email tidak valid"); return; }
    if (pw.length < 4) { toast.error("Password min 4 karakter"); return; }
    setOtpLoading(true);
    try {
      const r = await axios.post(`${API}/auth/request-otp`, { email, password: pw, name: name || email.split('@')[0] });
      if (!r.data?.otp_sent && !r.data?.debug_otp) {
        toast.error(r.data?.message || "Email gagal terkirim — periksa konfigurasi email server");
        setOtpLoading(false);
        return;
      }
      toast.success("OTP terkirim");
      setOtpSent(true);
      if (r.data.debug_otp) setDebugOtp(r.data.debug_otp);
    } catch (e) { toast.error(getApiError(e, "Gagal")); }
    setOtpLoading(false);
  };

  const verifyOtp = async () => {
    if (otp.length < 6) { toast.error("6 digit OTP"); return; }
    setOtpLoading(true);
    try {
      await axios.post(`${API}/auth/verify-otp`, { email, otp });
      toast.success("User ditambahkan!");
      resetForm();
      fetchUsers();
    } catch (e) { toast.error(getApiError(e, "OTP salah")); }
    setOtpLoading(false);
  };

  const resetForm = () => {
    setShowAdd(false); setEmail(''); setName(''); setPw(''); setOtpSent(false); setOtp(''); setDebugOtp(null);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="w-[95vw] max-w-sm max-h-[80vh] overflow-hidden flex flex-col p-0 gap-0 rounded-xl [&>button.absolute]:hidden">
        {/* Header */}
        <DialogHeader className="px-3 sm:px-4 py-2.5 sm:py-3 border-b border-border flex-shrink-0">
          <DialogTitle className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <div className="w-6 h-6 rounded-lg bg-muted flex items-center justify-center">
              <Users className="w-3.5 h-3.5 text-muted-foreground" />
            </div>
            Users
            <span className="text-[10px] text-muted-foreground font-normal ml-1">{users.length}</span>
            <button 
              onClick={() => onClose(false)}
              className="ml-auto inline-flex items-center justify-center p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              data-testid="user-mgmt-close"
            >
              <X className="w-4 h-4" />
            </button>
          </DialogTitle>
          <DialogDescription className="sr-only">User management</DialogDescription>
        </DialogHeader>

        {!isAdmin ? (
          <div className="flex-1 flex flex-col items-center justify-center py-10 text-center">
            <ShieldCheck className="w-8 h-8 text-slate-300 dark:text-slate-600 mb-2" />
            <p className="text-xs text-muted-foreground">Admin only</p>
          </div>
        ) : loading ? (
          <div className="flex-1 flex items-center justify-center py-10">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            {/* Add User */}
            <div className="p-3 border-b border-border">
              {!showAdd ? (
                <button
                  onClick={() => setShowAdd(true)}
                  className="w-full h-8 border border-dashed border-border rounded-lg flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground hover:border-foreground/30 hover:text-foreground hover:bg-muted/50 transition-all"
                  data-testid="add-user-btn"
                >
                  <UserPlus className="w-3.5 h-3.5" /> Tambah user
                </button>
              ) : (
                <div className="bg-muted rounded-lg p-3" data-testid="add-user-form">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-medium text-muted-foreground">{otpSent ? 'Verifikasi OTP' : 'User baru'}</span>
                    <button onClick={resetForm} className="text-muted-foreground hover:text-muted-foreground"><X className="w-3.5 h-3.5" /></button>
                  </div>
                  
                  {!otpSent ? (
                    <div className="space-y-2">
                      <div className="relative">
                        <Mail className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground" />
                        <input 
                          type="email" 
                          value={email} 
                          onChange={e => setEmail(e.target.value)} 
                          placeholder="Email" 
                          className="w-full h-8 pl-7 pr-2 text-xs border border-border rounded-lg bg-card text-foreground focus:outline-none focus:border-blue-400" 
                          data-testid="new-user-email" 
                        />
                      </div>
                      <input 
                        value={name} 
                        onChange={e => setName(e.target.value)} 
                        placeholder="Nama (opsional)" 
                        className="w-full h-8 px-2 text-xs border border-border rounded-lg bg-card text-foreground focus:outline-none focus:border-blue-400" 
                        data-testid="new-user-name" 
                      />
                      <div className="relative">
                        <input 
                          type={showPw ? "text" : "password"} 
                          value={pw} 
                          onChange={e => setPw(e.target.value)} 
                          placeholder="Password" 
                          className="w-full h-8 px-2 pr-8 text-xs border border-border rounded-lg bg-card text-foreground focus:outline-none focus:border-blue-400" 
                          data-testid="new-user-password" 
                        />
                        <button 
                          type="button"
                          onClick={() => setShowPw(!showPw)} 
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-muted-foreground"
                        >
                          {showPw ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                      <button 
                        onClick={sendOtp} 
                        disabled={otpLoading} 
                        className="w-full h-8 text-[11px] font-medium bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 flex items-center justify-center gap-1" 
                        data-testid="send-otp-btn"
                      >
                        {otpLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />} Kirim OTP
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-[10px] text-muted-foreground">OTP dikirim ke <b>{email}</b></p>
                      {debugOtp && <div className="px-2 py-1 bg-amber-50 dark:bg-amber-900/30 rounded text-[9px] text-amber-600 dark:text-amber-400">Debug: {debugOtp}</div>}
                      <input 
                        value={otp} 
                        onChange={e => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))} 
                        placeholder="000000" 
                        className="w-full h-10 text-center text-base tracking-[0.3em] font-mono border border-border rounded-lg bg-card text-foreground focus:outline-none focus:border-blue-400" 
                        maxLength={6} 
                        data-testid="otp-input" 
                      />
                      <div className="flex gap-2">
                        <button 
                          onClick={verifyOtp} 
                          disabled={otpLoading || otp.length < 6} 
                          className="flex-1 h-8 text-[11px] font-medium bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 flex items-center justify-center gap-1" 
                          data-testid="verify-otp-btn"
                        >
                          {otpLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />} Verifikasi
                        </button>
                        <button 
                          onClick={() => { setOtpSent(false); setOtp(''); }} 
                          className="h-8 px-3 text-[11px] border border-border rounded-lg hover:bg-muted"
                        >
                          <RefreshCw className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* User List */}
            <div>
              {users.map(u => (
                <UserRow
                  key={u.id}
                  user={u}
                  isSelf={u.id === adminId}
                  adminId={adminId}
                  onRefresh={fetchUsers}
                  onUpdateLocalUser={handleUpdateLocalUser}
                  satkerList={satkerList}
                />
              ))}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default UserManagementDialog;
