/* Hero: the same house photographed by day and at night. Scrolling takes it from day, through dusk,
   to the lights switching on strand by strand; scrolling up reverses it.
   day.jpg = real daytime photo        off.jpg = dusk, lights still off (built from the day photo + night sky)
   lit.jpg = real night photo, lit     map.png = R: when each pixel switches on, G: how "bulb-like" it is
   Built by handyman-holiday-site-tools/build_hero_daynight.py */
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
    "uniform sampler2D tDay,tOff,tLit,tMap;uniform float p,seed;uniform vec4 rect;uniform vec2 res;",
    "float h(vec2 c){return fract(sin(dot(c,vec2(12.9898,78.233)))*43758.5453);}",
    "void main(){",
    " vec2 fc=vec2(gl_FragCoord.x,res.y-gl_FragCoord.y);",
    " vec2 uv=(fc-rect.xy)/rect.zw;",
    " vec2 c=clamp(vec2(1.-abs(1.-abs(uv.x)),uv.y),0.,1.);", // mirror sideways (sky + lawn continue); top sky row extends upward
    " vec3 day=texture2D(tDay,c).rgb; vec3 off=texture2D(tOff,c).rgb; vec3 lit=texture2D(tLit,c).rgb; vec4 m=texture2D(tMap,c);",
    " float dusk=smoothstep(0.,.32,p);",                  // phase 1: day falls to dusk
    " float q=clamp((p-.3)/.7,0.,1.);",                   // phase 2: lights switch on
    " vec3 base=mix(day,off,dusk);",
    " float soft=mix(.12,.016,m.g);",
    " float a=smoothstep(m.r-.004,m.r+soft,q);",
    " a=max(a,smoothstep(.93,1.,q));",
    " vec3 col=mix(base,lit,a);",
    " col+=lit*m.g*a*(1.-a)*1.3;",                       // brief ignition flare as a bulb comes on
    " vec2 v=fc/res-.5; col*=1.-dot(v,v)*mix(.25,.5,dusk);",// lens vignette, stronger at night
    " col+=(h(fc+seed)-.5)*mix(.012,.03,dusk);",          // fine grain, mostly in the dark
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

  let iw = 1870, ih = 840, W = 0, H = 0, dpr = 1;
  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const cw = canvas.clientWidth, ch = canvas.clientHeight;
    const scale = Math.min(dpr, 2200 / Math.max(cw, 1));
    W = Math.round(cw * scale); H = Math.round(ch * scale);
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    if (gl) gl.viewport(0, 0, W, H);
  }
  function layout(p) {
    const z = 1 + 0.05 * p;                              // slow dolly-in as night falls
    if (W / H < 0.9) {                                   // portrait: the house (right half of the photo) large and centred
      const w = W * 1.9 * z, h = w * ih / iw;
      return [W * 0.5 - w * 0.715, H * 0.56 - h * 0.5, w, h];
    }
    // landscape: house on the right, open sky behind the headline; bottom-anchored,
    // the sky's top row extends upward and the lawn/sky mirror sideways if needed
    const s = Math.max(W / iw, (H * 0.86) / ih) * z;
    const w = iw * s, h = ih * s;
    return [W - w, H - h, w, h];
  }
  // text scrim: light and sky-tinted by day, full strength once it's dark
  const setNight = (p) => { const t = clamp(p / 0.32, 0, 1); hero.style.setProperty("--night", (t * t * (3 - 2 * t)).toFixed(3)); };
  const lightsOn = (p) => clamp((p - 0.3) / 0.7, 0, 1);

  function draw(p) {
    if (fallback) { fallback.style.opacity = p; setNight(p); setMeter(lightsOn(p)); return; }
    if (!ready) return;
    gl.uniform1f(U.p, p);
    gl.uniform1f(U.seed, (p * 977) % 97);
    const r = layout(p);
    gl.uniform4fv(U.rect, r);
    gl.uniform2f(U.res, W, H);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
    setNight(p);
    setMeter(lightsOn(p));
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
    // No WebGL: cross-fade the real day and night photos.
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
      ["tDay", "tOff", "tLit", "tMap", "p", "seed", "rect", "res"].forEach((n) => (U[n] = gl.getUniformLocation(prog, n)));
      const [day, off, lit, map] = await Promise.all(["day.jpg", "off.jpg", "lit.jpg", "map.png"].map((f) => loadImg("images/hero/" + f)));
      iw = lit.naturalWidth; ih = lit.naturalHeight;
      tex(day, 0); tex(off, 1); tex(lit, 2); tex(map, 3);
      gl.uniform1i(U.tDay, 0); gl.uniform1i(U.tOff, 1); gl.uniform1i(U.tLit, 2); gl.uniform1i(U.tMap, 3);
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
