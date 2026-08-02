import { motion } from "framer-motion";
import { useEffect, useState } from "react";

/**
 * Konfirmasi kata sandi ber-panduan: kotak titik di atas menandai TIAP karakter
 * yang sudah diketik ulang — hijau bila cocok, merah bila meleset — dan kotak
 * bergetar saat pengguna mencoba mengetik melewati panjang kata sandi.
 *
 * CATATAN KEAMANAN (disengaja oleh pemanggil): komponen ini MENAMPILKAN kata
 * sandi apa adanya di layar dan memberi umpan balik per-karakter. Pakai hanya
 * pada layar di mana pengguna baru saja mengetik kata sandinya sendiri (mis.
 * pendaftaran / ganti kata sandi), JANGAN pada layar masuk atau di tempat yang
 * bisa terekam layar/terlihat orang lain.
 *
 * @param {Object} props
 * @param {string} props.password    Kata sandi acuan yang harus diketik ulang.
 * @param {string} [props.placeholder] Teks bantu kolom isian.
 * @param {(cocok: boolean) => void} [props.onMatchChange] Dipanggil saat status
 *   kecocokan berubah — pemanggil biasanya memakainya untuk mengaktifkan tombol
 *   simpan. Tanpa ini komponen tetap berfungsi (murni visual).
 */
export function AssistedPasswordConfirmation({
  password,
  placeholder = "Konfirmasi Kata Sandi",
  onMatchChange,
}) {
  const [confirmPassword, setConfirmPassword] = useState("");
  const [shake, setShake] = useState(false);

  const handleConfirmPasswordChange = (e) => {
    if (
      confirmPassword.length >= password.length &&
      e.target.value.length > confirmPassword.length
    ) {
      setShake(true);
    } else {
      // Potong ke panjang kata sandi acuan: tanpa ini, TEMPEL (paste) teks yang
      // lebih panjang saat kolom masih kosong lolos begitu saja — karakter
      // lebihnya tak punya kotak titik untuk ditandai, sehingga pengguna
      // melihat semua huruf "hijau" tetapi status tetap tidak cocok selamanya.
      setConfirmPassword(e.target.value.slice(0, password.length));
    }
  };

  useEffect(() => {
    if (shake) {
      const timer = setTimeout(() => setShake(false), 500);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [shake]);

  const getLetterStatus = (letter, index) => {
    if (!confirmPassword[index]) return "";
    return confirmPassword[index] === letter
      ? "bg-green-500/20"
      : "bg-red-500/20";
  };

  const passwordsMatch = password === confirmPassword;

  // Beri tahu pemanggil (mis. untuk mengaktifkan tombol Simpan) — efek terpisah
  // agar render tetap murni dan tidak memanggil setState induk saat render.
  useEffect(() => {
    if (onMatchChange) onMatchChange(passwordsMatch);
  }, [passwordsMatch, onMatchChange]);

  const bounceAnimation = {
    x: shake ? [-10, 10, -10, 10, 0] : 0,
    transition: { duration: 0.5 },
  };

  const matchAnimation = {
    scale: passwordsMatch ? [1, 1.05, 1] : 1,
    transition: { duration: 0.3 },
  };

  const borderAnimation = {
    borderColor: passwordsMatch ? "#10B981" : "",
    transition: { duration: 0.3 },
  };

  return (
    <main className="relative flex min-h-screen w-full items-start justify-center px-4 py-10 md:items-center">
      <div className="z-10 flex w-full flex-col items-center">
        <div className="mx-auto flex h-full w-full max-w-lg flex-col items-center justify-center gap-8 bg-white p-16 rounded-2xl">
          <div className="relative flex w-full flex-col items-start justify-center">
            <span className="text-sm text-gray-900 font-semibold">
              → {password}
            </span>
            <motion.div
              className="mb-3 mt-1 h-[52px] w-full rounded-xl border-2 bg-white px-2 py-2"
              animate={{
                ...bounceAnimation,
                ...matchAnimation,
                ...borderAnimation,
              }}
            >
              <div className="relative h-full w-fit overflow-hidden rounded-lg">
                <div className="z-10 flex h-full items-center justify-center bg-transparent px-0 py-1 tracking-[0.15em]">
                  {password.split("").map((_, index) => (
                    <div
                      key={index}
                      className="flex h-full w-4 shrink-0 items-center justify-center"
                    >
                      <span className="size-[5px] rounded-full bg-black"></span>
                    </div>
                  ))}
                </div>
                <div className="absolute bottom-0 left-0 top-0 z-0 flex h-full w-full items-center justify-start">
                  {password.split("").map((letter, index) => (
                    <motion.div
                      key={index}
                      className={`ease absolute h-full w-4 transition-all duration-300 ${getLetterStatus(
                        letter,
                        index,
                      )}`}
                      style={{
                        left: `${index * 16}px`,
                        scaleX: confirmPassword[index] ? 1 : 0,
                        transformOrigin: "left",
                      }}
                    ></motion.div>
                  ))}
                </div>
              </div>
            </motion.div>

            <motion.div
              className="h-[52px] w-full overflow-hidden rounded-xl"
              animate={matchAnimation}
            >
              <motion.input
                className="h-full w-full rounded-xl border-2 bg-white px-3.5 py-3 tracking-[0.4em] outline-none placeholder:tracking-normal focus:border-slate-900 text-gray-900"
                type="password"
                placeholder={placeholder}
                aria-label={placeholder}
                autoComplete="new-password"
                value={confirmPassword}
                onChange={handleConfirmPasswordChange}
                animate={borderAnimation}
              />
            </motion.div>
          </div>
        </div>
      </div>
    </main>
  );
}
