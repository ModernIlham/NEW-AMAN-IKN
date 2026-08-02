import { ArrowRight, Check, Loader2 } from "lucide-react";
import { motion } from "framer-motion";

import { cn } from "@/lib/utils";

/**
 * Tombol dengan titik yang MENGEMBANG memenuhi tombol saat disentuh, lalu
 * memunculkan lapisan kedua berisi label + panah.
 *
 * BEDA dari komponen aslinya: status di sini DIKENDALIKAN pemanggil lewat
 * prop `status`, bukan disimulasikan `setTimeout` di dalam. Versi asli memang
 * peragaan — ia selalu "berhasil" setelah 2 detik. Pada tombol Masuk, status
 * harus mengikuti jawaban server: kalau kata sandi salah, tombol tak boleh
 * memperagakan centang hijau.
 *
 * @param {Object} props
 * @param {string} [props.text] Label keadaan normal.
 * @param {string} [props.loadingText] Label saat proses berjalan.
 * @param {string} [props.successText] Label saat berhasil.
 * @param {"idle"|"loading"|"success"} [props.status]
 * @param {string} [props.className]
 */
export default function InteractiveHoverButton({
  text = "Tombol",
  loadingText = "Memproses...",
  successText = "Berhasil!",
  status = "idle",
  className,
  ...sisa
}) {
  const diam = status === "idle";

  return (
    <motion.button
      className={cn(
        "group relative flex w-full items-center justify-center overflow-hidden rounded-full border border-slate-900 bg-background p-2 px-6 text-sm font-semibold text-foreground",
        "disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-200",
        className,
      )}
      layout
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      aria-busy={status === "loading"}
      {...sisa}
    >
      {/* Lingkaran isian yang mengembang dari posisi titik. Ukurannya RELATIF
          terhadap lebar tombol (`w-[240%]`), bukan kelipatan tetap seperti
          `scale-[40]` di komponen aslinya: kelipatan tetap hanya cukup untuk
          tombol selebar ±160 px, sedangkan tombol Masuk di sini selebar form
          (±450 px) — hasilnya persegi gelap di tengah pil putih, bukan tombol
          terisi penuh. */}
      <span
        className={cn(
          "pointer-events-none absolute left-6 top-1/2 aspect-square w-[240%] -translate-x-1/2 -translate-y-1/2 scale-0 rounded-full bg-slate-900 transition-transform duration-500 group-hover:scale-100 dark:bg-slate-200",
          !diam && "scale-100",
        )}
        aria-hidden="true"
      />
      <span className="flex items-center gap-2">
        {/* Titik kecil keadaan diam — benih visual isian di atas. */}
        <span
          className="h-2 w-2 rounded-full bg-slate-900 dark:bg-slate-200"
          aria-hidden="true"
        />
        {/* Teks ini KEMBAR dengan yang di lapisan kedua — hanya bedanya yang
            satu tergeser keluar saat disentuh. Disembunyikan dari pembaca layar
            supaya nama tombolnya tidak terbaca dua kali; lapisan kedualah yang
            menjadi nama sebenarnya karena ia juga menyuarakan status. */}
        <span
          aria-hidden="true"
          className={cn(
            "inline-block transition-all duration-500 group-hover:translate-x-20 group-hover:opacity-0",
            !diam && "translate-x-20 opacity-0",
          )}
        >
          {text}
        </span>
        {/* Lapisan kedua: muncul setelah titik menutupi tombol. `pointer-events-none`
            wajib — tanpa itu lapisan ini menadah klik dan tombolnya terasa mati
            justru saat kursor berada di atasnya. */}
        <span
          className={cn(
            "pointer-events-none absolute left-0 top-0 z-10 flex h-full w-full -translate-x-16 items-center justify-center gap-2 text-background opacity-0 transition-all duration-500 group-hover:translate-x-0 group-hover:opacity-100",
            !diam && "translate-x-0 opacity-100",
          )}
        >
          {status === "loading" ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>{loadingText}</span>
            </>
          ) : status === "success" ? (
            <>
              <Check className="h-4 w-4" />
              <span>{successText}</span>
            </>
          ) : (
            <>
              <span>{text}</span>
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </span>
      </span>
    </motion.button>
  );
}
