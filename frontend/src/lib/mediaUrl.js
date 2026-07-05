// ============================================================================
// authMediaUrl — attach the JWT to media/report URLs that can't send a header.
// ============================================================================
// Media streaming endpoints (photos, checklist files, BAST, pengesahan dokumen)
// and the HTML/PDF report previews are consumed by plain <img src="..."> tags
// and window.open(...), neither of which can attach an Authorization header.
// The backend (auth_utils.require_user_or_query_token) therefore also accepts
// the token as a `?token=<jwt>` query param. This helper appends it while
// preserving any existing query string (e.g. ?v=<version> / ?thumb=1).
//
// TRADEOFF: a JWT placed in the URL is captured by web-server / proxy access
// logs. This is accepted as strictly better than the previous posture (fully
// anonymous media/report reads); the token carries the normal 24h TTL. A
// short-lived, media-scoped token is a future improvement.
export function authMediaUrl(url) {
  if (!url) return url;
  const token = localStorage.getItem("token");
  if (!token) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}token=${encodeURIComponent(token)}`;
}
