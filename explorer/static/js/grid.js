// Rendering a 64×64 game screen and a score sparkline onto <canvas>. This mirrors the
// proven logic in demo.html: each cell value 0–15 maps to a colour from the palette the
// server sends (a display choice; the model reasons over the numbers, not the hues).

export function decodeGrid(hex, w, h) {
  const g = new Uint8Array(w * h);
  for (let k = 0; k < hex.length; k++) g[k] = parseInt(hex[k], 16);
  return g;
}

export function drawScreen(canvas, step, palette) {
  const w = step.w, h = step.h;
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d');
  const g = decodeGrid(step.grid, w, h);
  const img = ctx.createImageData(w, h);
  for (let p = 0; p < g.length; p++) {
    const c = palette[g[p]] || '#000';
    img.data[p * 4] = parseInt(c.slice(1, 3), 16);
    img.data[p * 4 + 1] = parseInt(c.slice(3, 5), 16);
    img.data[p * 4 + 2] = parseInt(c.slice(5, 7), 16);
    img.data[p * 4 + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
}

// Score over the whole run, with a playhead at step `i`. The flat line is the point.
export function drawSpark(canvas, steps, i) {
  const ctx = canvas.getContext('2d');
  const W = canvas.width = canvas.clientWidth || 420;
  const H = canvas.height = 40;
  ctx.clearRect(0, 0, W, H);
  const n = steps.length;
  const maxS = Math.max(1, ...steps.map(s => s.score));
  ctx.strokeStyle = 'rgba(127,127,127,.25)';
  ctx.beginPath(); ctx.moveTo(0, H - 6); ctx.lineTo(W, H - 6); ctx.stroke();
  ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue('--accent') || '#4FC3F7';
  ctx.lineWidth = 2; ctx.beginPath();
  steps.forEach((s, k) => {
    const x = n > 1 ? (k / (n - 1)) * W : 0;
    const y = H - 6 - (s.score / maxS) * (H - 12);
    k ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
  const px = n > 1 ? (i / (n - 1)) * W : 0;
  ctx.strokeStyle = 'rgba(160,160,160,.7)'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, H); ctx.stroke();
}
