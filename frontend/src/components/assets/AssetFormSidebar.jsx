import React from "react";
import AssetForm from "./AssetForm";

// Satu pemilik draf/tab untuk kedua ukuran layar. Perubahan breakpoint hanya
// mengubah posisi/ukuran, tidak mengganti instance form yang sedang diketik.
export default function AssetFormSidebar({ isDesktop, panelVisible, isOpen, ...formProps }) {
  return <div data-testid="asset-form-sidebar"
    className={`shrink-0 ${isDesktop ? (panelVisible ? "w-[320px] min-w-[320px]" : "w-0 min-w-0 overflow-hidden") : "w-0"}`}
    style={isDesktop ? { transition: "width 0.3s ease, min-width 0.3s ease", willChange: "width", contain: "layout style" } : undefined}>
    <AssetForm {...formProps} isOpen={isDesktop ? isOpen || panelVisible : isOpen} alwaysExpanded={isDesktop && panelVisible} />
  </div>;
}
