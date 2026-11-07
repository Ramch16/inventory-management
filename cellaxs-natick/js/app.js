(() => {
  "use strict";
  const S = window.SITE;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const el = (tag, attrs = {}, html) => {
    const n = document.createElement(tag);
    for (const k in attrs) {
      if (k === "class") n.className = attrs[k];
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== false && attrs[k] != null) n.setAttribute(k, attrs[k] === true ? "" : attrs[k]);
    }
    if (html != null) n.innerHTML = html;
    return n;
  };
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const img = (name, size) => `images/${name}-${size}.jpg`;
  const serviceById = Object.fromEntries(S.services.map((s) => [s.id, s]));

  /* ---------------- shop clock (always Natick time) ---------------- */
  const toMin = (hhmm) => { const [h, m] = hhmm.split(":").map(Number); return h * 60 + m; };
  const fmtTime = (min) => {
    const h = Math.floor(min / 60), m = min % 60, ap = h >= 12 ? "PM" : "AM";
    return `${((h + 11) % 12) + 1}${m ? ":" + String(m).padStart(2, "0") : ""} ${ap}`;
  };
  function shopNow() {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: S.timezone, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23", weekday: "short"
    }).formatToParts(new Date());
    const p = Object.fromEntries(parts.map((x) => [x.type, x.value]));
    const y = +p.year, mo = +p.month, d = +p.day;
    return { y, mo, d, dow: new Date(Date.UTC(y, mo - 1, d)).getUTCDay(), min: (+p.hour % 24) * 60 + +p.minute };
  }
  const hoursFor = (dow) => S.hours.find((h) => h.day === dow);

  function openStatus() {
    const n = shopNow(), h = hoursFor(n.dow);
    if (h && n.min >= toMin(h.open) && n.min < toMin(h.close)) return { open: true, text: `Open now · until ${fmtTime(toMin(h.close))}` };
    for (let i = 0; i < 8; i++) {
      const dow = (n.dow + i) % 7, hh = hoursFor(dow);
      if (!hh) continue;
      if (i === 0 && n.min >= toMin(hh.open)) continue;
      const when = i === 0 ? "today" : i === 1 ? "tomorrow" : hh.label;
      return { open: false, text: `Closed · opens ${when} ${fmtTime(toMin(hh.open))}` };
    }
    return { open: false, text: "" };
  }
  function paintStatus() {
    const st = openStatus();
    $$("[data-open-status]").forEach((n) => { n.textContent = st.text; n.classList.toggle("is-open", st.open); });
  }

  /* ---------------- static content from content.js ---------------- */
  function renderContent() {
    $$("[data-area]").forEach((n) => (n.textContent = S.area));
    if (S.email) {
      $$("[data-email]").forEach((a) => { a.href = "mailto:" + S.email; a.textContent = S.email; });
      $$("[data-email-wrap]").forEach((n) => (n.hidden = false));
    }
    $("#year").textContent = new Date().getFullYear();

    const tb = $("#hoursTable tbody"), today = shopNow().dow;
    [1, 2, 3, 4, 5, 6, 0].forEach((d) => {
      const h = hoursFor(d);
      const tr = el("tr", { class: d === today ? "is-today" : "" },
        `<td>${h.label}</td><td>${h ? fmtTime(toMin(h.open)) + " – " + fmtTime(toMin(h.close)) : "Closed"}</td>`);
      tb.append(tr);
    });

    const list = $("#servicesList"), sel = $("#qService"), foot = $("#footServices");
    S.services.forEach((s, i) => {
      const li = el("li", { class: "svc reveal", "data-id": s.id });
      li.innerHTML = `<button type="button" aria-label="${esc(s.name)}: add to my estimate request">
          <div class="svc__img"><img src="${img(s.img, "sm")}" alt="" loading="lazy" decoding="async" width="640" height="480"></div>
          <div class="svc__body">
            <h3 class="svc__name">${esc(s.name)}<small>${String(i + 1).padStart(2, "0")}</small></h3>
            <p class="svc__line">${esc(s.line)}</p>
            <span class="svc__cta">Ask about this</span>
          </div></button>`;
      li.firstElementChild.addEventListener("click", () => chooseService(s.id, { scroll: true }));
      list.append(li);
      sel.append(el("option", { value: s.name }, esc(s.name)));
      foot.append(el("li", {}, `<a href="#services">${esc(s.name)}</a>`));
    });

    const trust = $("#trustList");
    S.trust.forEach((t) => trust.append(el("li", { class: "reveal" }, `<h3>${esc(t.title)}</h3><p>${esc(t.text)}</p>`)));
    $("#disclaimer").textContent = S.disclaimer;

    if (S.reviews && S.reviews.length) {
      const rl = $("#rList");
      S.reviews.forEach((r) => rl.append(el("li", { class: "review reveal" },
        `<div class="review__stars" aria-label="${r.stars} out of 5 stars">${"★".repeat(r.stars)}</div>
         <blockquote>${esc(r.text)}</blockquote><cite>${esc(r.name)} <span>· ${esc(r.source || "")}</span></cite>`)));
      $("#reviews").hidden = false;
    }
  }

  /* ---------------- pick a service → form ---------------- */
  function chooseService(id, { scroll } = {}) {
    const s = serviceById[id];
    if (!s) return;
    $("#qService").value = s.name;
    $$(".svc").forEach((n) => n.classList.toggle("is-picked", n.dataset.id === id));
    showChosen();
    if (scroll) goToForm();
  }
  function showChosen(extra) {
    const box = $("#qChosen"), svc = $("#qService").value;
    if (!svc) { box.hidden = true; return; }
    box.innerHTML = `<b>Selected</b>${esc(svc)}${extra ? "<br>" + esc(extra) : ""}`;
    box.hidden = false;
  }
  function goToForm() {
    $("#quote").scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
    setTimeout(() => $("input[name=name]").focus({ preventScroll: true }), reduced ? 0 : 650);
  }

  /* ---------------- HERO: screen replacement scrub ---------------- */
  function hero() {
    const canvas = $("#heroCanvas"), track = $("#heroTrack");
    const ctx = canvas.getContext("2d");
    const off = document.createElement("canvas"), octx = off.getContext("2d");
    const IW = 1672, IH = 941;
    // glass outline in source-image pixels (used for the light sweep)
    const GLASS = [[790,108],[1044,110],[1066,128],[1072,160],[1072,770],[1062,800],[1040,816],[790,816],[768,800],[762,770],[762,160],[770,128]];
    const A = [917, 104], B = [917, 820]; // phone's long axis, top → bottom
    const pics = ["images/hero-cracked.jpg", "images/hero-repaired.jpg"].map((src) => { const i = new Image(); i.decoding = "async"; i.src = src; return i; });
    let W = 0, H = 0, dpr = 1, target = 0, cur = 0, raf = 0, visible = true, ready = false;
    const meterFill = $("#meterFill"), meterPct = $("#meterPct"), meterLabel = $("#meterLabel"), hint = $("#heroHint");

    // film grain tile (generated once, tiny)
    const g = document.createElement("canvas"); g.width = g.height = 180;
    const gx = g.getContext("2d"), id = gx.createImageData(180, 180);
    for (let i = 0; i < id.data.length; i += 4) { const v = Math.random() * 255; id.data[i] = id.data[i + 1] = id.data[i + 2] = v; id.data[i + 3] = 255; }
    gx.putImageData(id, 0, 0);
    $(".grain").style.backgroundImage = `url(${g.toDataURL()})`;

    function size() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = canvas.clientWidth; H = canvas.clientHeight;
      canvas.width = off.width = Math.round(W * dpr);
      canvas.height = off.height = Math.round(H * dpr);
      draw(cur);
    }
    function view(p) {
      if (W < 760) {
        // portrait: show the whole phone, centred, above the copy
        const s = Math.min((W * 0.62) / 330, (H * 0.42) / 720) * (1 + 0.04 * p);
        const top = 100;
        return { s, ox: W / 2 - 915 * s, oy: top - 100 * s, mobile: true };
      }
      const zoom = 1 + 0.07 * p;
      const s = Math.max(W / IW, H / IH) * zoom;
      const fx = 915, fy = 465, tx = 0.68, ty = 0.52;
      let ox = W * tx - fx * s, oy = H * ty - fy * s;
      ox = Math.min(0, Math.max(W - IW * s, ox));
      oy = Math.min(0, Math.max(H - IH * s, oy));
      return { s, ox, oy, mobile: false };
    }
    const ease = (t) => 0.55 * t + 0.45 * t * t * (3 - 2 * t);
    function draw(raw) {
      if (!ready || !W) return;
      const p = reduced ? 1 : ease(Math.min(1, Math.max(0, (raw - 0.04) / 0.86)));
      const { s, ox, oy, mobile } = view(p);
      const T = (x, y) => [(ox + x * s) * dpr, (oy + y * s) * dpr];
      const dw = IW * s * dpr, dh = IH * s * dpr, dx = ox * dpr, dy = oy * dpr;

      ctx.globalCompositeOperation = "source-over";
      if (mobile) { ctx.fillStyle = "#0d0d0e"; ctx.fillRect(0, 0, canvas.width, canvas.height); }
      ctx.drawImage(pics[0], dx, dy, dw, dh);

      if (p > 0) {
        // new panel: repaired photo, revealed along the phone's axis with a soft edge
        const [ax, ay] = T(...A), [bx, by] = T(...B);
        octx.globalCompositeOperation = "source-over";
        octx.clearRect(0, 0, off.width, off.height);
        octx.drawImage(pics[1], dx, dy, dw, dh);
        octx.globalCompositeOperation = "destination-in";
        const f = 0.05, e = p * (1 + 2 * f) - f;
        const gr = octx.createLinearGradient(ax, ay, bx, by);
        gr.addColorStop(0, "#000");
        gr.addColorStop(Math.min(1, Math.max(0, e - f)), "#000");
        gr.addColorStop(Math.min(1, Math.max(0, e + f)), "rgba(0,0,0,0)");
        gr.addColorStop(1, "rgba(0,0,0,0)");
        octx.fillStyle = gr;
        octx.fillRect(0, 0, off.width, off.height);
        ctx.drawImage(off, 0, 0);

        // light catching the edge of the new glass
        const glint = Math.sin(Math.PI * Math.min(1, p * 1.02)) * 0.55;
        if (glint > 0.01) {
          ctx.save();
          ctx.beginPath();
          GLASS.forEach(([x, y], i) => { const [cx, cy] = T(x, y); i ? ctx.lineTo(cx, cy) : ctx.moveTo(cx, cy); });
          ctx.closePath(); ctx.clip();
          const lg = ctx.createLinearGradient(ax, ay, bx, by), w = 0.018;
          const c = (v) => Math.min(1, Math.max(0, v));
          lg.addColorStop(0, "rgba(255,255,255,0)");
          lg.addColorStop(c(e - w * 2.5), "rgba(255,255,255,0)");
          lg.addColorStop(c(e - w * 0.3), `rgba(220,232,255,${0.22 * glint})`);
          lg.addColorStop(c(e), `rgba(255,255,255,${0.5 * glint})`);
          lg.addColorStop(c(e + w * 0.6), "rgba(255,255,255,0)");
          lg.addColorStop(1, "rgba(255,255,255,0)");
          ctx.globalCompositeOperation = "screen";
          ctx.fillStyle = lg;
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.restore();
        }
      }
      if (mobile) {
        // feather the photo's top and bottom edges into the dark stage
        const fade = (y0, y1) => { const g = ctx.createLinearGradient(0, y0, 0, y1); g.addColorStop(0, "rgba(13,13,14,1)"); g.addColorStop(1, "rgba(13,13,14,0)"); return g; };
        ctx.globalCompositeOperation = "source-over";
        ctx.fillStyle = fade(dy, dy + 70 * dpr); ctx.fillRect(0, dy, canvas.width, 70 * dpr);
        ctx.fillStyle = fade(dy + dh, dy + dh - 110 * dpr); ctx.fillRect(0, dy + dh - 110 * dpr, canvas.width, 110 * dpr);
        ctx.fillStyle = "#0d0d0e";
        if (dy > 0) ctx.fillRect(0, 0, canvas.width, dy + 1);
        ctx.fillRect(0, dy + dh - 2, canvas.width, canvas.height);
      }
      const pct = Math.round(p * 100);
      meterFill.style.transform = `scaleX(${p})`;
      meterPct.textContent = pct + "%";
      meterLabel.textContent = pct < 3 ? "Cracked glass" : pct < 97 ? "Fitting new screen" : "Screen replaced";
      hint.style.opacity = raw > 0.03 ? 0 : 1;
    }
    function readScroll() {
      const r = track.getBoundingClientRect();
      const span = track.offsetHeight - window.innerHeight;
      target = span > 0 ? Math.min(1, Math.max(0, -r.top / span)) : 1;
    }
    function tick() {
      raf = 0;
      const d = target - cur;
      cur = Math.abs(d) < 0.0008 ? target : cur + d * 0.14;
      draw(cur);
      if (cur !== target && visible) raf = requestAnimationFrame(tick);
    }
    const kick = () => { if (!raf && visible) raf = requestAnimationFrame(tick); };

    Promise.all(pics.map((i) => (i.decode ? i.decode().catch(() => {}) : Promise.resolve()))).then(() => {
      ready = true; readScroll(); cur = target; size();
    });
    new IntersectionObserver(([en]) => { visible = en.isIntersecting; if (visible) { readScroll(); kick(); } }).observe(track);
    addEventListener("scroll", () => { readScroll(); kick(); }, { passive: true });
    let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { readScroll(); size(); }, 80); });
  }

  /* ---------------- repair planner ---------------- */
  function planner() {
    const DEVICES = [
      { id: "iphone", label: "iPhone" }, { id: "samsung", label: "Samsung Galaxy" }, { id: "android", label: "Other Android" },
      { id: "ipad", label: "iPad" }, { id: "macbook", label: "MacBook" }, { id: "watch", label: "Apple Watch" }, { id: "ps5", label: "PS5" }
    ];
    const MODELS = {
      iphone: ["iPhone 17 Pro Max","iPhone 17 Pro","iPhone 17","iPhone Air","iPhone 16 Pro Max","iPhone 16 Pro","iPhone 16 Plus","iPhone 16","iPhone 16e","iPhone 15 Pro Max","iPhone 15 Pro","iPhone 15 Plus","iPhone 15","iPhone 14 Pro Max","iPhone 14 Pro","iPhone 14 Plus","iPhone 14","iPhone 13 Pro Max","iPhone 13 Pro","iPhone 13","iPhone 13 mini","iPhone 12 Pro Max","iPhone 12 Pro","iPhone 12","iPhone 12 mini","iPhone 11 Pro Max","iPhone 11 Pro","iPhone 11","iPhone XS Max","iPhone XS","iPhone XR","iPhone X","iPhone SE (3rd gen)","iPhone SE (2nd gen)","iPhone 8 Plus","iPhone 8"],
      samsung: ["Galaxy S25 Ultra","Galaxy S25+","Galaxy S25","Galaxy S24 Ultra","Galaxy S24+","Galaxy S24","Galaxy S23 Ultra","Galaxy S23","Galaxy S22 Ultra","Galaxy S22","Galaxy S21","Galaxy Z Flip","Galaxy Z Fold","Galaxy A series","Galaxy Note"],
      android: ["Google Pixel","LG","Motorola","OnePlus"],
      ipad: ["iPad","iPad mini","iPad Air","iPad Pro"],
      macbook: ["MacBook Air","MacBook Pro"],
      watch: ["Apple Watch Series","Apple Watch SE","Apple Watch Ultra"],
      ps5: ["PS5 (disc)","PS5 Digital Edition","PS5 Slim","PS5 Pro"]
    };
    const PHONES = ["iphone", "samsung", "android"];
    // issue → service id, per device (falls back to "diagnostics")
    const ISSUES = [
      { id: "cracked", label: "Cracked screen", for: [...PHONES, "ipad", "watch", "macbook"], map: { iphone: "screen", samsung: "screen", android: "screen", ipad: "ipad", watch: "watch", macbook: "macbook" } },
      { id: "display", label: "Lines / black display", for: [...PHONES, "ipad", "watch", "macbook"], map: { iphone: "screen", samsung: "screen", android: "screen", ipad: "ipad", watch: "watch", macbook: "macbook" } },
      { id: "battery", label: "Battery dies fast", for: [...PHONES, "ipad", "watch", "macbook"], map: { iphone: "battery", samsung: "battery", android: "battery", ipad: "battery", watch: "battery", macbook: "macbook" } },
      { id: "charge", label: "Won't charge", for: [...PHONES, "ipad", "watch", "macbook"], map: { iphone: "port", samsung: "port", android: "port", ipad: "port", watch: "watch", macbook: "macbook" } },
      { id: "water", label: "Got wet", for: [...PHONES, "ipad", "watch", "macbook", "ps5"], map: { iphone: "water", samsung: "water", android: "water", ipad: "water", watch: "water", macbook: "macbook", ps5: "ps5" } },
      { id: "camera", label: "Camera problem", for: [...PHONES, "ipad"], map: { iphone: "camera", samsung: "camera", android: "camera", ipad: "camera" } },
      { id: "back", label: "Cracked back glass", for: ["iphone", "samsung"], map: { iphone: "backglass", samsung: "backglass" } },
      { id: "buttons", label: "Buttons, speaker or mic", for: [...PHONES, "ipad"], map: { iphone: "iphone", samsung: "samsung", android: "diagnostics", ipad: "ipad" } },
      { id: "hdmi", label: "No picture on TV", for: ["ps5"], map: { ps5: "ps5" } },
      { id: "heat", label: "Overheating or loud fan", for: ["ps5", "macbook"], map: { ps5: "ps5", macbook: "macbook" } },
      { id: "power", label: "Won't turn on", for: [...PHONES, "ipad", "watch", "macbook", "ps5"], map: { macbook: "macbook", ps5: "ps5" } },
      { id: "unlock", label: "Needs unlocking", for: PHONES, map: { iphone: "unlock", samsung: "unlock", android: "unlock" } },
      { id: "unsure", label: "Not sure", for: [...PHONES, "ipad", "watch", "macbook", "ps5"], map: {} }
    ];
    const st = { device: null, issues: [], day: null, slot: null };
    const devBox = $("#pDevice"), issBox = $("#pIssue"), daysBox = $("#pDays"), slotBox = $("#pSlots"), model = $("#pModel");

    // radio-group keyboard support (arrow keys move the choice)
    function radioKeys(box, onPick) {
      box.addEventListener("keydown", (e) => {
        const items = $$("[role=radio]:not(:disabled)", box);
        const i = items.indexOf(document.activeElement);
        if (i < 0) return;
        let j = null;
        if (e.key === "ArrowRight" || e.key === "ArrowDown") j = (i + 1) % items.length;
        if (e.key === "ArrowLeft" || e.key === "ArrowUp") j = (i - 1 + items.length) % items.length;
        if (j == null) return;
        e.preventDefault(); items[j].focus(); onPick(items[j]);
      });
    }
    const setRadio = (box, btn) => $$("[role=radio]", box).forEach((b) => { const on = b === btn; b.setAttribute("aria-checked", on); b.tabIndex = on ? 0 : -1; });

    DEVICES.forEach((d, i) => {
      const b = el("button", { type: "button", class: "chip", role: "radio", "aria-checked": "false", tabindex: i ? -1 : 0, "data-id": d.id }, esc(d.label));
      b.addEventListener("click", () => pickDevice(b));
      devBox.append(b);
    });
    radioKeys(devBox, pickDevice);
    function pickDevice(b) {
      setRadio(devBox, b);
      st.device = b.dataset.id;
      st.issues = st.issues.filter((id) => ISSUES.find((x) => x.id === id).for.includes(st.device));
      $("#modelList").innerHTML = (MODELS[st.device] || []).map((m) => `<option value="${esc(m)}">`).join("");
      renderIssues(); update();
    }
    function renderIssues() {
      issBox.innerHTML = "";
      const list = st.device ? ISSUES.filter((x) => x.for.includes(st.device)) : ISSUES.filter((x) => ["cracked", "battery", "charge", "water", "unsure"].includes(x.id));
      list.forEach((x) => {
        const b = el("button", { type: "button", class: "chip", "aria-pressed": st.issues.includes(x.id) ? "true" : "false" }, esc(x.label));
        b.addEventListener("click", () => {
          if (x.id === "unsure") st.issues = st.issues.includes("unsure") ? [] : ["unsure"];
          else {
            st.issues = st.issues.filter((i) => i !== "unsure");
            st.issues = st.issues.includes(x.id) ? st.issues.filter((i) => i !== x.id) : [...st.issues, x.id];
          }
          renderIssues(); update();
        });
        issBox.append(b);
      });
    }

    // drop-off days: next 8 days in shop time
    const now = shopNow();
    const days = [];
    for (let i = 0; i < 8; i++) {
      const dt = new Date(Date.UTC(now.y, now.mo - 1, now.d + i, 12));
      const dow = dt.getUTCDay(), h = hoursFor(dow);
      const slots = [];
      if (h) for (let m = toMin(h.open); m <= toMin(h.close) - 60; m += 30) if (i > 0 || m >= now.min + 30) slots.push(m);
      days.push({
        iso: dt.toISOString().slice(0, 10), slots,
        wk: i === 0 ? "Today" : i === 1 ? "Tmrw" : dt.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" }),
        num: dt.getUTCDate(),
        long: dt.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric", timeZone: "UTC" })
      });
    }
    days.forEach((d, i) => {
      const b = el("button", { type: "button", class: "day", role: "radio", "aria-checked": "false", tabindex: -1, disabled: !d.slots.length, "data-i": i,
        "aria-label": d.long + (d.slots.length ? "" : ", no times left") }, `<small>${d.wk}</small><b>${d.num}</b>`);
      b.addEventListener("click", () => pickDay(b));
      daysBox.append(b);
    });
    radioKeys(daysBox, pickDay);
    function pickDay(b) {
      setRadio(daysBox, b);
      st.day = days[+b.dataset.i]; st.slot = null;
      slotBox.innerHTML = "";
      st.day.slots.forEach((m, i) => {
        const s = el("button", { type: "button", class: "slot", role: "radio", "aria-checked": "false", tabindex: i ? -1 : 0, "data-m": m }, fmtTime(m));
        s.addEventListener("click", () => pickSlot(s));
        slotBox.append(s);
      });
      update();
    }
    radioKeys(slotBox, pickSlot);
    function pickSlot(s) { setRadio(slotBox, s); st.slot = +s.dataset.m; update(); }
    const firstDay = $(".day:not(:disabled)", daysBox);
    if (firstDay) { firstDay.tabIndex = 0; pickDay(firstDay); }
    model.addEventListener("input", update);

    function services() {
      const ids = st.issues.map((iid) => ISSUES.find((x) => x.id === iid).map[st.device] || "diagnostics");
      return [...new Set(ids.length ? ids : st.device ? [] : [])].map((id) => serviceById[id]).filter(Boolean);
    }
    function update() {
      const dev = DEVICES.find((d) => d.id === st.device);
      const svcs = services();
      $("#tDevice").textContent = dev ? dev.label + (model.value.trim() ? " · " + model.value.trim() : "") : "—";
      $("#tIssue").textContent = st.issues.length ? st.issues.map((i) => ISSUES.find((x) => x.id === i).label).join(", ") : "—";
      $("#tService").textContent = svcs.length ? svcs.map((s) => s.name).join(" + ") : "—";
      $("#tTime").textContent = st.day && st.slot != null ? `${st.day.long}, ${fmtTime(st.slot)}` : st.day ? st.day.long + " · pick a time" : "—";
      const w = svcs.find((s) => s.warranty);
      const wb = $("#tWarranty");
      if (w) { wb.innerHTML = `<b>Warranty · ${esc(w.name)}</b>${esc(w.warranty)}`; wb.hidden = false; } else wb.hidden = true;
      $("#tSend").disabled = !(dev && svcs.length);
    }
    $("#tSend").addEventListener("click", () => {
      const dev = DEVICES.find((d) => d.id === st.device), svcs = services();
      $("#qService").value = svcs[0].name;
      $("#qDevice").value = dev.label + (model.value.trim() ? " · " + model.value.trim() : "");
      const lines = [`Problem: ${$("#tIssue").textContent}`];
      if (svcs.length > 1) lines.push(`Also: ${svcs.slice(1).map((s) => s.name).join(", ")}`);
      if (st.day && st.slot != null) lines.push(`Planned drop-off: ${st.day.long}, ${fmtTime(st.slot)}`);
      const det = $("#qDetails");
      det.value = lines.join("\n") + (det.value && !det.value.startsWith("Problem:") ? "\n\n" + det.value : "");
      if (st.day) $("#qDate").value = st.day.iso;
      if (st.slot != null) $("#qTime").value = fmtTime(st.slot);
      $$(".svc").forEach((n) => n.classList.toggle("is-picked", n.dataset.id === svcs[0].id));
      showChosen(`${$("#qDevice").value}${st.slot != null ? " · " + $("#tTime").textContent : ""}`);
      goToForm();
    });
    renderIssues(); update();
  }

  /* ---------------- gallery + lightbox ---------------- */
  function gallery() {
    const FIRST = 12;
    const items = S.gallery;
    const tags = ["All", ...new Set(items.map((g) => g.tag))];
    let filter = "All", expanded = false, list = items, at = 0;
    const grid = $("#gGrid"), more = $("#gMore"), bar = $("#gFilters");

    tags.forEach((t) => {
      const n = t === "All" ? items.length : items.filter((g) => g.tag === t).length;
      const b = el("button", { type: "button", class: "filter", "aria-pressed": t === filter }, `${esc(t)} <span>${n}</span>`);
      b.addEventListener("click", () => { filter = t; expanded = false; $$(".filter", bar).forEach((x) => x.setAttribute("aria-pressed", x === b)); render(); });
      bar.append(b);
    });
    function render() {
      list = filter === "All" ? items : items.filter((g) => g.tag === filter);
      const shown = expanded ? list : list.slice(0, FIRST);
      grid.innerHTML = "";
      shown.forEach((g, i) => {
        const li = el("li");
        const b = el("button", { type: "button", "aria-label": `Open photo: ${g.alt}` },
          `<img src="${img(g.img, "sm")}" alt="${esc(g.alt)}" loading="lazy" decoding="async" width="640" height="480">`);
        b.addEventListener("click", () => open(i));
        li.append(b); grid.append(li);
      });
      more.hidden = expanded || list.length <= FIRST;
      more.textContent = `Show all ${list.length} photos`;
    }
    more.addEventListener("click", () => { expanded = true; render(); });

    const dlg = $("#lightbox"), lbImg = $("#lbImg"), cap = $("#lbCap");
    let lastFocus = null;
    function show(i) {
      at = (i + list.length) % list.length;
      const g = list[at];
      lbImg.src = img(g.img, "sm"); lbImg.alt = g.alt;
      cap.textContent = `${g.alt} · ${at + 1} / ${list.length}`;
      const big = new Image();
      big.onload = () => { if (list[at] === g) lbImg.src = big.src; };
      big.src = img(g.img, "lg");
    }
    function open(i) {
      lastFocus = document.activeElement;
      show(i);
      if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
      $("#lbClose").focus();
    }
    function close() { dlg.close ? dlg.close() : dlg.removeAttribute("open"); }
    dlg.addEventListener("close", () => lastFocus && lastFocus.focus());
    $("#lbPrev").addEventListener("click", () => show(at - 1));
    $("#lbNext").addEventListener("click", () => show(at + 1));
    $("#lbClose").addEventListener("click", close);
    dlg.addEventListener("click", (e) => { if (e.target === dlg) close(); });
    dlg.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") { e.preventDefault(); show(at - 1); }
      if (e.key === "ArrowRight") { e.preventDefault(); show(at + 1); }
    });
    render();
  }

  /* ---------------- form (Netlify Forms) ---------------- */
  function form() {
    const f = $("#quoteForm"), err = $("#qError"), btn = $("#qSubmit"), done = $("#qDone");
    $("#qDate").min = (() => { const n = shopNow(); return `${n.y}-${String(n.mo).padStart(2, "0")}-${String(n.d).padStart(2, "0")}`; })();
    $("#qService").addEventListener("change", () => {
      const s = S.services.find((x) => x.name === $("#qService").value);
      $$(".svc").forEach((n) => n.classList.toggle("is-picked", !!s && n.dataset.id === s.id));
      showChosen();
    });
    const fail = (msg, field) => {
      err.textContent = msg; err.hidden = false;
      if (field) { field.setAttribute("aria-invalid", "true"); field.focus(); }
    };
    f.addEventListener("input", (e) => e.target.removeAttribute("aria-invalid"));
    f.addEventListener("submit", async (e) => {
      e.preventDefault();
      err.hidden = true;
      $$("[aria-invalid]", f).forEach((n) => n.removeAttribute("aria-invalid"));
      const v = (n) => f.elements[n].value.trim();
      if (!v("name")) return fail("Please add your name.", f.elements.name);
      if (v("phone").replace(/\D/g, "").length < 10) return fail("Please add a phone number we can call or text (10 digits).", f.elements.phone);
      if (v("email") && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v("email"))) return fail("That email address doesn't look right.", f.elements.email);
      if (v("zip") && !/^\d{5}$/.test(v("zip"))) return fail("ZIP code should be 5 digits.", f.elements.zip);
      if (!v("service")) return fail("Please choose a repair (or “Free Evaluation & Diagnostics” if you're not sure).", f.elements.service);
      const file = f.elements.photo.files[0];
      if (file && file.size > 8 * 1024 * 1024) return fail("That photo is over 8 MB. Please choose a smaller one.", f.elements.photo);
      if (file && !file.type.startsWith("image/")) return fail("Please attach an image file.", f.elements.photo);

      btn.disabled = true; btn.textContent = "Sending…";
      try {
        const res = await fetch("/", { method: "POST", body: new FormData(f) });
        if (!res.ok) throw new Error(res.status);
        f.hidden = true; done.hidden = false; done.focus();
      } catch (_) {
        fail("Sorry, your request didn't go through. Please try again, or call us at 508-893-4214.");
      } finally {
        btn.disabled = false; btn.textContent = "Send my request";
      }
    });
  }

  /* ---------------- chrome: nav, call bar, reveals ---------------- */
  function chrome() {
    const nav = $("#nav"), bar = $("#callbar"), track = $("#heroTrack");
    const onScroll = () => {
      const past = track.getBoundingClientRect().bottom < 80;
      nav.classList.toggle("is-solid", past);
      bar.classList.toggle("is-on", track.getBoundingClientRect().bottom < window.innerHeight * 0.5);
    };
    addEventListener("scroll", onScroll, { passive: true }); onScroll();

    if (reduced || !("IntersectionObserver" in window)) { $$(".reveal").forEach((n) => n.classList.add("in")); return; }
    const io = new IntersectionObserver((ents) => ents.forEach((en) => {
      if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
    }), { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    $$(".reveal").forEach((n, i) => { n.style.transitionDelay = `${(i % 3) * 60}ms`; io.observe(n); });
  }

  renderContent();
  paintStatus(); setInterval(paintStatus, 60000);
  hero();
  planner();
  gallery();
  form();
  chrome();
})();
