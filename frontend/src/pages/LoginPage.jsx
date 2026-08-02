import { useState, useRef } from "react";
import { Package, Mail, Lock, ArrowRight, Loader2, Eye, EyeOff, User, ShieldCheck, RotateCcw, Layers, MapPinned, WifiOff, PenLine, Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "@/lib/utils";
import { useTripleClick } from "@/hooks/useTripleClick";
import { AssistedPasswordConfirmationField } from "@/components/ui/assisted-password-confirmation";
import { galatPassword, statusSyaratPassword } from "@/lib/passwordRules";
import { KataBerganti } from "@/components/ui/animated-hero";
import InteractiveHoverButton from "@/components/ui/interactive-hover-button";
import { LiquidEffectAnimation } from "@/components/ui/liquid-effect-animation";

// Kata yang bergantian pada judul panel kiri. Semuanya menyifati hal yang sama
// — pengelolaan BMN — dari sudut berbeda, bukan sekadar sinonim berjajar.
const SIFAT_JUDUL = ["Terpadu", "Terlacak", "Terhubung", "Tepercaya", "Tuntas"];

// Kemampuan yang BENAR-BENAR ada hari ini. Daftar lama masih menyebut "CRUD
// lengkap dengan foto" dan "Import data massal via CSV" — deskripsi aplikasi
// dua tahun lalu, jauh sebelum 16 modul siklus BMN, peta berlapis, e-sign, dan
// isolasi per satuan kerja ada.
const SOROTAN = [
  { Ikon: Layers, teks: "16 modul siklus BMN — perencanaan sampai penghapusan" },
  { Ikon: WifiOff, teks: "Inventarisasi lapangan tetap jalan tanpa sinyal" },
  { Ikon: Building2, teks: "Selaras SIMAN V2 & SAKTI — penyusutan per semester" },
  { Ikon: MapPinned, teks: "Peta aset, denah berlapis, dan pelacakan posisi" },
  { Ikon: PenLine, teks: "Tanda tangan elektronik & BAST resmi ber-QR" },
];

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// OTP Verification Screen
function OTPVerification({ email, debugOtp, onVerified, onBack, onDebugOtp }) {
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const inputsRef = useRef([]);

  const handleChange = (idx, val) => {
    if (val.length > 1) val = val.slice(-1);
    if (val && !/^\d$/.test(val)) return;
    const next = [...otp];
    next[idx] = val;
    setOtp(next);
    if (val && idx < 5) inputsRef.current[idx + 1]?.focus();
  };

  const handleKeyDown = (idx, e) => {
    if (e.key === "Backspace" && !otp[idx] && idx > 0) {
      inputsRef.current[idx - 1]?.focus();
    }
  };

  const handlePaste = (e) => {
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (pasted.length === 6) {
      setOtp(pasted.split(""));
      inputsRef.current[5]?.focus();
      e.preventDefault();
    }
  };

  const handleVerify = async () => {
    const code = otp.join("");
    if (code.length !== 6) { toast.error("Masukkan 6 digit kode OTP"); return; }
    setLoading(true);
    try {
      const res = await axios.post(`${API}/auth/verify-otp`, { email, otp: code });
      // NEW: handle pending_approval flow — user created but inactive, no token issued
      if (res.data?.pending_approval === true || !res.data?.access_token) {
        toast.success(
          res.data?.message ||
            "Pendaftaran berhasil. Menunggu aktivasi admin sebelum dapat login.",
          { duration: 7000 }
        );
        // Bounce back to the login form
        if (typeof onBack === "function") onBack();
        return;
      }
      toast.success("Verifikasi berhasil!");
      onVerified(res.data.user, res.data.access_token);
    } catch (err) {
      toast.error(getApiError(err, "Kode OTP salah"));
    } finally { setLoading(false); }
  };

  const handleResend = async () => {
    setResending(true);
    try {
      const res = await axios.post(`${API}/auth/resend-otp`, { email, otp: "" });
      if (!res.data?.otp_sent && !res.data?.debug_otp) {
        toast.error(res.data?.message || "Email gagal terkirim — hubungi administrator");
        return;
      }
      if (res.data.debug_otp && onDebugOtp) onDebugOtp(res.data.debug_otp);
      toast.success("Kode OTP baru telah dikirim");
      setOtp(["", "", "", "", "", ""]);
    } catch (err) {
      toast.error(getApiError(err, "Gagal kirim ulang OTP"));
    } finally { setResending(false); }
  };

  return (
    <div className="w-full max-w-md space-y-8" data-testid="otp-verification">
      <div className="text-center">
        <div className="mx-auto w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mb-4">
          <ShieldCheck className="w-8 h-8 text-blue-600" />
        </div>
        <h2 className="text-2xl font-bold text-foreground font-['Manrope']">Verifikasi Email</h2>
        <p className="text-muted-foreground mt-2 text-sm">
          Kode OTP telah dikirim ke <span className="font-medium text-foreground">{email}</span>
        </p>
      </div>

      {debugOtp && (
        <div className="bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-700 rounded-lg p-3 text-center" data-testid="debug-otp">
          <p className="text-xs text-amber-600 dark:text-amber-400 mb-1">Kode OTP (debug):</p>
          <p className="text-2xl font-mono font-bold text-amber-800 dark:text-amber-200 tracking-[8px]">{debugOtp}</p>
        </div>
      )}

      <div className="flex justify-center gap-2" onPaste={handlePaste}>
        {otp.map((digit, idx) => (
          <input
            key={idx}
            ref={el => inputsRef.current[idx] = el}
            type="text"
            inputMode="numeric"
            maxLength={1}
            value={digit}
            onChange={e => handleChange(idx, e.target.value)}
            onKeyDown={e => handleKeyDown(idx, e)}
            data-testid={`otp-input-${idx}`}
            className="w-12 h-14 text-center text-xl font-bold border-2 border-border rounded-lg focus:border-ring focus:ring-2 focus:ring-blue-200 outline-none transition-all bg-background text-foreground"
          />
        ))}
      </div>

      <Button
        onClick={handleVerify}
        disabled={loading || otp.join("").length !== 6}
        className="w-full h-11 bg-slate-900 hover:bg-slate-800 text-white font-medium"
        data-testid="verify-otp-btn"
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : (
          <>Verifikasi <ArrowRight className="w-4 h-4 ml-2" /></>
        )}
      </Button>

      <div className="flex items-center justify-between text-sm">
        <button onClick={onBack} className="text-muted-foreground hover:text-foreground flex items-center gap-1" data-testid="back-to-register">
          <ArrowRight className="w-3 h-3 rotate-180" /> Kembali
        </button>
        <button onClick={handleResend} disabled={resending} className="text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1" data-testid="resend-otp-btn">
          {resending ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
          Kirim Ulang
        </button>
      </div>
    </div>
  );
}

// Password strength checker
function PasswordStrength({ password }) {
  // Aturan dari satu sumber bersama (lib/passwordRules) — dipakai form Daftar
  // MAUPUN alur reset OTP, agar syaratnya tak bisa lagi berbeda antar layar.
  const checks = statusSyaratPassword(password);
  const passed = checks.filter(c => c.ok).length;
  if (!password) return null;
  return (
    <div className="space-y-1.5 mt-1.5" data-testid="password-strength">
      <div className="flex gap-1">
        {[1,2,3,4,5].map(i => (
          <div key={i} className={`h-1 flex-1 rounded-full transition-colors ${i <= passed ? (passed <= 2 ? 'bg-red-400' : passed <= 3 ? 'bg-amber-400' : 'bg-emerald-400') : 'bg-muted'}`} />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
        {checks.map((c, i) => (
          <span key={i} className={`text-[10px] flex items-center gap-1 ${c.ok ? 'text-emerald-600' : 'text-muted-foreground'}`}>
            {c.ok ? '✓' : '○'} {c.label}
          </span>
        ))}
      </div>
    </div>
  );
}

// Main Login Page
export default function LoginPage({ onLogin, onShowInfo }) {
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({ username: "", password: "", confirmPassword: "", name: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [otpStep, setOtpStep] = useState(false);
  const [otpEmail, setOtpEmail] = useState("");
  const [debugOtp, setDebugOtp] = useState(null);
  // Alur lupa password: null = tertutup; {email, otp, baru, terkirim, saving}
  const [reset, setReset] = useState(null);
  // Kecocokan ketikan ulang kata sandi baru (alur reset OTP). Disimpan di state
  // TERSENDIRI, bukan di dalam objek `reset`: setter useState identitasnya
  // stabil, jadi aman dioper sebagai callback ke komponen konfirmasi.
  const [resetCocok, setResetCocok] = useState(false);
  // Tombol kirim menampilkan centang "berhasil" SETELAH server menjawab —
  // tidak pernah sebagai tebakan. Sengaja tidak pernah di-reset ke false pada
  // jalur sukses: begitu bernilai true, halaman memang sedang berpindah.
  const [sukses, setSukses] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Registration validations
    if (!isLogin) {
      if (formData.password !== formData.confirmPassword) {
        toast.error("Password tidak sama. Periksa kembali.");
        return;
      }
      const galat = galatPassword(formData.password);
      if (galat) { toast.error(galat); return; }
    }
    setLoading(true);
    try {
      if (isLogin) {
        const res = await axios.post(`${API}/auth/login`, {
          username: formData.username,
          password: formData.password
        });
        toast.success("Login berhasil!");
        setSukses(true);
        onLogin(res.data.user, res.data.access_token, res.data.media_token);
      } else {
        // Registration: request OTP first
        const email = formData.username.trim().toLowerCase();
        const res = await axios.post(`${API}/auth/request-otp`, {
          email,
          password: formData.password,
          name: formData.name
        });
        // Email GAGAL terkirim (mis. layanan email belum dikonfigurasi di
        // server) → tampilkan alasannya sebagai GALAT dan JANGAN masuk
        // langkah isi OTP — sebelumnya pesan gagal tampil sebagai toast
        // sukses dan pengguna menunggu email yang mustahil datang.
        if (!res.data?.otp_sent && !res.data?.debug_otp) {
          toast.error(res.data?.message || "Email gagal terkirim — hubungi administrator");
          return;
        }
        setOtpEmail(email);
        setDebugOtp(res.data.debug_otp || null);
        setSukses(true);
        setOtpStep(true);
        toast.success(res.data.message || "Kode OTP dikirim ke email");
      }
    } catch (err) {
      toast.error(getApiError(err, "Terjadi kesalahan"));
    } finally { setLoading(false); }
  };

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  // Halaman Info/PRD dibuka lewat klik LOGO aplikasi (tanpa tombol Info terpisah)
  // Halaman Info tersembunyi: butuh 3 klik beruntun pada logo
  const activateInfo = useTripleClick(onShowInfo);
  const logoProps = onShowInfo ? {
    role: "button", tabIndex: 0, onClick: activateInfo,
    onKeyDown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activateInfo(); } },
    "aria-label": "Info aplikasi", title: "Info aplikasi",
  } : {};

  return (
    <div className="min-h-screen flex" data-testid="login-page">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-slate-900 login-pattern relative overflow-hidden">
        {/* Permukaan air di belakang tulisan. Kanvas LOKAL — lihat catatan
            panjang di `liquid-effect-animation.jsx` soal kenapa skrip CDN
            versi contohnya tidak dipakai di layar yang menerima kata sandi. */}
        <div className="absolute inset-0 z-0">
          <LiquidEffectAnimation />
        </div>
        {/* `pointer-events-none` supaya sentuhan/kursor menembus ke kanvas dan
            melahirkan riak di seluruh panel; hanya logo yang menadah klik
            (pintu tersembunyi ke halaman Info). */}
        <div className="pointer-events-none relative z-10 flex flex-col justify-between p-12 w-full">
          <div className={`pointer-events-auto flex items-center gap-3 w-fit ${onShowInfo ? "cursor-pointer" : ""}`} data-testid="login-logo" {...logoProps}>
            <div className="w-10 h-10 bg-gradient-to-br from-teal-600 to-teal-700 rounded-lg flex items-center justify-center shadow-elev-2">
              <Package className="w-6 h-6 text-white" />
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-xl font-bold text-white font-['Manrope']">AMAN</span>
              <span className="text-[11px] font-medium text-slate-300">Aplikasi Manajemen Aset Negara</span>
            </div>
          </div>
          <div className="space-y-6 max-w-lg">
            <h1 className="text-4xl xl:text-5xl font-bold text-white leading-tight font-['Manrope']">
              Pengelolaan BMN yang
              {/* Tinggi baris dijaga komponennya sendiri (salinan tak terlihat
                  kata terpanjang), jadi barisnya tak berkedut saat berganti. */}
              <KataBerganti kata={SIFAT_JUDUL} className="text-teal-300" />
            </h1>
            <p className="text-slate-300 text-lg">
              Satu pintu untuk seluruh daur hidup Barang Milik Negara — dari
              rencana kebutuhan, penatausahaan, sampai penghapusan.
            </p>
            <div className="space-y-3 pt-2">
              {SOROTAN.map(({ Ikon, teks }) => (
                <div key={teks} className="flex items-center gap-3 text-slate-300">
                  <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-teal-500/15 ring-1 ring-teal-400/25">
                    <Ikon className="h-3.5 w-3.5 text-teal-300" />
                  </span>
                  <span className="text-sm">{teks}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="text-slate-400 text-sm">&copy; {new Date().getFullYear()} AMAN — Aplikasi Manajemen Aset Negara</div>
        </div>
      </div>

      {/* Right Panel */}
      <div className="flex-1 flex items-center justify-center p-8 bg-card">
        {otpStep ? (
          <OTPVerification
            email={otpEmail}
            debugOtp={debugOtp}
            onVerified={onLogin}
            // `sukses` ikut dibersihkan: tanpa ini, kembali dari layar OTP
            // memampangkan tombol bercentang "OTP terkirim" padahal pengguna
            // justru sedang mengulang dari awal.
            onBack={() => { setOtpStep(false); setDebugOtp(null); setSukses(false); }}
            onDebugOtp={setDebugOtp}
          />
        ) : (
          <div className="w-full max-w-md space-y-8">
            {/* Mobile Logo */}
            <div className={`lg:hidden flex items-center justify-center gap-3 mb-8 ${onShowInfo ? "cursor-pointer" : ""}`} data-testid="login-logo-mobile" {...logoProps}>
              <div className="w-10 h-10 bg-gradient-to-br from-slate-900 to-slate-800 rounded-lg flex items-center justify-center shadow-elev-2">
                <Package className="w-6 h-6 text-white" />
              </div>
              <div className="flex flex-col leading-tight text-left">
                <span className="text-xl font-bold text-foreground font-['Manrope']">AMAN</span>
                <span className="text-[11px] font-medium text-muted-foreground">Aplikasi Manajemen Aset Negara</span>
              </div>
            </div>

            <div className="text-center lg:text-left">
              <h2 className="text-2xl font-bold text-foreground font-['Manrope']">
                {isLogin ? "Selamat Datang" : "Buat Akun Baru"}
              </h2>
              <p className="text-muted-foreground mt-2">
                {isLogin ? "Masuk untuk mengakses sistem inventaris" : "Daftarkan diri Anda untuk mulai menggunakan sistem"}
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5" data-testid="login-form">
              {!isLogin && (
                <div className="space-y-2">
                  <Label htmlFor="name" className="text-foreground font-medium">Nama Lengkap</Label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input id="name" name="name" type="text"
                      placeholder="Tulis Namamu disini"
                      value={formData.name} onChange={handleChange}
                      className="pl-10 h-11 border-border focus:border-ring focus:ring-ring"
                      data-testid="name-input"
                    />
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="username" className="text-foreground font-medium">{isLogin ? "Email atau Username" : "Alamat Email"}</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input id="username" name="username" type={isLogin ? "text" : "email"}
                    placeholder={isLogin ? "Email atau username" : "example@gmail.com"}
                    value={formData.username} onChange={handleChange} required
                    className="pl-10 h-11 border-border focus:border-ring focus:ring-ring"
                    data-testid="username-input"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-foreground font-medium">Password</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input id="password" name="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="********"
                    value={formData.password} onChange={handleChange} required
                    className="pl-10 pr-10 h-11 border-border focus:border-ring focus:ring-ring"
                    data-testid="password-input"
                  />
                  <button type="button" onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-muted-foreground transition-colors"
                    data-testid="toggle-password-visibility">
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {!isLogin && <PasswordStrength password={formData.password} />}
              </div>

              {!isLogin && (
                <div className="space-y-2">
                  <Label htmlFor="confirmPassword" className="text-foreground font-medium">Ulangi Password</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input id="confirmPassword" name="confirmPassword"
                      type={showPassword ? "text" : "password"}
                      placeholder="Ketik ulang password"
                      value={formData.confirmPassword} onChange={handleChange} required
                      className={`pl-10 h-11 border-border focus:border-ring focus:ring-ring ${formData.confirmPassword && formData.password !== formData.confirmPassword ? 'border-red-400 focus:border-red-500 focus:ring-red-200' : formData.confirmPassword && formData.password === formData.confirmPassword ? 'border-emerald-400 focus:border-emerald-500 focus:ring-emerald-200' : ''}`}
                      data-testid="confirm-password-input"
                    />
                  </div>
                  {formData.confirmPassword && formData.password !== formData.confirmPassword && (
                    <p className="text-xs text-red-500" data-testid="password-mismatch-error">Password tidak sama</p>
                  )}
                </div>
              )}

              {/* Status DIKENDALIKAN dari sini, bukan disimulasikan di dalam
                  tombol: "Berhasil" hanya muncul setelah server benar-benar
                  menjawab, dan itu jendela nyata — `onLogin` masih harus
                  memuat potongan dasbor sebelum halaman berganti. */}
              <InteractiveHoverButton
                type="submit"
                disabled={loading}
                status={sukses ? "success" : loading ? "loading" : "idle"}
                text={isLogin ? "Masuk" : "Daftar"}
                loadingText={isLogin ? "Memeriksa..." : "Mengirim OTP..."}
                successText={isLogin ? "Berhasil masuk" : "OTP terkirim"}
                className="h-11"
                data-testid="submit-button"
              />
            </form>

            {isLogin && !reset && (
              <div className="text-center text-sm -mt-2">
                <button type="button" onClick={() => setReset({ email: formData.username.includes("@") ? formData.username : "", otp: "", baru: "", terkirim: false, saving: false })}
                  className="text-blue-600 hover:text-blue-700 font-medium" data-testid="lupa-password">
                  Lupa password?
                </button>
              </div>
            )}
            {reset && (
              <div className="rounded-xl border border-border bg-muted/40 p-3 space-y-2" data-testid="panel-reset">
                <p className="text-xs font-semibold text-foreground">Reset password via OTP email</p>
                <Input type="email" className="h-9 text-sm" placeholder="Email akun" value={reset.email}
                  onChange={(e) => setReset((r) => ({ ...r, email: e.target.value }))} data-testid="reset-email" />
                {reset.terkirim && (
                  <>
                    <Input className="h-9 text-sm" placeholder="Kode OTP (6 digit)" inputMode="numeric" value={reset.otp}
                      onChange={(e) => setReset((r) => ({ ...r, otp: e.target.value.replace(/\D/g, "").slice(0, 6) }))} data-testid="reset-otp" />
                    <Input type="password" className="h-9 text-sm" placeholder="Password baru" value={reset.baru}
                      onChange={(e) => setReset((r) => ({ ...r, baru: e.target.value }))} data-testid="reset-baru" />
                    {/* Syarat kata sandi DITEGAKKAN sama seperti Daftar akun
                        (passwordRules) — dulu alur ini hanya meminta 8 karakter,
                        sehingga akun bisa berakhir dengan sandi yang justru
                        ditolak saat mendaftar. */}
                    {reset.baru && <PasswordStrength password={reset.baru} />}
                    {/* Konfirmasi ber-panduan RINGKAS: satu kolom + strip
                        penanda tipis. Alur reset ini dulu TANPA ketik ulang
                        sama sekali — satu salah ketik langsung tersimpan dan
                        pengguna terkunci dari akunnya sendiri. */}
                    {reset.baru && (
                      <AssistedPasswordConfirmationField
                        ringkas
                        password={reset.baru}
                        onMatchChange={setResetCocok}
                        placeholder="Ulangi password baru"
                        testId="reset-baru-konfirmasi"
                      />
                    )}
                  </>
                )}
                <div className="flex gap-2">
                  <Button type="button" variant="outline" className="flex-1 h-9"
                    onClick={() => { setReset(null); setResetCocok(false); }}>Batal</Button>
                  {/* `!reset.baru` ikut dicek: saat kolom sandi dikosongkan,
                      komponen konfirmasi ter-unmount tanpa sempat melaporkan
                      "tidak cocok", sehingga resetCocok bisa tertinggal true. */}
                  <Button type="button" className="flex-1 h-9" data-testid="reset-kirim"
                    disabled={reset.saving || (reset.terkirim && (!reset.baru || !resetCocok))}
                    onClick={async () => {
                      setReset((r) => ({ ...r, saving: true }));
                      try {
                        if (!reset.terkirim) {
                          const r1 = await axios.post(`${API}/auth/request-reset-otp`, { email: reset.email.trim(), otp: "" });
                          toast.success(r1.data?.message || "OTP terkirim bila email terdaftar");
                          if (r1.data?.debug_otp) toast.info(`OTP (debug): ${r1.data.debug_otp}`);
                          setReset((r) => ({ ...r, terkirim: true, saving: false }));
                        } else {
                          const galatBaru = galatPassword(reset.baru);
                          if (galatBaru) {
                            toast.error(galatBaru);
                            setReset((r) => (r ? { ...r, saving: false } : r));
                            return;
                          }
                          const r2 = await axios.post(`${API}/auth/reset-password`, {
                            email: reset.email.trim(), otp: reset.otp, new_password: reset.baru });
                          toast.success(r2.data?.message || "Password direset — silakan masuk");
                          setReset(null);
                          setResetCocok(false);
                        }
                      } catch (e2) {
                        toast.error(e2?.response?.data?.detail || "Gagal memproses reset password");
                        setReset((r) => (r ? { ...r, saving: false } : r));
                      }
                    }}>
                    {reset.terkirim ? "Setel Password Baru" : "Kirim OTP"}
                  </Button>
                </div>
              </div>
            )}
            <div className="text-center text-sm">
              <span className="text-muted-foreground">{isLogin ? "Belum punya akun?" : "Sudah punya akun?"}</span>
              <button type="button"
                onClick={() => { setIsLogin(!isLogin); setSukses(false); }}
                className="ml-2 text-blue-600 hover:text-blue-700 font-medium"
                data-testid="toggle-auth-mode">
                {isLogin ? "Daftar sekarang" : "Masuk"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
