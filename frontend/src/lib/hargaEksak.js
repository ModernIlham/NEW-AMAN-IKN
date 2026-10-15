// Kontrak reader sama dengan Decimal128 server: angka hingga 34 digit
// signifikan, eksponen desimal -6176..6144 (sesudah normalisasi). Harga lama
// yang kosong/tidak valid/nonfinite diperlakukan nol, termasuk boolean.
const GRAMMAR = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;
const ZERO = Object.freeze({ sign: 0, digits: "0", exponent: 0 });
export function hargaEksak(value) {
  if (typeof value !== "string" && typeof value !== "number") return ZERO;
  const text = String(value).trim();
  if (!GRAMMAR.test(text)) return ZERO;
  const sign = text.startsWith("-") ? -1 : 1;
  const [mantissa, exp = "0"] = text.replace(/^[+-]/, "").split(/[eE]/);
  const [integer, fraction = ""] = mantissa.split(".");
  let digits = (integer + fraction).replace(/^0+/, "");
  if (!digits) return ZERO;
  let exponent = Number(exp) - fraction.length;
  const trailing = digits.match(/0+$/)?.[0].length || 0;
  if (trailing) { digits = digits.slice(0, -trailing); exponent += trailing; }
  if (!Number.isFinite(exponent) || digits.length > 34 || exponent < -6176 || exponent + digits.length - 1 > 6144) return ZERO;
  return { sign, digits, exponent };
}
export function bandingkanHargaTerurai(x, y) {
  if (x.sign !== y.sign) return x.sign < y.sign ? -1 : 1;
  if (x.sign === 0) return 0;
  const magnitudeX = x.digits.length + x.exponent;
  const magnitudeY = y.digits.length + y.exponent;
  if (magnitudeX !== magnitudeY) return (magnitudeX < magnitudeY ? -1 : 1) * x.sign;
  const width = Math.max(x.digits.length, y.digits.length);
  const left = x.digits.padEnd(width, "0"), right = y.digits.padEnd(width, "0");
  return left === right ? 0 : (left < right ? -1 : 1) * x.sign;
}

export function bandingkanHargaEksak(a, b) {
  return bandingkanHargaTerurai(hargaEksak(a), hargaEksak(b));
}
