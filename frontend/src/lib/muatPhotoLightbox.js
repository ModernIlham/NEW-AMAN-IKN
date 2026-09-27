let permintaan;

// Satu unduhan untuk daftar, galeri, dan peta. Kegagalan bukan cache permanen:
// setelah jaringan pulih pengguna dapat mencoba lagi tanpa reload/form hilang.
export function muatPhotoLightbox() {
  if (!permintaan) {
    permintaan = import(/* webpackChunkName: "photo-lightbox" */ "../components/assets/PhotoLightbox")
      .catch(error => { permintaan = null; throw error; });
  }
  return permintaan;
}
