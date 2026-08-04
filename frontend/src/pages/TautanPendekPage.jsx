/**
 * Halaman pengalihan tautan pendek: /s/{kode} → tujuan sebenarnya.
 *
 * Kenapa dialihkan dari SPA, bukan 301 dari nginx: fitur ini ikut pipeline
 * deploy biasa, jadi konfigurasi nginx di VPS tak perlu disentuh dan tak ada
 * mode gagal senyap "tautan pendek 404 karena nginx belum diperbarui".
 * Ongkosnya satu kali boot SPA — tujuannya memang SPA ini juga.
 *
 * `replace` (bukan `assign`) supaya tombol Kembali peramban tidak melempar
 * penerima balik ke halaman pengalihan dan memutarnya berulang-ulang.
 */
import React, { useEffect, useState } from "react";
import axios from "axios";
import { Link2Off, Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

export default function TautanPendekPage() {
  const [galat, setGalat] = useState("");

  useEffect(() => {
    const kode = decodeURIComponent(
      window.location.pathname.replace(/^\/s\//, "").split(/[/?#]/)[0] || ""
    );
    if (!kode) {
      setGalat("Tautan tidak lengkap.");
      return;
    }
    let batal = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/s/${encodeURIComponent(kode)}`);
        const tujuan = r?.data?.tujuan;
        if (batal) return;
        if (!tujuan) {
          setGalat("Tautan tidak dikenal atau sudah tidak berlaku.");
          return;
        }
        window.location.replace(tujuan);
      } catch (e) {
        if (batal) return;
        setGalat(
          e?.response?.status === 404
            ? "Tautan tidak dikenal atau sudah tidak berlaku."
            : "Gagal membuka tautan. Periksa koneksi lalu coba lagi."
        );
      }
    })();
    return () => {
      batal = true;
    };
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background">
      <div className="max-w-sm w-full text-center" data-testid="tautan-pendek">
        {galat ? (
          <>
            <Link2Off className="w-10 h-10 mx-auto mb-3 text-muted-foreground" />
            <p className="font-bold mb-1">Tautan tidak dapat dibuka</p>
            <p className="text-sm text-muted-foreground">{galat}</p>
            <p className="text-xs text-muted-foreground mt-3">
              Tautan tanda tangan punya masa berlaku dan bisa diterbitkan ulang.
              Hubungi penerbit dokumen untuk mendapatkan tautan yang baru.
            </p>
          </>
        ) : (
          <>
            <Loader2 className="w-8 h-8 mx-auto mb-3 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Membuka tautan…</p>
          </>
        )}
      </div>
    </div>
  );
}
