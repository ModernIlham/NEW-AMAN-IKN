import React, { useEffect, useRef } from "react";
import { Pencil, RotateCcw } from "lucide-react";

/**
 * Kotak "Perkiraan nomor yang akan terbit" yang BISA DISUNTING.
 *
 * Permintaan pemilik: *"setiap contoh booking perkiraan nomornya bisa diedit
 * dan di tambahkan unsur baru sesuai keinginan. ibaratnya menulis nomer manual
 * kurang lebihnya jadinya seperti dimodifikasi."*
 *
 * Satu komponen untuk KEDUA dialog booking — Registrasi Persuratan dan tombol
 * Booking Nomor lintas modul. Keduanya menampilkan kotak yang sama dan
 * mengirim ke endpoint yang sama; menulisnya dua kali berarti dua tempat yang
 * harus diingat setiap kali kotak ini berubah.
 *
 * YANG DISUNTING HANYA TULISANNYA. Nomor agenda tetap dikunci counter atomik
 * di server, apa pun yang diketik di sini. Itu sebabnya kotak ini menyebutkan
 * kalimat itu terang-terangan begitu operator mulai mengetik: nomor yang
 * ditulis tangan tidak menahan, memundurkan, atau melompati deret.
 *
 * Props:
 * - nomor: perkiraan dari server (string)
 * - nilai: teks yang SEDANG disunting; "" berarti belum disunting
 * - onChange(v): dipanggil dengan teks baru ("" = kembali ke otomatis)
 * - unsur: potongan tulisan tetap milik satker, disisipkan di posisi kursor
 * - keterangan: node kecil di bawah nomor (asal klasifikasi dsb.)
 */

/**
 * Sisipkan `unsur` ke `teks` pada rentang [mulai, akhir) — persis perilaku
 * mengetik: seleksi yang ada tergantikan, dan kursor berhenti di belakang
 * yang baru disisipkan.
 *
 * MURNI, dan dipisah dari komponennya karena inilah bagian yang mudah salah:
 * posisi kursor di luar jangkauan (input baru dirender, belum pernah difokus)
 * harus jatuh ke akhir teks, bukan ke posisi 0 — menyisipkan di depan nomor
 * adalah kebalikan dari yang diinginkan orang yang menekan chip.
 */
export function sisipUnsur(teks, unsur, mulai, akhir) {
  const t = String(teks ?? "");
  const u = String(unsur ?? "");
  const sah = (n) => (Number.isInteger(n) && n >= 0 && n <= t.length ? n : t.length);
  const a = sah(mulai);
  const b = Math.max(a, sah(akhir));
  return { teks: t.slice(0, a) + u + t.slice(b), kursor: a + u.length };
}

export default function NomorSuntingan({
  nomor = "", nilai = "", onChange, unsur = [], keterangan = null,
  judul = "Perkiraan nomor yang akan terbit:", testid = "pratinjau",
}) {
  const ref = useRef(null);
  const menyunting = String(nilai || "") !== "";

  // BENIH: nomor perkiraan yang terakhir DITUANGKAN ke kotak isian. Selama isi
  // kotak masih sama persis dengan benihnya, berarti operator belum benar-benar
  // mengetik apa pun — dan kotaknya harus IKUT perkiraan terbaru.
  //
  // Laporan pemilik: *"pada perkiraan nomor, nomernya selalu 003, begitu pun
  // yang backdate — jangan buat statis."* Memang: sekali tombol "Ubah nomor"
  // ditekan, kotaknya membeku pada angka saat itu. Deret agenda terus maju,
  // tanggal surat berganti, sisipan dicentang — semuanya mengubah nomor yang
  // AKAN terbit, sementara kotak itu tetap menunjukkan yang lama. Dan yang
  // lama itulah yang terkirim: dibooking sebagai "nomor tulisan tangan" pada
  // angka yang sudah kedaluwarsa.
  const benih = useRef("");
  useEffect(() => {
    if (!menyunting) { benih.current = ""; return; }
    if (nilai === benih.current && nomor && nomor !== nilai) {
      benih.current = nomor;
      onChange?.(nomor);
    }
  }, [nomor, nilai, menyunting, onChange]);

  const sisip = (u) => {
    const el = ref.current;
    const { teks, kursor } = sisipUnsur(
      nilai, u, el?.selectionStart, el?.selectionEnd);
    onChange?.(teks);
    // Kursor dikembalikan SETELAH React menulis nilai barunya; tanpa ini
    // kursor melompat ke ujung dan chip kedua menyisip di tempat yang salah.
    requestAnimationFrame(() => {
      if (!ref.current) return;
      ref.current.focus();
      ref.current.setSelectionRange(kursor, kursor);
    });
  };

  return (
    <div className="rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-3 py-2"
      data-testid={testid}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10px] text-muted-foreground">{judul}</p>
        {menyunting ? (
          <button type="button" onClick={() => onChange?.("")}
            className="text-[10px] inline-flex items-center gap-1 text-muted-foreground hover:text-foreground flex-shrink-0 min-w-0 min-h-0"
            data-testid={`${testid}-otomatis`}>
            <RotateCcw className="w-3 h-3" />Kembali otomatis
          </button>
        ) : (
          <button type="button"
            onClick={() => { benih.current = nomor; onChange?.(nomor); }}
            className="text-[10px] inline-flex items-center gap-1 text-cyan-700 dark:text-cyan-400 hover:underline flex-shrink-0 min-w-0 min-h-0"
            data-testid={`${testid}-ubah`}>
            <Pencil className="w-3 h-3" />Ubah nomor
          </button>
        )}
      </div>
      {menyunting ? (
        <>
          <input
            ref={ref} value={nilai} onChange={(e) => onChange?.(e.target.value)}
            className="w-full mt-1 h-9 rounded-md border border-input bg-background px-2 font-mono text-sm font-bold text-cyan-700 dark:text-cyan-400"
            data-testid={`${testid}-input`} />
          {unsur.length > 0 && (
            <div className="flex flex-wrap items-center gap-1 mt-1.5"
              data-testid={`${testid}-unsur`}>
              <span className="text-[10px] text-muted-foreground">Sisipkan:</span>
              {unsur.map((u) => (
                <button key={u} type="button"
                  // Fokus DIPERTAHANKAN di kotak nomor: tanpa ini tombol
                  // mencuri fokus lebih dulu, posisi kursor hilang, dan
                  // unsurnya selalu mendarat di ujung.
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => sisip(u)}
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-border bg-background hover:bg-muted min-w-0 min-h-0"
                  data-testid={`${testid}-unsur-${u}`}>
                  {u}
                </button>
              ))}
            </div>
          )}
          <p className="text-[10px] text-muted-foreground mt-1"
            data-testid={`${testid}-catatan-manual`}>
            Nomor ditulis manual. Nomor agenda tetap berjalan otomatis — tulisan
            ini tidak menggeser deret. Otomatisnya:{" "}
            <span className="font-mono">{nomor}</span> (tetap tersimpan sebagai
            pembanding).
          </p>
        </>
      ) : (
        <p className="font-mono text-sm font-bold text-cyan-700 dark:text-cyan-400 break-all"
          data-testid={`${testid}-nomor`}>{nomor}</p>
      )}
      {keterangan}
    </div>
  );
}
