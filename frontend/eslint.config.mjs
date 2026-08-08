// Konfigurasi eslint flat (eslint 9) — memuat aturan yang menangkap bug NYATA,
// bukan sekadar gaya penulisan. Tiap aturan di bawah dipasang karena kelasnya
// pernah benar-benar menjatuhkan halaman di lapangan.
import globals from "globals";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";

export default [
  { ignores: ["build/**", "node_modules/**", "public/**"] },
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, process: "readonly" },
    },
    plugins: { react, "react-hooks": reactHooks },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      // Komponen JSX yang TIDAK ADA definisinya. Webpack meloloskannya —
      // `<Anu/>` hanya menjadi pemanggilan fungsi, dan baru meledak di
      // PERAMBAN sebagai layar kosong. Halaman peta kolaborasi pernah tayang
      // rusak persis karena ini: lint bersih, build sukses, halaman gagal
      // ditampilkan. Aturan ini membuatnya gagal di CI, bukan di lapangan.
      "react/jsx-no-undef": "error",

      // Saudara kandungnya untuk kode NON-JSX. `jsx-no-undef` hanya menjaga
      // `<Komponen/>`; sebuah IDENTIFIER biasa yang tak pernah dideklarasikan
      // lolos tanpa suara sampai barisnya benar-benar dieksekusi di peramban.
      //
      // Bukan hipotesis: saat aturan ini pertama dinyalakan, ia langsung
      // menemukan `kirimGeserRef` di PetaKolaborasiPage — dipakai satu kali di
      // handler `dragend`, tak pernah dideklarasikan di mana pun. Akibatnya
      // fitur "tamu menggeser marker" mati tepat di langkah terakhir: tamu
      // mengetikkan namanya, lalu ReferenceError, dan usulannya tak pernah
      // terkirim. Lint bersih, build sukses, uji hijau — semua diam.
      "no-undef": "error",

      // TDZ: sebuah `const`/`let` yang DIPAKAI sebelum barisnya dieksekusi.
      // Halaman Peta Aset pernah tayang sebagai layar kosong karena ini
      // ("Cannot access '<x>' before initialization"). `functions: false`
      // sengaja dilonggarkan — deklarasi fungsi ter-hoist penuh dan memakainya
      // lebih awal adalah idiom React yang sah.
      "no-use-before-define": ["error", { functions: false, classes: false, variables: true }],
    },
  },
  {
    // Berkas uji berjalan di Jest, bukan di peramban: `describe`, `test`,
    // `expect`, `jest`, plus `require`/`module`/`__dirname` gaya CommonJS.
    // Tanpa blok ini `no-undef` akan menyalak 2.300+ kali pada global yang
    // memang disediakan runtime-nya — dan penjaga yang menyalak palsu sebanyak
    // itu pasti dimatikan orang, bukan dipatuhi.
    files: ["src/**/*.test.{js,jsx}", "src/**/__tests__/**/*.{js,jsx}", "src/setupTests.js"],
    languageOptions: {
      globals: { ...globals.jest, ...globals.node },
    },
  },
];
