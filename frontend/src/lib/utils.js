import { clsx } from "clsx";
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export function getApiError(err, fallback = "Terjadi kesalahan") {
  const d = err?.response?.data?.detail;
  if (!d) return fallback;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d.map(e => e.msg || String(e)).join(', ');
  return String(d);
}
