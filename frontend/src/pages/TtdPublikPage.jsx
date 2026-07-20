import React, { useEffect, useMemo, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  BadgeCheck, CircleAlert, Clock, FileSignature, Loader2, PenTool,
  ShieldCheck, Users,
} from "lucide-react";
import SignatureCapture from "@/components/ttd/SignatureCapture";
import AturPosisiTtd from "@/components/ttd/AturPosisiTtd";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * TtdPublikPage — halaman PUBLIK (tanpa login) untuk dua alur:
 *  - /ttd/:id?token=...        → penanda tangan tamu menandatangani via link
 *  - /ttd/verifikasi/:id       → verifikasi keabsahan e-sign (dibuka dari QR)
 *
 * Dirender langsung dari App.js SEBELUM gate auth (pathname /ttd/...), jadi
 * link yang dibagikan bekerja untuk siapa pun tanpa akun.
 */

function fmtWaktu(iso) {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("id-ID", {
      day: "2-digit", month: "long", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

function StatusPill({ status }) {
  const map = {
    ditandatangani: { cls: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400", label: "Ditandatangani", Icon: BadgeCheck },
    aktif: { cls: "bg-blue-500/15 text-blue-600 dark:text-blue-400", label: "Giliran menandatangani", Icon: PenTool },
    menunggu: { cls: "bg-amber-500/15 text-amber-600 dark:text-amber-400", label: "Menunggu giliran", Icon: Clock },
  };
  const m = map[status] || { cls: "bg-muted text-muted-foreground", label: status || "-", Icon: Clock };
  const I = m.Icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${m.cls}`}>
      <I className="w-3 h-3" />{m.label}
    </span>
  );
}

function Cangkang({ children }) {
  return (
    <div className="min-h-screen bg-background text-foreground flex items-start sm:items-center justify-center p-3 sm:p-6">
      <div className="w-full max-w-xl md:max-w-2xl">
        <div className="flex items-center gap-2.5 mb-4 justify-center">
          <span className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center">
            <FileSignature className="w-5 h-5 text-white" />
          </span>
          <div className="text-left">
            <p className="font-extrabold text-base leading-tight">AMAN — Tanda Tangan Elektronik</p>
            <p className="text-[11px] text-muted-foreground leading-tight">Aplikasi Manajemen Aset &amp; BMN</p>
          </div>
        </div>
        {children}
        <p className="text-center text-[11px] text-muted-foreground mt-4">
          Dokumen ditandatangani secara elektronik — tercatat dengan jejak audit &amp; kode verifikasi.
        </p>
      </div>
    </div>
  );
}

function Kartu({ children }) {
  return (
    <div className="rounded-2xl border border-border bg-card shadow-sm p-4 sm:p-5 space-y-4">
      {children}
    </div>
  );
}

// ── Alur verifikasi (QR) ────────────────────────────────────────────────────
function Verifikasi({ id }) {
  const [data, setData] = useState(null);
  const [galat, setGalat] = useState("");
  useEffect(() => {
    axios.get(`${API}/ttd/verifikasi/${id}`)
      .then((r) => setData(r.data))
      .catch((e) => setGalat(e?.response?.data?.detail || "Dokumen tidak ditemukan"));
  }, [id]);

  if (galat) {
    return (
      <Kartu>
        <div className="text-center py-6 space-y-2">
          <CircleAlert className="w-10 h-10 text-red-500 mx-auto" />
          <p className="font-bold">Verifikasi gagal</p>
          <p className="text-sm text-muted-foreground">{galat}</p>
        </div>
      </Kartu>
    );
  }
  if (!data) {
    return <Kartu><div className="py-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" /></div></Kartu>;
  }
  const selesai = data.status === "selesai";
  return (
    <Kartu>
      <div className="text-center space-y-1.5">
        <ShieldCheck className={`w-12 h-12 mx-auto ${selesai ? "text-emerald-500" : "text-amber-500"}`} />
        <p className="font-extrabold text-lg" data-testid="verif-judul">{data.judul}</p>
        <p className="text-xs text-muted-foreground">
          Dibuat {fmtWaktu(data.dibuat)} · Status:{" "}
          <b className={selesai ? "text-emerald-600" : "text-amber-600"}>
            {selesai ? "SEMUA SUDAH MENANDATANGANI" : (data.status || "-").toUpperCase()}
          </b>
        </p>
      </div>
      <div className="space-y-2">
        <p className="text-xs font-bold text-muted-foreground flex items-center gap-1.5">
          <Users className="w-3.5 h-3.5" />Penanda tangan
        </p>
        {(data.penanda_tangan || []).map((s, i) => (
          <div key={i} className="flex items-center justify-between gap-2 rounded-xl border border-border p-2.5">
            <div className="min-w-0">
              <p className="text-sm font-semibold truncate">{s.nama}</p>
              <p className="text-[11px] text-muted-foreground truncate">
                {s.jabatan || "-"}{s.nip ? ` · NIP ${s.nip}` : ""}
                {s.signed_at ? ` · ${fmtWaktu(s.signed_at)}` : ""}
              </p>
            </div>
            <StatusPill status={s.status} />
          </div>
        ))}
      </div>
      <p className="text-[11px] text-muted-foreground leading-relaxed border-t border-border pt-3">{data.catatan}</p>
    </Kartu>
  );
}

// ── Alur tanda tangan (link dibagikan) ──────────────────────────────────────
function TandaTangan({ id, token }) {
  const [info, setInfo] = useState(null);
  const [galat, setGalat] = useState("");        // galat token/permintaan (final)
  const [koneksi, setKoneksi] = useState(false); // galat JARINGAN (bisa coba lagi)
  const [kirim, setKirim] = useState(false);
  const [sukses, setSukses] = useState(false);
  // Alur 2 langkah bila ada dokumen: tangkap ttd → ATUR POSISI di dokumen.
  const [pngSiap, setPngSiap] = useState(null);
  const drafKey = `ttd-draf-${id}-${(token || "").slice(-12)}`;

  const muat = useCallback(() => {
    setKoneksi(false);
    axios.get(`${API}/ttd/tandatangan/${id}`, { params: { token }, timeout: 20000 })
      .then((r) => {
        setInfo(r.data);
        // Perangkat lain sudah meneken? Batalkan langkah posisi yang basi.
        if (r.data?.penanda_tangan?.status === "ditandatangani") setPngSiap(null);
      })
      .catch((e) => {
        if (!e?.response) {
          // Offline/DNS/timeout ≠ link mati — JANGAN dorong pengguna minta
          // terbit ulang (itu justru mematikan link yang masih valid).
          setKoneksi(true);
          return;
        }
        setGalat(e?.response?.data?.detail || "Link tidak valid / kedaluwarsa");
      });
  }, [id, token]);
  useEffect(() => { muat(); }, [muat]);

  const kirimTtd = useCallback(async (png, posisi) => {
    setKirim(true);
    try {
      await axios.post(`${API}/ttd/tandatangan/${id}/kirim`,
        { png_base64: png, posisi: posisi || null },
        { params: { token }, timeout: 60000 });
      setSukses(true);
      setPngSiap(null);
      try { sessionStorage.removeItem(drafKey); } catch { /* noop */ }
      toast.success("Tanda tangan berhasil dikirim");
    } catch (e) {
      if (e?.response?.status === 409) {
        // Bisa jadi submit SEBELUMNYA sudah tercatat tetapi responsnya hilang
        // di jaringan — muat ulang status agar halaman menunjukkan keadaan
        // sebenarnya, bukan galat menyesatkan.
        toast.info("Memeriksa ulang status tanda tangan…");
        muat();
      } else if (!e?.response) {
        toast.error("Koneksi terputus saat mengirim — tanda tangan Anda MASIH ADA, coba kirim lagi");
      } else {
        toast.error(e?.response?.data?.detail || "Gagal mengirim tanda tangan");
      }
    } finally {
      setKirim(false);
    }
  }, [id, token, muat, drafKey]);

  // Jangan biarkan tab tertutup diam-diam saat ttd sudah digambar tapi belum
  // terkirim (langkah atur posisi).
  useEffect(() => {
    if (!pngSiap || sukses) return;
    const tahan = (e) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", tahan);
    return () => window.removeEventListener("beforeunload", tahan);
  }, [pngSiap, sukses]);

  if (galat) {
    return (
      <Kartu>
        <div className="text-center py-6 space-y-2">
          <CircleAlert className="w-10 h-10 text-red-500 mx-auto" />
          <p className="font-bold">Link tidak dapat dibuka</p>
          <p className="text-sm text-muted-foreground" data-testid="ttd-galat">{galat}</p>
          <p className="text-[11px] text-muted-foreground">
            Minta link baru kepada pembuat dokumen bila link kedaluwarsa (masa berlaku 14 hari).
          </p>
        </div>
      </Kartu>
    );
  }
  if (koneksi) {
    return (
      <Kartu>
        <div className="text-center py-6 space-y-3">
          <CircleAlert className="w-10 h-10 text-amber-500 mx-auto" />
          <p className="font-bold">Koneksi bermasalah</p>
          <p className="text-sm text-muted-foreground">
            Halaman tidak dapat dimuat — periksa jaringan Anda. Link Anda kemungkinan besar MASIH BERLAKU.
          </p>
          <Button variant="outline" size="sm" className="h-9 text-xs" onClick={muat} data-testid="ttd-coba-lagi">
            Coba lagi
          </Button>
        </div>
      </Kartu>
    );
  }
  if (!info) {
    return <Kartu><div className="py-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" /></div></Kartu>;
  }
  if (sukses) {
    return (
      <Kartu>
        <div className="text-center py-6 space-y-2.5">
          <BadgeCheck className="w-14 h-14 text-emerald-500 mx-auto" />
          <p className="font-extrabold text-lg" data-testid="ttd-sukses">Terima kasih, {info.penanda_tangan?.nama}!</p>
          <p className="text-sm text-muted-foreground">
            Tanda tangan Anda untuk <b>{info.judul}</b> sudah tercatat dengan aman.
          </p>
          <Button variant="outline" size="sm" className="h-9 text-xs"
            onClick={() => { window.location.href = `/ttd/verifikasi/${id}`; }}>
            <ShieldCheck className="w-3.5 h-3.5 mr-1.5" />Lihat status dokumen
          </Button>
        </div>
      </Kartu>
    );
  }

  const sg = info.penanda_tangan || {};
  const bisaAturPosisi = info.ada_dokumen && (info.jumlah_halaman || 0) >= 1;

  // Langkah 2: atur letak & ukuran pembubuhan pada dokumen.
  if (pngSiap) {
    return (
      <Kartu>
        <div className="space-y-1">
          <p className="text-[11px] font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wide">Atur pembubuhan</p>
          <p className="font-extrabold text-base sm:text-lg leading-snug">{info.judul}</p>
        </div>
        <AturPosisiTtd
          srId={id}
          token={token}
          jumlahHalaman={info.jumlah_halaman || 1}
          pngTtd={pngSiap}
          mengirim={kirim}
          onBatal={() => setPngSiap(null)}
          onKirim={(posisi) => kirimTtd(pngSiap, posisi)}
        />
      </Kartu>
    );
  }

  return (
    <Kartu>
      <div className="space-y-1">
        <p className="text-[11px] font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wide">Permintaan tanda tangan</p>
        <p className="font-extrabold text-base sm:text-lg leading-snug" data-testid="ttd-judul">{info.judul}</p>
        <p className="text-xs text-muted-foreground">
          Mode {info.mode === "berurutan" ? "berurutan (sesuai giliran)" : "paralel"} · Status dokumen: {info.status_dokumen}
        </p>
      </div>
      <div className="rounded-xl border border-border p-3 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-bold truncate" title={sg.nama}>{sg.nama}</p>
          <p className="text-[11px] sm:text-xs text-muted-foreground truncate" title={`${sg.jabatan || ""}${sg.nip ? ` · NIP ${sg.nip}` : ""}`}>
            {sg.jabatan || "Penanda tangan"}{sg.nip ? ` · NIP ${sg.nip}` : ""}
          </p>
        </div>
        <StatusPill status={sg.status} />
      </div>
      {info.ada_dokumen && (
        <Button variant="outline" size="sm" className="h-auto py-2 text-xs w-full whitespace-normal"
          onClick={() => window.open(`${API}/ttd/tandatangan/${id}/dokumen?token=${encodeURIComponent(token)}`, "_blank", "noopener")}
          data-testid="ttd-lihat-dokumen">
          <ShieldCheck className="w-3.5 h-3.5 mr-1.5 flex-shrink-0" />
          <span className="text-left break-words min-w-0">Baca dokumen yang akan ditandatangani{info.dok_nama ? ` — ${info.dok_nama}` : ""}</span>
        </Button>
      )}
      {info.boleh_ttd ? (
        <>
          <p className="text-xs text-muted-foreground">
            Bubuhkan tanda tangan Anda di bawah — <b>gambar langsung</b> di layar (sentuh/mouse)
            atau <b>unggah foto</b> tanda tangan di kertas (background otomatis dihapus).
            {bisaAturPosisi ? " Setelah itu Anda dapat MENGATUR LETAK & UKURAN tanda tangan di dokumen." : ""}
          </p>
          <SignatureCapture
            onSave={(png) => { if (bisaAturPosisi) setPngSiap(png); else kirimTtd(png, null); }}
            saving={kirim}
            tokenQuery={token}
            drafKey={drafKey}
            labelSimpan={bisaAturPosisi ? "Lanjut Atur Posisi" : "Simpan Tanda Tangan"}
          />
        </>
      ) : (
        <div className="rounded-xl bg-muted p-3 text-sm text-muted-foreground flex items-start gap-2">
          <Clock className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>{info.alasan || "Belum dapat menandatangani saat ini."}</span>
        </div>
      )}
    </Kartu>
  );
}

export default function TtdPublikPage() {
  const { mode, id, token } = useMemo(() => {
    const path = window.location.pathname;
    const verif = path.match(/^\/ttd\/verifikasi\/([\w-]+)/);
    if (verif) return { mode: "verifikasi", id: verif[1], token: "" };
    const sign = path.match(/^\/ttd\/([\w-]+)/);
    const q = new URLSearchParams(window.location.search);
    return { mode: "sign", id: sign ? sign[1] : "", token: q.get("token") || "" };
  }, []);

  if (!id) {
    return (
      <Cangkang>
        <Kartu>
          <div className="text-center py-6 space-y-2">
            <CircleAlert className="w-10 h-10 text-red-500 mx-auto" />
            <p className="font-bold">Alamat tidak dikenali</p>
            <p className="text-sm text-muted-foreground">Periksa kembali link yang Anda terima.</p>
          </div>
        </Kartu>
      </Cangkang>
    );
  }
  return (
    <Cangkang>
      {mode === "verifikasi" ? <Verifikasi id={id} /> : <TandaTangan id={id} token={token} />}
    </Cangkang>
  );
}
