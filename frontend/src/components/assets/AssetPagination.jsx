import React, { memo } from "react";
import {
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const AssetPagination = memo(function AssetPagination({
  currentPage, totalPages, totalItems, pageSize, setPageSize, goToPage,
}) {
  return (
    <div className="hidden md:block bg-card px-3 py-2 border border-border rounded-lg mb-16 lg:mb-0" data-testid="asset-pagination">
      <div className="flex flex-col sm:flex-row items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>
            <b>{((currentPage - 1) * pageSize) + 1}-{Math.min(currentPage * pageSize, totalItems)}</b> / <b>{totalItems.toLocaleString('id-ID')}</b>
          </span>
          <Select value={String(pageSize)} onValueChange={v => setPageSize(Number(v))}>
            <SelectTrigger className="w-16 h-6 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10</SelectItem>
              <SelectItem value="25">25</SelectItem>
              <SelectItem value="50">50</SelectItem>
              <SelectItem value="100">100</SelectItem>
              <SelectItem value="200">200</SelectItem>
              <SelectItem value="500">500</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-0.5">
          <Button variant="outline" size="sm" className="h-6 w-6 p-0" onClick={() => goToPage(1)} disabled={currentPage <= 1} data-testid="pagination-first">
            <ChevronsLeft className="w-3 h-3" />
          </Button>
          <Button variant="outline" size="sm" className="h-6 w-6 p-0" onClick={() => goToPage(currentPage - 1)} disabled={currentPage <= 1} data-testid="pagination-prev">
            <ChevronLeft className="w-3 h-3" />
          </Button>
          {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
            let page;
            if (totalPages <= 5) page = i + 1;
            else if (currentPage <= 3) page = i + 1;
            else if (currentPage >= totalPages - 2) page = totalPages - 4 + i;
            else page = currentPage - 2 + i;
            return (
              <Button
                key={page}
                variant={page === currentPage ? "default" : "outline"}
                size="sm"
                className={`h-6 w-6 p-0 text-xs ${i > 2 ? "hidden sm:inline-flex" : ""}`}
                onClick={() => goToPage(page)}
                data-testid={`pagination-page-${page}`}
              >
                {page}
              </Button>
            );
          })}
          <Button variant="outline" size="sm" className="h-6 w-6 p-0" onClick={() => goToPage(currentPage + 1)} disabled={currentPage >= totalPages} data-testid="pagination-next">
            <ChevronRight className="w-3 h-3" />
          </Button>
          <Button variant="outline" size="sm" className="h-6 w-6 p-0" onClick={() => goToPage(totalPages)} disabled={currentPage >= totalPages} data-testid="pagination-last">
            <ChevronsRight className="w-3 h-3" />
          </Button>
        </div>
      </div>
    </div>
  );
});

export default AssetPagination;
