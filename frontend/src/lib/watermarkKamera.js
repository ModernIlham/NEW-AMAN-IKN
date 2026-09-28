// Stempel bukti lapangan: data tetap utuh, bingkai/tinggi setara stempel lama.
// Tidak memoles piksel objek dan tidak menaikkan resolusi atau kualitas JPEG.
export function gambarWatermarkKamera(ctx, lebar, tinggi, lines) {
  const fs = Math.max(13, Math.round(lebar * 0.018));
  const lh = Math.round(fs * 1.4), pad = Math.round(fs * 0.8);
  ctx.save();
  ctx.font = `600 ${fs}px Arial, sans-serif`;
  const boxW = Math.min(lebar - pad * 2, Math.max(...lines.map(l => ctx.measureText(l).width)) + pad * 2);
  const boxH = Math.min(tinggi - pad, lh * lines.length + pad * 1.4);
  const x = pad / 2, y = tinggi - boxH - pad / 2, r = Math.min(pad * 0.65, boxH / 2);
  // Path biasa, tidak bergantung canvas.roundRect yang absen di browser lama.
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.lineTo(x + boxW - r, y);
  ctx.quadraticCurveTo(x + boxW, y, x + boxW, y + r);
  ctx.lineTo(x + boxW, y + boxH - r); ctx.quadraticCurveTo(x + boxW, y + boxH, x + boxW - r, y + boxH);
  ctx.lineTo(x + r, y + boxH); ctx.quadraticCurveTo(x, y + boxH, x, y + boxH - r);
  ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y); ctx.closePath();
  ctx.clip();
  const gradasi = ctx.createLinearGradient(x, y, x + boxW, y + boxH);
  gradasi.addColorStop(0, "rgba(10,24,32,0.82)");
  gradasi.addColorStop(1, "rgba(10,24,32,0.62)");
  ctx.fillStyle = gradasi; ctx.fillRect(x, y, boxW, boxH);
  ctx.fillStyle = "#5eead4"; ctx.fillRect(x, y, Math.max(2, fs * 0.15), boxH);
  lines.forEach((line, i) => {
    ctx.font = `${i === 2 || i === 3 ? 700 : 500} ${fs}px Arial, sans-serif`;
    ctx.fillStyle = i === 2 ? "#99f6e4" : i === 0 || i === 3 ? "#ffffff" : "#e2e8f0";
    ctx.fillText(line, x + pad * 0.85, y + pad * 0.4 + lh * (i + 1) - fs * 0.25, boxW - pad * 1.6);
  });
  ctx.restore();
  return { x, y, lebar: boxW, tinggi: boxH };
}
