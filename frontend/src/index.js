import React from "react";
import ReactDOM from "react-dom/client";
// Font DIBUNDEL, bukan dari CDN Google Fonts. Aplikasi ini PWA lapangan yang
// wajib hidup saat luring — font dari CDN gagal justru di kondisi itu, dan
// @import CSS-nya memblokir render pertama. Plus Jakarta Sans (variabel,
// 200–800) dirancang Tokotype untuk instansi pemerintah Indonesia; JetBrains
// Mono untuk kode barang/NUP/nomor — angka sejajar kolom.
import "@fontsource-variable/plus-jakarta-sans";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@/index.css";
import App from "@/App";
import { pasangMarqueeEllipsis } from "@/lib/marqueeEllipsis";

// Teks ber-"..." di mana pun otomatis menggulir penuh saat hover/ketuk,
// lalu kembali ber-elipsis — dipasang sekali, berlaku seluruh aplikasi.
pasangMarqueeEllipsis();

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
