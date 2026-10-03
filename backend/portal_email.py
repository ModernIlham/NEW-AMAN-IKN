"""Tampilan email akses BMN Saya; tanpa gambar pelacak atau sumber eksternal."""
from html import escape


def isi_email_portal(nama, link, menit):
    """HTML email berbasis tabel + alternatif teks; TTL diberikan oleh pemanggil."""
    penerima = str(nama or "Pemegang BMN")
    nama_html = escape(penerima)
    link_html = escape(link, quote=True)
    html = f"""<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Akses BMN Saya — AMAN</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f4;color:#172f34;font-family:Arial,Helvetica,sans-serif;-webkit-text-size-adjust:100%;">
  <div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">Tautan pribadi untuk BMN Saya. Berlaku {menit} menit dan hanya dapat dipakai sekali.</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f1f5f4;">
    <tr><td align="center" style="padding:28px 12px;">
      <!--[if mso]><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;">
        <tr><td style="padding:0 12px 18px;">
          <p style="margin:0;color:#0f766e;font-size:26px;line-height:32px;font-weight:700;letter-spacing:2px;">AMAN</p>
          <p style="margin:4px 0 0;color:#526766;font-size:12px;line-height:18px;">Aplikasi Manajemen Aset &amp; BMN</p>
        </td></tr>
        <tr><td style="background-color:#ffffff;border:1px solid #dce6e3;border-top:4px solid #0f766e;border-radius:12px;padding:28px 24px;">
          <p style="margin:0 0 12px;color:#0f766e;font-size:11px;line-height:16px;font-weight:700;letter-spacing:1.6px;">PORTAL PEMEGANG BMN</p>
          <h1 style="margin:0 0 20px;color:#172f34;font-size:28px;line-height:35px;font-weight:700;">Masuk ke BMN Saya</h1>
          <p style="margin:0 0 12px;color:#334b50;font-size:15px;line-height:24px;overflow-wrap:anywhere;word-break:break-word;">Yth. <strong>{nama_html}</strong>,</p>
          <p style="margin:0 0 16px;color:#334b50;font-size:15px;line-height:24px;">Pantau aset yang Anda pegang dan laporkan keadaan terbarunya melalui BMN Saya.</p>
          <p style="margin:0 0 22px;color:#334b50;font-size:15px;line-height:24px;">Buka tautan ini pada <strong>peramban tempat Anda meminta akses</strong>.</p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr><td align="center" bgcolor="#0f766e" style="background-color:#0f766e;border-radius:8px;mso-padding-alt:16px 20px;">
              <a href="{link_html}" data-testid="email-portal-masuk" style="display:block;padding:16px 20px;border:1px solid #0f766e;border-radius:8px;color:#ffffff;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:22px;font-weight:700;text-align:center;text-decoration:none;">Masuk ke BMN Saya</a>
            </td></tr>
          </table>
          <p style="margin:12px 0 24px;color:#526766;font-size:12px;line-height:19px;text-align:center;">Berlaku {menit} menit &nbsp;&middot;&nbsp; Hanya dapat dipakai sekali</p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#edf6f3;border-radius:8px;">
            <tr><td style="padding:16px;">
              <h2 style="margin:0 0 6px;color:#18574f;font-size:14px;line-height:21px;font-weight:700;">Jaga keamanan akses Anda</h2>
              <p style="margin:0;color:#334b50;font-size:13px;line-height:21px;">Jangan teruskan tautan ini kepada siapa pun. Abaikan email ini bila Anda tidak meminta akses.</p>
            </td></tr>
          </table>
          <p style="margin:20px 0 0;color:#526766;font-size:13px;line-height:21px;"><strong>Tautan sudah kedaluwarsa?</strong><br>Kembali ke halaman BMN Saya dan masukkan email Anda untuk meminta tautan baru.</p>
        </td></tr>
        <tr><td align="center" style="padding:20px 16px 0;">
          <p style="margin:0;color:#526766;font-size:12px;line-height:19px;">Masuk ke portal bukan tindakan penandatanganan dokumen.</p>
          <p style="margin:8px 0 0;color:#526766;font-size:12px;line-height:19px;">AMAN &mdash; Aset terpantau, tanggung jawab tercatat.</p>
        </td></tr>
      </table>
      <!--[if mso]></td></tr></table><![endif]-->
    </td></tr>
  </table>
</body>
</html>"""
    text = (
        "AMAN — Aplikasi Manajemen Aset & BMN\nBMN Saya\n\n"
        f"Yth. {penerima},\n\n"
        "Pantau aset yang Anda pegang dan laporkan keadaan terbarunya melalui BMN Saya.\n"
        "Buka tautan ini pada peramban tempat Anda meminta akses:\n"
        f"{link}\n\n"
        f"Tautan berlaku {menit} menit dan hanya dapat dipakai sekali.\n"
        "Jangan teruskan tautan ini kepada siapa pun. Abaikan email ini bila Anda tidak meminta akses.\n\n"
        "Tautan sudah kedaluwarsa? Kembali ke halaman BMN Saya dan masukkan email Anda "
        "untuk meminta tautan baru.\n\n"
        "Masuk ke portal bukan tindakan penandatanganan dokumen.\n"
    )
    return {"html": html, "text": text}
