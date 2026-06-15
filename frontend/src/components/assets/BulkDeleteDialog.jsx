import React, { memo, useState, useCallback } from "react";
import { AlertTriangle, Trash2, Loader2 } from "lucide-react";
import { Button } from "../ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "../../lib/utils";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BulkDeleteDialog = memo(({ open, onClose, activityId, activityName, totalItems, onSuccess }) => {
  const [deleting, setDeleting] = useState(false);

  const handleDelete = useCallback(async () => {
    if (!activityId) { toast.error("Pilih kegiatan inventarisasi terlebih dahulu"); return; }
    setDeleting(true);
    try {
      const r = await axios.delete(`${API}/assets/bulk-delete/${activityId}`);
      toast.success(r.data.message);
      onClose(false);
      onSuccess?.();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menghapus data"));
    } finally {
      setDeleting(false);
    }
  }, [activityId, onClose, onSuccess]);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-red-600">
            <AlertTriangle className="w-5 h-5" />
            Hapus Semua Aset
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-4">
            <p className="text-sm text-red-800 dark:text-red-300 font-medium mb-2">
              Anda akan menghapus SEMUA data aset dari kegiatan:
            </p>
            <p className="text-sm text-red-700 dark:text-red-400 font-bold">"{activityName}"</p>
            <p className="text-xs text-red-600 dark:text-red-400 mt-2">
              Total: <b>{totalItems}</b> aset akan dihapus
            </p>
          </div>
          <p className="text-sm text-muted-foreground">
            Tindakan ini <b>tidak dapat dibatalkan</b>. Semua data aset, foto, dan dokumen kelengkapan akan dihapus permanen.
          </p>
          <div className="flex gap-3 justify-end">
            <Button variant="outline" onClick={() => onClose(false)} disabled={deleting}>Batal</Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting} className="bg-red-600 hover:bg-red-700">
              {deleting ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Menghapus...</> : <><Trash2 className="w-4 h-4 mr-2" />Ya, Hapus Semua</>}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
});

BulkDeleteDialog.displayName = "BulkDeleteDialog";
export default BulkDeleteDialog;
