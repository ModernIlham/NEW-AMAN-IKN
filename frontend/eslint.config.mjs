// Konfigurasi eslint flat (eslint 9) — fokus pada aturan react-hooks yang
// menangkap bug nyata (hook dipanggil kondisional, dependency effect kurang).
// `rules-of-hooks` = error (menggagalkan `yarn lint` & CI);
// `exhaustive-deps` = warn (ditampilkan tapi tidak menggagalkan).
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
    },
  },
];
