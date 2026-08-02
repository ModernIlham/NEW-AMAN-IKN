# Kebijakan Logging AMAN — "Aturan Main Logging"

Enam aturan yang ditegakkan di seluruh aplikasi, beserta status
implementasinya (semuanya di `backend/log_setup.py`, dipasang oleh
`server.py` lewat `configure_logging()`):

| # | Aturan | Status di AMAN |
|---|---|---|
| 1 | **Pakai library logging + level, bukan `print`/`console.log`** | ✅ Backend: seluruh runtime memakai `logging` (`print` hanya di skrip CLI mandiri — di sana print memang antarmukanya). Frontend: **0** `console.log/debug` di `src/`. |
| 2 | **Log berformat JSON** | ✅ `JsonLogFormatter` (JSON-lines) kini **DEFAULT**; `LOG_FORMAT=plain` opsi pengembangan lokal. |
| 3 | **Sensor data sensitif (redact)** | ✅ `RedaksiLogFilter` menyensor SETIAP pesan: `password/token/secret/api_key/otp/authorization = …`, `Bearer …`, JWT telanjang (`eyJ…`), dan NIK 16 digit (disisakan 4 digit akhir; NIP 18 digit & kode satker tidak tersentuh). Teruji unit. |
| 4 | **Request-id untuk pelacakan** | ✅ `RequestContextMiddleware`: terima/lahirkan `X-Request-ID`, tempel ke tiap baris log + header respons; job latar memakai `set_job_id()` (`job:<id>`). |
| 5 | **Keluaran ke stdout, bukan file** | ✅ Handler `StreamHandler(sys.stdout)` — journald/systemd yang menampung & merotasi. Tidak ada file log aplikasi. |
| 6 | **Centralized logging** | ⚙️ Lihat kebijakan di bawah — untuk satu VPS, journald ADALAH pusatnya; agen eksternal baru dipasang bila benar-benar perlu. |

## Cara membaca log di VPS (tanpa perkakas tambahan)

Karena keluaran JSON-lines ke stdout, journald menjadi agregator:

```bash
journalctl -u aman-backend -f                        # ikuti live
journalctl -u aman-backend -S -1h -o cat | jq 'select(.level=="ERROR")'
journalctl -u aman-backend -o cat | jq 'select(.request_id=="abc123")'   # lacak satu request
journalctl -u aman-backend -o cat | jq 'select(.duration_ms>1000)'       # request lambat
```

Plafon ukuran journal diatur di `docs/OPTIMASI-VPS.md` (blok D).

## Kebijakan centralized logging (Alloy → Loki → Grafana?) — keputusan bijak

**Untuk topologi saat ini (SATU VPS 2 vCPU / 8 GB): JANGAN memasang stack
log terpusat sendiri.** Alasan:

- "Terpusat" bermakna saat sumber lognya banyak. Dengan satu server,
  journald + `jq` sudah memberi 95% manfaatnya tanpa RAM tambahan.
- Loki + Grafana + Alloy self-hosted memakan ±1–1,5 GB RAM dan perawatan
  rutin — di mesin ini mereka bersaing langsung dengan MongoDB.

**Tangga eskalasi bila kebutuhan tumbuh:**

1. **Sekarang** — journald + `LOG_FORMAT=json` (sudah default) + `jq`.
2. **Butuh dasbor/alarm tanpa beban server** — pasang **Grafana Alloy**
   (agen tunggal, ±150 MB) yang membaca journald dan mengirim ke **Grafana
   Cloud tier gratis** (Loki terkelola). Nol perawatan server, log keluar
   VPS (aman saat VPS bermasalah). Ini langkah pertama yang disarankan bila
   ingin visual.
3. **Multi-server / retensi panjang / kedaulatan data penuh** — barulah
   Alloy → Loki self-hosted → Grafana di mesin TERPISAH (jangan di VPS
   aplikasi).

Pemicu konkret untuk naik ke tangga 2: Anda mendapati diri membuka
`journalctl` lebih dari beberapa kali seminggu untuk berburu galat, atau
butuh alarm otomatis (error rate/latensi) ke Telegram/e-mail.

## Konvensi menulis log untuk pengembang

- Selalu `logger = logging.getLogger(__name__)`; jangan pernah `print` di
  kode runtime backend, jangan `console.log` di frontend (`console.error`
  untuk galat nyata boleh — lint menjaga).
- Level: `debug` detail teknis; `info` peristiwa bisnis normal;
  `warning` anomali yang tertangani; `error` kegagalan yang butuh tindakan.
- **Jangan menaruh rahasia/PII di pesan log** — redaksi adalah jaring
  pengaman terakhir, bukan izin. Traceback TIDAK diredaksi: jangan
  menyisipkan rahasia ke pesan exception.
- Nilai kiriman user yang masuk log harus lewat `_bersih_log()` (anti
  injeksi baris log) — pola yang sudah dipakai access log.
