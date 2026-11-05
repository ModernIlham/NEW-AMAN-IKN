import React, { useCallback } from "react";
import * as Alert from "@radix-ui/react-alert-dialog";
import { Loader2, Trash2 } from "lucide-react";
import { useBackGuard } from "../../hooks/useBackGuard";

export default function ConfirmPhotoDelete({ src, busy = false, onCancel, onConfirm, description, testId = "photo-delete-confirm" }) {
  useBackGuard(useCallback(() => { if (!busy) onCancel(); }, [busy, onCancel]));
  return <Alert.Root open onOpenChange={open => { if (!open && !busy) onCancel(); }}>
    <Alert.Portal>
      <Alert.Overlay className="fixed inset-0 z-[170] bg-black/75" onClick={e => e.stopPropagation()} />
      <Alert.Content className="fixed left-1/2 top-1/2 z-[171] -translate-x-1/2 -translate-y-1/2 w-[calc(100vw-2rem)] max-w-sm rounded-xl bg-card p-4 shadow-xl space-y-3"
        onClick={e => e.stopPropagation()} onTouchStart={e => e.stopPropagation()} onTouchEnd={e => e.stopPropagation()}
        onEscapeKeyDown={e => { e.stopPropagation(); if (busy) e.preventDefault(); }}>
        <img src={src} alt="Foto yang akan dihapus" className="w-full max-h-56 object-contain rounded-lg bg-muted" />
        <Alert.Title className="text-sm font-semibold text-center">Hapus foto ini?</Alert.Title>
        <Alert.Description className="text-xs text-muted-foreground text-center">{description || "Foto akan dihapus dari aset. Foto lainnya tetap dipertahankan."}</Alert.Description>
        <div className="grid grid-cols-2 gap-2">
          <Alert.Cancel disabled={busy} className="h-11 rounded-lg border border-border text-sm">Batal</Alert.Cancel>
          <Alert.Action disabled={busy} onClick={e => { e.preventDefault(); onConfirm(); }} data-testid={testId}
            className="h-11 rounded-lg bg-red-600 text-white text-sm font-semibold flex items-center justify-center gap-1.5 disabled:opacity-50">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}Hapus
          </Alert.Action>
        </div>
      </Alert.Content>
    </Alert.Portal>
  </Alert.Root>;
}
