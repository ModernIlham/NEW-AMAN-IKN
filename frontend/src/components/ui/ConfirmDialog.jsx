import React, { useState, useCallback, useRef, useEffect } from "react";
import { AlertTriangle, ShieldCheck, Loader2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogCancel,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// ============================================================================
// CONFIRM DIALOG — pengganti window.confirm yang branded + dark-mode + non-blocking.
// Dibangun di atas Radix AlertDialog. Dua cara pakai:
//   1) Controlled : <ConfirmDialog open onOpenChange onConfirm ... />
//   2) Hook       : const { confirm, confirmDialog } = useConfirm();
//                   if (!(await confirm({ title, description, ... }))) return;
//                   ... lalu render {confirmDialog} sekali di komponen.
//
// requireText: bila diisi, tombol konfirmasi terkunci sampai user mengetik
// string persis — dipakai untuk aksi kaskade/irreversibel (mis. hapus kegiatan).
// ============================================================================
export function ConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  title = "Konfirmasi",
  description,
  confirmLabel = "Lanjutkan",
  cancelLabel = "Batal",
  variant = "default",
  requireText,
  loading = false,
}) {
  const [typed, setTyped] = useState("");
  const inputRef = useRef(null);
  const danger = variant === "danger";
  const needsText = typeof requireText === "string" && requireText.length > 0;
  const canConfirm = !needsText || typed === requireText;

  // Reset the typed guard each time the dialog opens; autofocus the input.
  useEffect(() => {
    if (open) {
      setTyped("");
      if (needsText) setTimeout(() => inputRef.current?.focus(), 80);
    }
  }, [open, needsText]);

  const handleConfirm = () => {
    if (!canConfirm || loading) return;
    onConfirm?.();
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent
        className="max-w-md"
        data-testid="confirm-dialog"
        onKeyDown={(e) => {
          if (e.key === "Enter" && canConfirm && !loading) {
            e.preventDefault();
            handleConfirm();
          }
        }}
      >
        <AlertDialogHeader>
          <AlertDialogTitle className={`flex items-center gap-2 ${danger ? "text-red-600 dark:text-red-400" : ""}`}>
            {danger
              ? <AlertTriangle className="w-5 h-5 flex-shrink-0" />
              : <ShieldCheck className="w-5 h-5 text-blue-600 flex-shrink-0" />}
            {title}
          </AlertDialogTitle>
          {description && (
            <AlertDialogDescription className="whitespace-pre-line">
              {description}
            </AlertDialogDescription>
          )}
        </AlertDialogHeader>

        {needsText && (
          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground">
              Ketik{" "}
              <span className="font-mono font-bold text-foreground bg-muted px-1.5 py-0.5 rounded border border-border select-all">
                {requireText}
              </span>{" "}
              untuk konfirmasi.
            </p>
            <Input
              ref={inputRef}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="off"
              spellCheck="false"
              className="h-9 text-sm"
              data-testid="confirm-dialog-input"
            />
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading} data-testid="confirm-dialog-cancel">
            {cancelLabel}
          </AlertDialogCancel>
          <Button
            type="button"
            variant={danger ? "destructive" : "default"}
            disabled={!canConfirm || loading}
            onClick={handleConfirm}
            className={danger ? "bg-red-600 hover:bg-red-700 text-white" : ""}
            data-testid="confirm-dialog-confirm"
          >
            {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {confirmLabel}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

// Promise-based confirm — swap `if (!window.confirm(x)) return` for
// `if (!(await confirm({ ... }))) return`. Render {confirmDialog} once.
export function useConfirm() {
  const [state, setState] = useState({ open: false, options: {} });
  const resolverRef = useRef(null);

  const confirm = useCallback((options = {}) => {
    return new Promise((resolve) => {
      resolverRef.current = resolve;
      setState({ open: true, options });
    });
  }, []);

  const settle = useCallback((result) => {
    setState((s) => ({ ...s, open: false }));
    const resolve = resolverRef.current;
    resolverRef.current = null;
    resolve?.(result);
  }, []);

  const handleOpenChange = useCallback((next) => {
    if (!next) settle(false);
  }, [settle]);

  const confirmDialog = (
    <ConfirmDialog
      {...state.options}
      open={state.open}
      onOpenChange={handleOpenChange}
      onConfirm={() => settle(true)}
    />
  );

  return { confirm, confirmDialog };
}

export default ConfirmDialog;
