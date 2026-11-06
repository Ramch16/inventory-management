/* Holiday light designer.
   - Sample homes come with pre-drawn strands; customers can also upload their own photo
     and tap along the roofline. Everything happens in the browser: the photo is never uploaded
     unless the customer chooses "Use this design in my quote" and then sends the form.
   - Rendering: real photo → night grade (multiply + desaturate) → thin wire → wall spill → glow → bulb core. */
(function () {
  const stage = document.getElementById("dzStage");
  const canvas = document.getElementById("dzCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const tip = document.getElementById("dzTip");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const PALETTES = [
    { id: "warm", name: "Warm white", colors: ["#ffcf86"] },
    { id: "multi", name: "Classic multi", colors: ["#ff3b3b", "#ffc23a", "#2fe07a", "#3fa2ff", "#ff63d0"] },
    { id: "cool", name: "Cool white", colors: ["#dfeeff"] },
    { id: "candy", name: "Candy cane", colors: ["#ff2e45", "#fff1e2"] },
    { id: "merry", name: "Red & green", colors: ["#ff2e45", "#2fe07a"] },
    { id: "ice", name: "Icy blue", colors: ["#63ccff", "#e4f6ff"] },
    { id: "amber", name: "Vintage amber", colors: ["#ff9a3a"] },
    { id: "plum", name: "Plum & gold", colors: ["#b36bff", "#ffc864"] }
  ];
  const STYLES = { c9: { core: 2.6, glow: 20, min: 16, max: 42 }, mini: { core: 1.5, glow: 11, min: 8, max: 22 }, icicle: { core: 1.3, glow: 9, min: 9, max: 24 } };
  const SAMPLES = {
    cottage: { src: "images/sample-cottage-lg.jpg", label: "Sample cottage", strands: [
      [[4.8, 22.3], [43.7, 2.6], [84.3, 22.3]], [[4.8, 23.9], [84.5, 23.9]], [[11.8, 28.6], [78.5, 28.6]],
      [[17.9, 30.5], [17.9, 63.5]], [[72.6, 30.5], [72.6, 63.5]]] },
    deck: { src: "images/sample-green-house-lg.jpg", label: "Sample deck", strands: [
      [[0, 5.7], [100, 5.7]], [[8.3, 33], [37, 33.8]], [[65.6, 33.6], [92, 32.6]], [[32.4, 50.2], [73.4, 50.2]]] }
  };

  const state = { img: null, own: false, sample: "cottage", strands: [[]], palette: PALETTES[0], style: "c9", effect: "steady", dusk: 0.85, spacing: 0.45 };
  let W = 0, H = 0, rect = [0, 0, 1, 1], visible = false, raf = 0, sprites = {}, bulbs = [], seeded = [];

  /* ---------- helpers ---------- */
  const hexRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const mix = (a, b, t) => a + (b - a) * t;
  function sprite(color, kind) {
    const key = color + kind;
    if (sprites[key]) return sprites[key];
    const s = 128, c = document.createElement("canvas"); c.width = c.height = s;
    const g = c.getContext("2d"), [r, gg, b] = hexRgb(color);
    const grad = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
    if (kind === "glow") {
      grad.addColorStop(0, `rgba(${r},${gg},${b},.95)`); grad.addColorStop(.18, `rgba(${r},${gg},${b},.45)`);
      grad.addColorStop(.45, `rgba(${r},${gg},${b},.12)`); grad.addColorStop(1, `rgba(${r},${gg},${b},0)`);
    } else { // core: hot white centre tinted by the bulb color
      grad.addColorStop(0, "rgba(255,255,250,1)"); grad.addColorStop(.35, `rgba(${mix(r, 255, .6)|0},${mix(gg, 255, .6)|0},${mix(b, 255, .6)|0},1)`);
      grad.addColorStop(.7, `rgba(${r},${gg},${b},.9)`); grad.addColorStop(1, `rgba(${r},${gg},${b},0)`);
    }
    g.fillStyle = grad; g.fillRect(0, 0, s, s);
    return (sprites[key] = c);
  }

  /* ---------- layout ---------- */
  function resize() {
    if (!state.img) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const cw = stage.clientWidth;
    const iw = state.img.naturalWidth || state.img.width, ih = state.img.naturalHeight || state.img.height;
    const aspect = Math.min(2, Math.max(0.8, iw / ih));
    W = Math.round(cw * dpr); H = Math.round((cw / aspect) * dpr);
    canvas.width = W; canvas.height = H;
    const s = Math.min(W / iw, H / ih), w = iw * s, h = ih * s;
    rect = [(W - w) / 2, (H - h) / 2, w, h];
    layoutBulbs();
    render(performance.now());
  }
  const toPx = (pt) => [rect[0] + (pt[0] / 100) * rect[2], rect[1] + (pt[1] / 100) * rect[3]];

  function layoutBulbs() {
    const st = STYLES[state.style], k = rect[2] / 1000;
    const gap = mix(st.min, st.max, state.spacing) * k * 1.6;
    bulbs = [];
    let idx = 0;
    state.strands.forEach((strand) => {
      if (strand.length < 2) return;
      let carry = 0;
      for (let i = 0; i < strand.length - 1; i++) {
        const [x1, y1] = toPx(strand[i]), [x2, y2] = toPx(strand[i + 1]);
        const len = Math.hypot(x2 - x1, y2 - y1);
        const steep = Math.abs(y2 - y1) > Math.abs(x2 - x1) * 1.2;   // no icicle drops on vertical runs
        let d = carry;
        while (d <= len) {
          const t = d / len;
          bulbs.push({ x: x1 + (x2 - x1) * t, y: y1 + (y2 - y1) * t, i: idx++, steep });
          d += gap;
        }
        carry = d - len;
      }
    });
    // stable per-bulb randomness (twinkle phase, icicle length)
    while (seeded.length < bulbs.length) seeded.push({ ph: Math.random() * 6.28, sp: 1.2 + Math.random() * 2.2, drop: 0.35 + Math.random() * 0.65 });
  }

  /* ---------- render ---------- */
  function render(t, forExport) {
    if (!state.img) return;
    const d = state.dusk, k = rect[2] / 1000, st = STYLES[state.style], pal = state.palette.colors;
    ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
    ctx.fillStyle = "#05070f"; ctx.fillRect(0, 0, W, H);
    ctx.drawImage(state.img, rect[0], rect[1], rect[2], rect[3]);
    // night grade
    ctx.save(); ctx.beginPath(); ctx.rect(rect[0], rect[1], rect[2], rect[3]); ctx.clip();
    ctx.globalCompositeOperation = "saturation"; ctx.globalAlpha = 0.55 * d; ctx.fillStyle = "#808080"; ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = "multiply"; ctx.globalAlpha = 1;
    ctx.fillStyle = `rgb(${mix(255, 30, d) | 0},${mix(255, 44, d) | 0},${mix(255, 92, d) | 0})`; ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = "source-over";
    const sky = ctx.createLinearGradient(0, rect[1], 0, rect[1] + rect[3]);
    sky.addColorStop(0, `rgba(10,18,48,${0.25 * d})`); sky.addColorStop(1, `rgba(3,5,12,${0.35 * d})`);
    ctx.fillStyle = sky; ctx.fillRect(0, 0, W, H);

    // wires
    ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.strokeStyle = `rgba(20,28,22,${0.55 + 0.3 * (1 - d)})`; ctx.lineWidth = Math.max(1, 1.4 * k);
    state.strands.forEach((s) => { if (s.length < 2) return; ctx.beginPath(); s.forEach((p, i) => { const [x, y] = toPx(p); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.stroke(); });

    // bulbs
    const power = 0.35 + 0.65 * d;
    ctx.globalCompositeOperation = "lighter";
    const time = t / 1000;
    const level = (b) => {
      const r = seeded[b.i] || seeded[0];
      if (state.effect === "twinkle") return 0.5 + 0.5 * Math.max(0, Math.sin(time * r.sp + r.ph)) ** 2 + 0.05;
      if (state.effect === "chase") { const ph = ((b.i - time * 7) % 4 + 4) % 4; return ph < 1.6 ? 1 : 0.28; }
      return 1;
    };
    // pass 1: soft light spill on the wall / roof below each bulb
    bulbs.forEach((b) => {
      const c = pal[b.i % pal.length], L = level(b) * power, r = st.glow * k * 5;
      ctx.globalAlpha = 0.13 * L; ctx.drawImage(sprite(c, "glow"), b.x - r, b.y - r * 0.5, r * 2, r * 2);
    });
    // pass 2: glow + icicle drops + core
    bulbs.forEach((b) => {
      const c = pal[b.i % pal.length], L = level(b) * power, rnd = seeded[b.i] || seeded[0];
      const drops = state.style === "icicle" && !b.steep ? [0, rnd.drop * 0.55, rnd.drop] : [0];
      drops.forEach((dd) => {
        const y = b.y + dd * 34 * k;
        const g = st.glow * k * 2.3;
        ctx.globalAlpha = Math.min(1, 1.05 * L); ctx.drawImage(sprite(c, "glow"), b.x - g, y - g, g * 2, g * 2);
        const cr = st.core * k * 1.7;
        ctx.globalAlpha = Math.min(1, 0.4 + L); ctx.drawImage(sprite(c, "core"), b.x - cr, y - cr, cr * 2, cr * 2);
      });
    });
    ctx.restore();

    // editing guides (not in exports)
    if (!forExport) {
      ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha = 1;
      const cur = state.strands[state.strands.length - 1];
      state.strands.forEach((s) => s.forEach((p) => {
        const [x, y] = toPx(p);
        ctx.beginPath(); ctx.arc(x, y, (s === cur ? 5 : 3.5) * k * 1.6, 0, 6.283);
        ctx.strokeStyle = s === cur ? "rgba(255,255,255,.9)" : "rgba(255,255,255,.35)"; ctx.lineWidth = 1.5 * k * 1.4; ctx.stroke();
      }));
    }
  }

  function loop(t) {
    raf = 0; render(t);
    if (visible && state.effect !== "steady" && !reduced) raf = requestAnimationFrame(loop);
  }
  function kick() { if (!raf) raf = requestAnimationFrame(loop); }
  function redraw() { layoutBulbs(); if (state.effect === "steady" || reduced || !visible) render(performance.now()); else kick(); }

  /* ---------- image loading ---------- */
  function setImage(src, opts) {
    const img = new Image(); img.decoding = "async";
    img.onload = () => {
      state.img = img; state.own = !!opts.own;
      state.strands = opts.strands ? opts.strands.map((s) => s.map((p) => p.slice())).concat([[]]) : [[]];
      resize();
      tip.textContent = opts.own ? "Tap along your roofline to place lights" : "Tap the photo to add your own strand";
      tip.classList.remove("is-hidden");
      if (state.effect !== "steady") kick();
    };
    img.src = src;
  }
  function loadSample(id) {
    state.sample = id;
    setImage(SAMPLES[id].src, { strands: SAMPLES[id].strands });
    document.querySelectorAll(".thumb[data-sample]").forEach((b) => { const on = b.dataset.sample === id; b.classList.toggle("is-active", on); b.setAttribute("aria-pressed", on); });
    document.querySelector(".thumb--upload").classList.remove("is-active");
  }
  let ownURL = null;
  document.getElementById("dzUpload").addEventListener("change", (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f || !/^image\//.test(f.type)) return;
    if (ownURL) URL.revokeObjectURL(ownURL);
    ownURL = URL.createObjectURL(f);
    state.sample = null;
    setImage(ownURL, { own: true });
    document.querySelectorAll(".thumb[data-sample]").forEach((b) => { b.classList.remove("is-active"); b.setAttribute("aria-pressed", "false"); });
    document.querySelector(".thumb--upload").classList.add("is-active");
    e.target.value = "";
  });
  document.querySelectorAll(".thumb[data-sample]").forEach((b) => b.addEventListener("click", () => loadSample(b.dataset.sample)));

  /* ---------- drawing ---------- */
  canvas.addEventListener("pointerdown", (e) => {
    if (!state.img) return;
    const r = canvas.getBoundingClientRect(), sx = W / r.width;
    const x = (e.clientX - r.left) * sx, y = (e.clientY - r.top) * sx;
    const px = ((x - rect[0]) / rect[2]) * 100, py = ((y - rect[1]) / rect[3]) * 100;
    if (px < 0 || px > 100 || py < 0 || py > 100) return;
    state.strands[state.strands.length - 1].push([+px.toFixed(2), +py.toFixed(2)]);
    tip.classList.add("is-hidden");
    redraw();
  });
  document.getElementById("dzNew").addEventListener("click", () => { if (state.strands[state.strands.length - 1].length) state.strands.push([]); redraw(); });
  document.getElementById("dzUndo").addEventListener("click", () => {
    let cur = state.strands[state.strands.length - 1];
    if (!cur.length && state.strands.length > 1) { state.strands.pop(); cur = state.strands[state.strands.length - 1]; }
    cur.pop(); redraw();
  });
  document.getElementById("dzClear").addEventListener("click", () => { state.strands = [[]]; tip.textContent = "Tap along a roofline to add lights"; tip.classList.remove("is-hidden"); redraw(); });

  /* ---------- controls ---------- */
  const palWrap = document.getElementById("dzPalettes");
  PALETTES.forEach((p, i) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "swatch"; b.setAttribute("aria-pressed", i === 0);
    b.innerHTML = `<span class="swatch__dots">${p.colors.map((c) => `<i style="background:${c};color:${c}"></i>`).join("")}</span>${p.name}`;
    b.addEventListener("click", () => { state.palette = p; palWrap.querySelectorAll(".swatch").forEach((s) => s.setAttribute("aria-pressed", s === b)); redraw(); });
    palWrap.appendChild(b);
  });
  function segment(id, key) {
    const wrap = document.getElementById(id);
    wrap.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
      state[key] = b.dataset[key];
      wrap.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
      redraw(); if (key === "effect" && state.effect !== "steady") kick();
    }));
  }
  segment("dzStyles", "style"); segment("dzEffects", "effect");
  const dusk = document.getElementById("dzDusk"), duskOut = document.getElementById("dzDuskOut");
  const spacing = document.getElementById("dzSpacing"), spacingOut = document.getElementById("dzSpacingOut");
  dusk.addEventListener("input", () => { state.dusk = dusk.value / 100; duskOut.textContent = state.dusk < 0.3 ? "Day" : state.dusk < 0.62 ? "Dusk" : "Night"; redraw(); });
  spacing.addEventListener("input", () => { state.spacing = spacing.value / 100; spacingOut.textContent = state.spacing < 0.33 ? "Tight" : state.spacing < 0.67 ? "Medium" : "Wide"; redraw(); });

  /* ---------- send to quote form ---------- */
  document.getElementById("dzUse").addEventListener("click", () => {
    if (!state.img) return;
    const strands = state.strands.filter((s) => s.length > 1).length;
    const summary = `${state.palette.name}, ${{ c9: "large C9", mini: "mini", icicle: "icicle" }[state.style]} bulbs, ${state.effect}, ${strands} strand${strands === 1 ? "" : "s"}, on ${state.own ? "customer's own photo" : SAMPLES[state.sample].label.toLowerCase()}`;
    // export at a sensible size, without the editing guides
    const save = [W, H, rect.slice()];
    const scale = Math.min(1, 1400 / W);
    W = Math.round(W * scale); H = Math.round(H * scale); rect = rect.map((v) => v * scale);
    canvas.width = W; canvas.height = H; layoutBulbs(); render(performance.now(), true);
    canvas.toBlob((blob) => {
      [W, H, rect] = save; canvas.width = W; canvas.height = H; redraw();
      window.dispatchEvent(new CustomEvent("design:use", { detail: { blob, own: state.own, summary } }));
    }, "image/jpeg", 0.86);
  });

  /* ---------- lifecycle ---------- */
  new IntersectionObserver((es) => { visible = es[0].isIntersecting; if (visible && state.effect !== "steady") kick(); }, { rootMargin: "50px" }).observe(stage);
  let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(resize, 120); });
  // Load the first sample when the section gets close, to keep the first paint light.
  new IntersectionObserver((es, o) => { if (es[0].isIntersecting) { loadSample("cottage"); o.disconnect(); } }, { rootMargin: "600px" }).observe(stage);
})();
