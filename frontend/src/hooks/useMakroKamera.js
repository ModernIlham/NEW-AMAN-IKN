import { useCallback, useEffect, useRef, useState } from "react";
import { bacaFokus, cariFokusMakro, deteksiMakro, pembacaKetajaman, terapkanFokus } from "../lib/makroKamera";

export function useMakroKamera(track, videoRef, dijeda) {
  const [status, setStatus] = useState("mati");
  const [pesan, setPesan] = useState("");
  const operasi = useRef(null);
  const pemulihan = useRef({ track: null, selesai: Promise.resolve() });
  const urutan = useRef(0);
  const kemampuan = deteksiMakro(track);
  const batalkan = useCallback(() => {
    const op = operasi.current;
    if (!op) return;
    operasi.current = null; op.batal = true;
    // Tunggu applyConstraints yang masih terbang sebelum memulihkan fokus.
    // Track lama tidak pernah diganti dengan track baru saat pemulihan.
    const selesai = op.selesai.finally(async () => {
      if (op.track.readyState === "live") await terapkanFokus(op.track, op.awal).catch(() => {});
    });
    pemulihan.current = { track: op.track, selesai };
    return selesai;
  }, []);
  const hentikan = useCallback(() => { urutan.current++; batalkan(); }, [batalkan]);
  useEffect(() => {
    urutan.current++; setStatus("mati"); setPesan("");
    return hentikan;
  }, [track, dijeda, hentikan]);

  const toggle = useCallback(async () => {
    const tiket = ++urutan.current;
    if (operasi.current) {
      setStatus("memulihkan");
      await batalkan();
      if (tiket === urutan.current) { setStatus("mati"); setPesan(""); }
      return;
    }
    if (dijeda || deteksiMakro(track).jenis === "none") return;
    setStatus("memulihkan");
    if (pemulihan.current.track === track) await pemulihan.current.selesai;
    if (tiket !== urutan.current) return;
    const op = { track, awal: bacaFokus(track), batal: false, selesai: Promise.resolve() };
    operasi.current = op; setStatus("mencari"); setPesan("Tahan kamera tetap diam; arahkan detail ke tengah.");
    op.selesai = (async () => {
      try {
        const jenis = await cariFokusMakro(track, pembacaKetajaman(videoRef.current), () => !op.batal);
        if (op.batal) return;
        setStatus("aktif");
        setPesan(jenis === "manual" ? "Fokus detail terkunci pada kamera ini. Ulangi bantuan fokus jika jarak berubah." : "Bantuan fokus otomatis aktif pada kamera ini. Dekatkan perlahan sesuai kemampuan lensa.");
      } catch (err) {
        if (op.batal) return;
        await terapkanFokus(track, op.awal).catch(() => {});
        if (!op.batal) { operasi.current = null; setStatus("mati"); setPesan(err.message); }
      }
    })();
    await op.selesai;
  }, [track, videoRef, dijeda, batalkan]);
  return { status, pesan, kemampuan, toggle, sibuk: status === "mencari" || status === "memulihkan" };
}
