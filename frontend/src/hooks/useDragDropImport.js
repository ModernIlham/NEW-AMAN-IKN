/**
 * useDragDropImport - Manages drag & drop file import state.
 */
import { useState, useRef, useCallback } from "react";
import { toast } from "sonner";

export function useDragDropImport({ onFileDropped }) {
  const [isDragOverImport, setIsDragOverImport] = useState(false);
  const [dropFile, setDropFile] = useState(null);
  const dragCounterRef = useRef(0);

  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    if (e.dataTransfer.items?.length > 0) setIsDragOverImport(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) setIsDragOverImport(false);
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOverImport(false);
    dragCounterRef.current = 0;
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['csv', 'xlsx', 'xls'].includes(ext)) {
      toast.error("Format file tidak didukung. Gunakan CSV atau Excel (.xlsx)");
      return;
    }
    setDropFile(file);
    onFileDropped?.();
  }, [onFileDropped]);

  const clearDropFile = useCallback(() => setDropFile(null), []);

  return {
    isDragOverImport,
    dropFile,
    handleDragEnter,
    handleDragLeave,
    handleDragOver,
    handleDrop,
    clearDropFile,
  };
}
