import React, { memo } from "react";
import {
  Package, ArrowLeft, Users, History, LogOut,
  Wifi, WifiOff, Users2, RefreshCw, Moon, Sun, MoreVertical
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { useTripleClick } from "@/hooks/useTripleClick";

const DashboardHeader = memo(({
  activity, user, perms, onBack, onLogout,
  auditOpen, onAuditToggle, onOpenUserManagement,
  isOnline, wsConnected, onlineUsers, pendingCount, syncing, onSync,
  dark, toggleDark, onShowInfo,
}) => {
  // Halaman Info tersembunyi: butuh 3 klik beruntun pada logo
  const activateInfo = useTripleClick(onShowInfo);
  return (
  <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-4 py-2.5 sticky top-0 z-40 print:hidden" data-testid="dashboard-header">
    <div className="flex items-center justify-between gap-2 min-w-0">
      <div className="flex items-center gap-2 min-w-0 overflow-hidden flex-shrink">
        <Button variant="ghost" size="sm" onClick={onBack} className="h-8 w-8 p-0 flex-shrink-0 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors duration-180">
          <ArrowLeft className="w-4 h-4 text-blue-600 dark:text-blue-400" />
        </Button>
        <div className="flex items-center gap-2 min-w-0 overflow-hidden">
          {/* Klik logo 3x beruntun = buka halaman Info/PRD tersembunyi */}
          <div
            className={`w-9 h-9 rounded-lg bg-gradient-to-br from-blue-600 to-blue-500 flex items-center justify-center flex-shrink-0 shadow-elev-1 ${onShowInfo ? "cursor-pointer" : ""}`}
            {...(onShowInfo ? {
              role: "button", tabIndex: 0, onClick: activateInfo,
              onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activateInfo(); } },
              "aria-label": "Info aplikasi (klik 3 kali)",
            } : {})}
            data-testid="dashboard-logo"
          >
            <Package className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
          </div>
          <div className="min-w-0 overflow-hidden">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight truncate font-['Manrope']">
              {activity?.nama_kegiatan || 'Manajemen Aset'}
            </h1>
            <p className="text-[10px] text-muted-foreground hidden sm:flex items-center gap-1.5 truncate">
              {activity?.ticket_number && (
                <span className="font-mono font-semibold bg-slate-800 text-slate-100 dark:bg-slate-200 dark:text-slate-800 px-1 py-px rounded" data-testid="header-ticket-badge">{activity.ticket_number}</span>
              )}
              <span className="truncate">{activity?.nomor_surat}</span>
            </p>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        {/* Online/Offline */}
        <div className="flex items-center gap-1 mr-0.5">
          {!isOnline ? (
            <span className="flex items-center gap-1 text-[10px] bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400 px-1.5 py-0.5 rounded-full font-medium" data-testid="offline-indicator">
              <WifiOff className="w-3 h-3" /> Offline
            </span>
          ) : pendingCount > 0 ? (
            <button onClick={onSync} disabled={syncing} className="flex items-center gap-1 text-[10px] bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400 px-1.5 py-0.5 rounded-full font-medium" data-testid="sync-pending-btn">
              <RefreshCw className={`w-3 h-3 ${syncing ? 'animate-spin' : ''}`} /> {pendingCount}
            </button>
          ) : wsConnected ? (
            <Wifi className="w-3 h-3 text-emerald-500" data-testid="online-indicator" />
          ) : (
            <span className="flex items-center gap-1 text-[10px] bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400 px-1.5 py-0.5 rounded-full font-medium" data-testid="ws-disconnected-indicator" title="Koneksi real-time terputus — perubahan tetap tersimpan, namun notifikasi dari user lain tertunda">
              <WifiOff className="w-3 h-3" /> WS
            </span>
          )}
          {onlineUsers.length > 1 && (
            <span className="flex items-center gap-0.5 text-[9px] bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400 px-1.5 py-0.5 rounded-full font-medium" data-testid="online-users-count" title={onlineUsers.map(u => u.user_name).join(', ')}>
              <Users2 className="w-2.5 h-2.5" /> {onlineUsers.length}
            </span>
          )}
        </div>
        {/* Dark mode */}
        <button
          onClick={toggleDark}
          className={`h-7 w-7 rounded-lg flex items-center justify-center transition-all duration-180 border ${
            dark
              ? "bg-slate-700 border-slate-600 hover:bg-slate-600 hover:shadow-elev-1 text-amber-400"
              : "bg-card border-border hover:bg-muted hover:shadow-elev-1 text-muted-foreground"
          }`}
          data-testid="dark-mode-toggle"
          title={dark ? "Light mode" : "Dark mode"}
        >
          {dark ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
        </button>
        {/* ≥sm: tombol individual (Pengguna / Riwayat / Keluar). */}
        {perms.canManageUsers && (
          <Button variant="ghost" size="sm" onClick={onOpenUserManagement} aria-label="Kelola Pengguna" title="Kelola Pengguna" className="h-7 px-2 gap-1 text-xs hidden sm:flex flex-shrink-0" data-testid="header-users-btn">
            <Users className="w-3.5 h-3.5" /><span className="hidden md:inline">Pengguna</span>
          </Button>
        )}
        <Button variant={auditOpen ? "default" : "ghost"} size="sm" onClick={onAuditToggle} className={`h-7 gap-1 text-xs hidden sm:flex ${auditOpen ? 'bg-blue-600 text-white hover:bg-blue-700' : ''}`} data-testid="audit-toggle-btn">
          <History className="w-3 h-3" /><span className="hidden sm:inline">Riwayat</span>
        </Button>
        <span className={`text-[9px] px-1 py-0.5 rounded font-bold hidden sm:inline ${
          perms.role === 'admin' ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400' :
          perms.role === 'operator' ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400' :
          'bg-muted text-muted-foreground'
        }`} data-testid="user-role-badge">{perms.role === 'admin' ? 'Admin' : perms.role === 'operator' ? 'Operator' : 'Viewer'}</span>
        <Button variant="outline" size="sm" onClick={onLogout} className="h-7 gap-1 text-xs hidden sm:flex"><LogOut className="w-3 h-3" /><span className="hidden sm:inline">Keluar</span></Button>

        {/* HP: satu menu ringkas berisi Pengguna + Riwayat + Keluar — header
            terlalu penuh bila ketiganya jadi tombol terpisah di layar kecil. */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label="Menu: pengguna, riwayat, keluar"
              className="h-7 w-7 rounded-lg border border-border text-foreground/80 flex sm:hidden items-center justify-center hover:bg-muted flex-shrink-0"
              data-testid="header-more-menu"
            >
              <MoreVertical className="w-4 h-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            {perms.canManageUsers && (
              <DropdownMenuItem className="min-h-[42px]" onClick={onOpenUserManagement} data-testid="header-more-users">
                <Users className="w-4 h-4 mr-2" />Kelola Pengguna
              </DropdownMenuItem>
            )}
            <DropdownMenuItem className="min-h-[42px]" onClick={onAuditToggle} data-testid="header-more-audit">
              <History className="w-4 h-4 mr-2" />Riwayat {auditOpen ? "(tutup)" : ""}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="min-h-[42px] text-red-600 dark:text-red-400 focus:text-red-600" onClick={onLogout} data-testid="header-more-logout">
              <LogOut className="w-4 h-4 mr-2" />Keluar
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  </header>
  );
});

DashboardHeader.displayName = "DashboardHeader";
export default DashboardHeader;
