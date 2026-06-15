import React, { memo } from "react";
import { Package } from "lucide-react";

// ============================================================================
// LOADING INDICATOR COMPONENT - Shows progress for large data loads
// ============================================================================
const LoadingIndicator = memo(({ message, totalItems, pageSize, currentPage }) => {
  const startItem = totalItems > 0 ? ((currentPage - 1) * pageSize) + 1 : 0;
  const endItem = Math.min(currentPage * pageSize, totalItems);
  
  return (
    <div className="flex flex-col items-center justify-center py-16 space-y-4">
      {/* Animated spinner */}
      <div className="relative">
        <div className="w-16 h-16 border-4 border-blue-100 rounded-full"></div>
        <div className="absolute top-0 left-0 w-16 h-16 border-4 border-blue-600 rounded-full border-t-transparent animate-spin"></div>
        <Package className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-6 h-6 text-blue-600" />
      </div>
      
      {/* Loading message */}
      <div className="text-center space-y-1">
        <p className="text-foreground font-medium">{message || "Memuat data..."}</p>
        {totalItems > 0 && (
          <p className="text-sm text-muted-foreground">
            Menampilkan {startItem.toLocaleString('id-ID')} - {endItem.toLocaleString('id-ID')} dari {totalItems.toLocaleString('id-ID')} aset
          </p>
        )}
      </div>
      
      {/* Progress bar (if we know total) */}
      {totalItems > 0 && (
        <div className="w-48 bg-muted rounded-full h-1.5 overflow-hidden">
          <div 
            className="h-full bg-blue-600 rounded-full transition-all duration-300"
            style={{ width: `${Math.min((endItem / totalItems) * 100, 100)}%` }}
          ></div>
        </div>
      )}
      
      {/* Skeleton preview */}
      <div className="w-full max-w-md space-y-2 opacity-50">
        {[1, 2, 3].map(i => (
          <div key={i} className="bg-muted rounded-lg p-3 animate-pulse">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-muted rounded"></div>
              <div className="flex-1 space-y-1">
                <div className="h-3 bg-muted rounded w-1/3"></div>
                <div className="h-2 bg-muted rounded w-1/2"></div>
              </div>
              <div className="h-5 w-12 bg-muted rounded-full"></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
});
LoadingIndicator.displayName = "LoadingIndicator";

export default LoadingIndicator;
