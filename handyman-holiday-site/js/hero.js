/* Hero: a real photo of a decorated house. Scroll switches its lights on, strand by strand.
   off.jpg  = the same photo, lights removed and graded to a dark night (pre-processed)
   lit.jpg  = the real lit photo
   map.png  = R: when each pixel switches on (0..1), G: how "bulb-like" it is (sharp pop vs soft glow)
   A WebGL shader blends off → lit per pixel from the scroll position, so it reverses on scroll-up. */
(function () {
  const hero = document.getElementById("hero");
  const track = document.getElementById("heroTrack");
  const canvas = document.getElementById("heroCanvas");
  const poster = document.getElementById("heroPoster");
  const meterFill = document.getElementById("meterFill");
  const meterVal = document.getElementById("meterVal");
  const hint = document.getElementById("heroHint");
  if (!hero || !canvas) return;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced) document.documentElement.classList.add("reduced");

  const BG = [11 / 255, 16 / 255, 32 / 255];
  let target = 0, current = reduced ? 1 : 0, visible = true, raf = 0, ready = false, fallback = null;

  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const ease = (t) => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

  function scrollProgress() {
    const rect = track.getBoundingClientRect();
    const range = track.offsetHeight - window.innerHeight;
    if (range <= 0) return 1;
    const raw = clamp(-rect.top / range, 0, 1);
    if (hint) hint.classList.toggle("is-hidden", raw > 0.03);
    return ease(clamp((raw - 0.03) / 0.84, 0, 1));
  }

  function setMeter(p) {
    const pct = Math.round(p * 100);
    meterFill.style.height = pct + "%";
    meterVal.textContent = pct + "%";
  }

  function loadImg(src) {
    return new Promise((res, rej) => { const i = new Image(); i.decoding = "async"; i.onload = () => res(i); i.onerror = rej; i.src = src; });
  }

  /* ---------- WebGL ---------- */
  const gl = canvas.getContext("webgl", { antialias: false, alpha: false, premultipliedAlpha: false, powerPreference: "low-power" });

  const VS = "attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}";
  const FS = [
    "precision mediump float;",
    "uniform sampler2D tOff,tLit,tMap;uniform float p,seed,edge;uniform vec4 rect;uniform vec2 res;uniform vec3 bg;",
    "float h(vec2 c){return fract(sin(dot(c,vec2(12.9898,78.233)))*43758.5453);}",
    "void main(){",
    " vec2 fc=vec2(gl_FragCoord.x,res.y-gl_FragCoord.y);",
    " vec2 uv=(fc-rect.xy)/rect.zw; vec2 c=clamp(uv,0.,1.);",
    " vec3 off=texture2D(tOff,c).rgb; vec3 lit=texture2D(tLit,c).rgb; vec4 m=texture2D(tMap,c);",
    " float soft=mix(.11,.016,m.g);",
    " float a=smoothstep(m.r-.004,m.r+soft,p);",
    " a=max(a,smoothstep(.93,1.,p));",
    " vec3 col=mix(off,lit,a);",
    " col+=lit*m.g*a*(1.-a)*1.4;",                       // brief ignition flare as a bulb comes on
    " float ex=smoothstep(0.,edge,uv.x)*smoothstep(1.,.96,uv.x);",
    " float ey=smoothstep(0.,.10,uv.y)*smoothstep(1.,.86,uv.y);",
    " col=mix(bg,col,ex*ey);",
    " vec2 q=fc/res-.5; col*=1.-dot(q,q)*.5;",          // lens vignette
    " col+=(h(fc+seed)-.5)*.045;",                       // film grain hides the soft source resolution
    " gl_FragColor=vec4(col,1.);}"
  ].join("\n");

  let prog, U = {};
  function shader(type, src) { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; }
  function tex(img, unit) {
    const t = gl.createTexture(); gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, img);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  }

  let iw = 960, ih = 648, W = 0, H = 0, dpr = 1;
  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const cw = canvas.clientWidth, ch = canvas.clientHeight;
    const scale = Math.min(dpr, 2200 / Math.max(cw, 1));
    W = Math.round(cw * scale); H = Math.round(ch * scale);
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    if (gl) gl.viewport(0, 0, W, H);
  }
  function layout(p) {
    // Portrait: keep the whole house large and centred. Landscape: height-fit and shift the
    // house right so the headline sits on the dark left side; the image edge fades into the page.
    const z = 1 + 0.06 * p;                              // slow dolly-in as the lights come on
    if (W / H < 0.9) {
      const s = (W / (iw * 0.74)) * z, w = iw * s, h = ih * s;
      return [W * 0.5 - w * 0.5, H * 0.53 - h * 0.5, w, h];
    }
    const s = (H / ih) * Math.max(0.84, Math.min(1.04, 1.86 - (W / H) * 0.6)) * z;
    const w = iw * s, h = ih * s;
    const x = W - w * 0.97 - (z - 1) * w * 0.3;         // right-anchored; the left edge fades out
    const y = (H - h) * 0.45;
    return [x, y, w, h];
  }

  function draw(p) {
    if (fallback) { fallback.style.opacity = p; setMeter(p); return; }
    if (!ready) return;
    gl.uniform1f(U.p, p);
    gl.uniform1f(U.seed, (p * 977) % 97);
    const r = layout(p);
    gl.uniform4fv(U.rect, r);
    gl.uniform1f(U.edge, r[0] > 2 ? 0.2 : 0.04);
    gl.uniform2f(U.res, W, H);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
    setMeter(p);
  }

  function tick() {
    raf = 0;
    const d = target - current;
    current = Math.abs(d) < 0.0008 ? target : current + d * 0.14;
    draw(current);
    if (current !== target && visible) raf = requestAnimationFrame(tick);
  }
  function request() { if (!raf && visible) raf = requestAnimationFrame(tick); }

  function onScroll() { if (reduced) return; target = scrollProgress(); request(); }

  function useFallback() {
    // No WebGL: cross-fade the two real photos.
    fallback = document.createElement("img");
    fallback.src = "images/hero/lit.jpg"; fallback.alt = ""; fallback.className = "hero__poster"; fallback.style.opacity = current;
    poster.after(fallback);
    canvas.style.display = "none";
    draw(current);
  }

  async function init() {
    if (reduced) { poster.src = "images/hero/lit.jpg"; setMeter(1); }
    if (!gl) { useFallback(); return; }
    try {
      prog = gl.createProgram();
      gl.attachShader(prog, shader(gl.VERTEX_SHADER, VS));
      gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, FS));
      gl.linkProgram(prog); gl.useProgram(prog);
      const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
      const loc = gl.getAttribLocation(prog, "a"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      ["tOff", "tLit", "tMap", "p", "seed", "edge", "rect", "res", "bg"].forEach((n) => (U[n] = gl.getUniformLocation(prog, n)));
      const [off, lit, map] = await Promise.all([loadImg("images/hero/off.jpg"), loadImg("images/hero/lit.jpg"), loadImg("images/hero/map.png")]);
      iw = lit.naturalWidth; ih = lit.naturalHeight;
      tex(off, 0); tex(lit, 1); tex(map, 2);
      gl.uniform1i(U.tOff, 0); gl.uniform1i(U.tLit, 1); gl.uniform1i(U.tMap, 2);
      gl.uniform3fv(U.bg, BG);
      resize(); ready = true; hero.classList.add("is-gl");
      target = reduced ? 1 : scrollProgress(); current = target; draw(current);
    } catch (e) { console.warn("Hero WebGL unavailable, using fallback.", e); useFallback(); }
  }

  // Pause rendering while the hero is off-screen.
  new IntersectionObserver((es) => { visible = es[0].isIntersecting; if (visible) onScroll(); }, { rootMargin: "100px" }).observe(track);
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", () => { resize(); draw(current); });
  canvas.addEventListener("webglcontextlost", (e) => { e.preventDefault(); ready = false; });
  init();
})();
