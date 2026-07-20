import { useState, useRef } from "react";
import { Package, Mail, Lock, ArrowRight, Loader2, Eye, EyeOff, User, ShieldCheck, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "@/lib/utils";
import { useTripleClick } from "@/hooks/useTripleClick";

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
            className="w-12 h-14 text-center text-xl font-bold border-2 border-border rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all bg-background text-foreground"
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
  const checks = [
    { label: "Min. 8 karakter", ok: password.length >= 8 },
    { label: "Huruf besar (A-Z)", ok: /[A-Z]/.test(password) },
    { label: "Huruf kecil (a-z)", ok: /[a-z]/.test(password) },
    { label: "Angka (0-9)", ok: /\d/.test(password) },
    { label: "Karakter khusus (!@#$)", ok: /[^A-Za-z0-9]/.test(password) },
  ];
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Registration validations
    if (!isLogin) {
      if (formData.password !== formData.confirmPassword) {
        toast.error("Password tidak sama. Periksa kembali.");
        return;
      }
      if (formData.password.length < 8) {
        toast.error("Password minimal 8 karakter");
        return;
      }
      const hasUpper = /[A-Z]/.test(formData.password);
      const hasLower = /[a-z]/.test(formData.password);
      const hasDigit = /\d/.test(formData.password);
      if (!hasUpper || !hasLower || !hasDigit) {
        toast.error("Password harus mengandung huruf besar, huruf kecil, dan angka");
        return;
      }
    }
    setLoading(true);
    try {
      if (isLogin) {
        const res = await axios.post(`${API}/auth/login`, {
          username: formData.username,
          password: formData.password
        });
        toast.success("Login berhasil!");
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
        <div className="relative z-10 flex flex-col justify-between p-12 w-full">
          <div className={`flex items-center gap-3 ${onShowInfo ? "cursor-pointer" : ""}`} data-testid="login-logo" {...logoProps}>
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center shadow-elev-2">
              <Package className="w-6 h-6 text-white" />
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-xl font-bold text-white font-['Manrope']">AMAN</span>
              <span className="text-[11px] font-medium text-slate-300">Aplikasi Manajemen Aset Negara</span>
            </div>
          </div>
          <div className="space-y-6">
            <h1 className="text-4xl font-bold text-white leading-tight font-['Manrope']">
              Sistem Inventaris<br />Aset Terpadu
            </h1>
            <p className="text-muted-foreground text-lg max-w-md">
              Kelola aset fisik organisasi Anda dengan mudah, cepat, dan terstruktur.
            </p>
            <div className="space-y-3 pt-4">
              {["CRUD lengkap dengan foto", "Export PDF & Excel dengan gambar", "Manajemen kategori dinamis", "Import data massal via CSV"].map((f, i) => (
                <div key={i} className="flex items-center gap-3 text-muted-foreground">
                  <div className="w-1.5 h-1.5 bg-blue-500 rounded-full" />
                  <span className="text-sm">{f}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="text-muted-foreground text-sm">&copy; {new Date().getFullYear()} AMAN — Aplikasi Manajemen Aset Negara</div>
        </div>
      </div>

      {/* Right Panel */}
      <div className="flex-1 flex items-center justify-center p-8 bg-card">
        {otpStep ? (
          <OTPVerification
            email={otpEmail}
            debugOtp={debugOtp}
            onVerified={onLogin}
            onBack={() => { setOtpStep(false); setDebugOtp(null); }}
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
                      className="pl-10 h-11 border-border focus:border-blue-500 focus:ring-blue-500"
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
                    className="pl-10 h-11 border-border focus:border-blue-500 focus:ring-blue-500"
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
                    className="pl-10 pr-10 h-11 border-border focus:border-blue-500 focus:ring-blue-500"
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
                      className={`pl-10 h-11 border-border focus:border-blue-500 focus:ring-blue-500 ${formData.confirmPassword && formData.password !== formData.confirmPassword ? 'border-red-400 focus:border-red-500 focus:ring-red-200' : formData.confirmPassword && formData.password === formData.confirmPassword ? 'border-emerald-400 focus:border-emerald-500 focus:ring-emerald-200' : ''}`}
                      data-testid="confirm-password-input"
                    />
                  </div>
                  {formData.confirmPassword && formData.password !== formData.confirmPassword && (
                    <p className="text-xs text-red-500" data-testid="password-mismatch-error">Password tidak sama</p>
                  )}
                </div>
              )}

              <Button type="submit" disabled={loading}
                className="w-full h-11 bg-slate-900 hover:bg-slate-800 text-white font-medium"
                data-testid="submit-button">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : (
                  <>{isLogin ? "Masuk" : "Daftar"}<ArrowRight className="w-4 h-4 ml-2" /></>
                )}
              </Button>
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
                <Input type="email" placeholder="Email akun" value={reset.email}
                  onChange={(e) => setReset((r) => ({ ...r, email: e.target.value }))} data-testid="reset-email" />
                {reset.terkirim && (
                  <>
                    <Input placeholder="Kode OTP (6 digit)" inputMode="numeric" value={reset.otp}
                      onChange={(e) => setReset((r) => ({ ...r, otp: e.target.value.replace(/\D/g, "").slice(0, 6) }))} data-testid="reset-otp" />
                    <Input type="password" placeholder="Password baru (min. 8 karakter)" value={reset.baru}
                      onChange={(e) => setReset((r) => ({ ...r, baru: e.target.value }))} data-testid="reset-baru" />
                  </>
                )}
                <div className="flex gap-2">
                  <Button type="button" variant="outline" className="flex-1 h-9" onClick={() => setReset(null)}>Batal</Button>
                  <Button type="button" className="flex-1 h-9" disabled={reset.saving} data-testid="reset-kirim"
                    onClick={async () => {
                      setReset((r) => ({ ...r, saving: true }));
                      try {
                        if (!reset.terkirim) {
                          const r1 = await axios.post(`${API}/auth/request-reset-otp`, { email: reset.email.trim(), otp: "" });
                          toast.success(r1.data?.message || "OTP terkirim bila email terdaftar");
                          if (r1.data?.debug_otp) toast.info(`OTP (debug): ${r1.data.debug_otp}`);
                          setReset((r) => ({ ...r, terkirim: true, saving: false }));
                        } else {
                          const r2 = await axios.post(`${API}/auth/reset-password`, {
                            email: reset.email.trim(), otp: reset.otp, new_password: reset.baru });
                          toast.success(r2.data?.message || "Password direset — silakan masuk");
                          setReset(null);
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
                onClick={() => setIsLogin(!isLogin)}
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
