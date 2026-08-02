import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

/**
 * INTI konfirmasi kata sandi ber-panduan — versi yang bisa DISEMATKAN ke dalam
 * form yang sudah ada (tanpa pembungkus halaman penuh).
 *
 * Kotak titik menandai TIAP karakter ketikan ulang — hijau bila cocok, merah
 * bila meleset — dan kotak bergetar saat pengguna mengetik melewati panjang
 * kata sandi acuan. Warna memakai token tema repo sehingga ikut mode gelap.
 *
 * @param {Object} props
 * @param {string} props.password Kata sandi acuan yang harus diketik ulang.
 * @param {boolean} [props.tampilkanSandi] Tampilkan kata sandi acuan apa adanya
 *   di atas kotak. DEFAULT `false`: memampangkan kata sandi di layar berisiko
 *   terlihat orang lain / terekam layar. Penanda per-karakter tetap bekerja
 *   penuh meski sandinya disembunyikan.
 * @param {string} [props.placeholder] Teks bantu kolom isian.
 * @param {(cocok: boolean) => void} [props.onMatchChange] Dipanggil saat status
 *   kecocokan berubah — biasanya untuk mengaktifkan tombol simpan. AMAN
 *   menerima fungsi inline (lihat catatan ref di bawah).
 * @param {string} [props.testId] data-testid kolom isian.
 */
export function AssistedPasswordConfirmationField({
  password,
  tampilkanSandi = false,
  placeholder = "Ulangi kata sandi baru",
  onMatchChange,
  testId = "assisted-password-confirm",
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
      // melihat seluruh huruf "hijau" tetapi status tetap tidak cocok selamanya.
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

  // Kata sandi acuan MEMENDEK (pengguna menyunting kolom di atasnya) —
  // ketikan ulang yang kini lebih panjang dari acuannya harus ikut dipangkas,
  // kalau tidak jumlah kotak titik dan isi kolom tak lagi sinkron.
  useEffect(() => {
    setConfirmPassword((c) => (c.length > password.length
      ? c.slice(0, password.length) : c));
  }, [password]);

  // Wajib ada sandi untuk dicocokkan: tanpa syarat panjang, keadaan awal
  // (acuan "" dan ketikan "") bernilai `"" === ""` alias COCOK — tombol simpan
  // pemanggil akan menyala sebelum pengguna mengetik apa pun.
  const passwordsMatch = password.length > 0 && password === confirmPassword;

  // Callback disimpan di ref, BUKAN di deps efek: pemanggil lazim mengoper
  // fungsi inline (identitas baru tiap render). Bila fungsi itu masuk deps,
  // efek berjalan pada SETIAP render — dan bila induk menanggapinya dengan
  // setState objek baru, jadilah render tak berujung.
  const onMatchRef = useRef(onMatchChange);
  useEffect(() => {
    onMatchRef.current = onMatchChange;
  });
  useEffect(() => {
    if (onMatchRef.current) onMatchRef.current(passwordsMatch);
  }, [passwordsMatch]);

  const getLetterStatus = (letter, index) => {
    if (!confirmPassword[index]) return "";
    return confirmPassword[index] === letter
      ? "bg-green-500/25"
      : "bg-red-500/25";
  };

  const bounceAnimation = {
    x: shake ? [-10, 10, -10, 10, 0] : 0,
    transition: { duration: 0.5 },
  };

  const matchAnimation = {
    scale: passwordsMatch ? [1, 1.05, 1] : 1,
    transition: { duration: 0.3 },
  };

  const borderAnimation = {
    // Hijau saat cocok; selain itu kembalikan ke warna garis tema (token HSL
    // shadcn perlu dibungkus hsl() agar sah sebagai nilai warna CSS).
    borderColor: passwordsMatch ? "#10B981" : "hsl(var(--border))",
    transition: { duration: 0.3 },
  };

  return (
    <div className="relative flex w-full flex-col items-start justify-center">
      {tampilkanSandi && (
        <span className="text-sm text-foreground font-semibold">
          → {password}
        </span>
      )}
      <motion.div
        className="mb-2 mt-1 h-[52px] w-full rounded-xl border-2 border-border bg-card px-2 py-2"
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
                <span className="size-[5px] rounded-full bg-foreground"></span>
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
          className="h-full w-full rounded-xl border-2 border-border bg-background px-3.5 py-3 tracking-[0.4em] text-foreground outline-none placeholder:tracking-normal placeholder:text-muted-foreground focus:border-ring"
          type="password"
          placeholder={placeholder}
          aria-label={placeholder}
          autoComplete="new-password"
          value={confirmPassword}
          onChange={handleConfirmPasswordChange}
          animate={borderAnimation}
          data-testid={testId}
        />
      </motion.div>
    </div>
  );
}

/**
 * Pembungkus HALAMAN PENUH di atas `AssistedPasswordConfirmationField` —
 * bentuk asli komponen (kartu di tengah layar), berguna untuk pratinjau/demo.
 * Untuk menyematkannya ke form yang sudah ada, pakai `…Field` langsung.
 *
 * @param {Object} props
 * @param {string} props.password
 * @param {boolean} [props.tampilkanSandi] Default `true` di sini karena bentuk
 *   ini memang dipakai untuk memperagakan cara kerjanya.
 */
export function AssistedPasswordConfirmation({
  password,
  tampilkanSandi = true,
  ...sisa
}) {
  return (
    <main className="relative flex min-h-screen w-full items-start justify-center px-4 py-10 md:items-center">
      <div className="z-10 flex w-full flex-col items-center">
        <div className="mx-auto flex h-full w-full max-w-lg flex-col items-center justify-center gap-8 bg-card p-16 rounded-2xl">
          <AssistedPasswordConfirmationField
            password={password}
            tampilkanSandi={tampilkanSandi}
            {...sisa}
          />
        </div>
      </div>
    </main>
  );
}
