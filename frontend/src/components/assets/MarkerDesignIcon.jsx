import React from "react";

// Pin + pensil: identitas yang sama untuk judul form, editor, dan ubah massal.
export default function MarkerDesignIcon({ className = "", ...props }) {
  return <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    aria-hidden="true" focusable="false" data-testid="marker-design-icon"
    className={`lucide lucide-map-pin-pencil ${className}`} {...props}>
    <path d="M14 8c0 4-6 9-6 9S2 12 2 8a6 6 0 0 1 12 0Z" />
    <circle cx="8" cy="8" r="2" />
    <path d="m14 21 7-7a1.4 1.4 0 0 0-2-2l-7 7-1 4 3-2Zm3-7 2 2" />
  </svg>;
}
