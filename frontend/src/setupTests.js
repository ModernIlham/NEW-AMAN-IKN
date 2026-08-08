/**
 * Persiapan lingkungan uji — dijalankan Jest sekali sebelum tiap berkas uji.
 *
 * Menambah matcher DOM (`toBeInTheDocument`, `toHaveTextContent`, …) supaya uji
 * render bisa menegaskan APA YANG TERLIHAT PENGGUNA, bukan sekadar isi berkas.
 * Sebelum ini seluruh 741 uji repo bersifat statis: ia membaca `.jsx` sebagai
 * TEKS dan mencocokkan pola. Penjaga semacam itu berguna — ia menangkap kelas
 * cacat yang tak terlihat saat membaca kode — tetapi ia buta pada satu hal
 * yang justru paling sering menjatuhkan halaman: komponennya gagal dirender
 * sama sekali.
 */
require("@testing-library/jest-dom");
