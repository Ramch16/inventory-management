(function () {
  document.documentElement.classList.add("js");
  const $ = (s, r = document) => r.querySelector(s);
  const S = window.SITE, PHOTOS = window.PHOTOS || [];
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const photo = (slug) => PHOTOS.find((p) => p.slug === slug) || { alt: "", w: 4, h: 3 };

  /* ---------- nav + call bar ---------- */
  const nav = $(".nav"), callbar = $("#callbar"), heroTrack = $("#heroTrack");
  function onScroll() {
    const y = window.scrollY;
    nav.classList.toggle("is-solid", y > 40);
    callbar.classList.toggle("is-on", y > heroTrack.offsetHeight - window.innerHeight * 0.5);
  }
  window.addEventListener("scroll", onScroll, { passive: true }); onScroll();
  // the quote section has its own call/quote actions, so tuck the bar away there
  new IntersectionObserver((es) => callbar.classList.toggle("is-away", es[0].isIntersecting), { threshold: 0.15 }).observe(document.getElementById("quote"));

  /* ---------- services ---------- */
  const serviceSelect = $("#fService");
  function addOptions(label, list, prefix) {
    const g = document.createElement("optgroup"); g.label = label;
    list.forEach((s) => { const o = document.createElement("option"); o.value = prefix + s.name; o.textContent = s.name; g.appendChild(o); });
    serviceSelect.appendChild(g);
  }
  addOptions("Holiday lighting", S.holiday, "Holiday: ");
  addOptions("Roofing & snow", S.roofing, "Roofing: ");
  addOptions("Handyman", S.handyman, "Handyman: ");
  const other = document.createElement("option"); other.value = "Other / several jobs"; other.textContent = "Other / several jobs"; serviceSelect.appendChild(other);

  const PREFIX = { holiday: "Holiday: ", roofing: "Roofing: ", handy: "Handyman: " };
  function card(s, kind) {
    const p = photo(s.photo);
    const el = document.createElement("article");
    el.className = `card reveal ${kind === "holiday" ? "card--night tone-" + s.tone : "card--handy"}`;
    el.innerHTML = `
      <div class="card__media"><img src="images/${s.photo}-sm.jpg" alt="${esc(p.alt)}" width="640" height="${Math.round(640 * p.h / p.w)}" loading="lazy" decoding="async"></div>
      <div class="card__body">
        <h3>${esc(s.name)}</h3>
        <p>${esc(s.text)}</p>
        <span class="card__cta" aria-hidden="true">Request this</span>
      </div>
      <button type="button" class="card__btn"><span class="sr-only">Request a quote for ${esc(s.name)}</span></button>`;
    el.querySelector(".card__btn").addEventListener("click", () => prefill(PREFIX[kind] + s.name));
    return el;
  }
  const hc = $("#holidayCards"), dc = $("#handyCards");
  S.holiday.forEach((s) => hc.appendChild(card(s, "holiday")));
  S.handyman.forEach((s) => dc.appendChild(card(s, "handy")));
  const rc = $("#roofCards");
  S.roofing.forEach((s) => rc.appendChild(card(s, "roofing")));
  const fs = $("#footerServices");
  ["Holiday light installation", "Light takedown & packing", ...S.roofing.map((s) => s.name), ...S.handyman.slice(0, 5).map((s) => s.name)].forEach((n) => { const li = document.createElement("li"); li.textContent = n; fs.appendChild(li); });

  function prefill(value) {
    serviceSelect.value = value;
    serviceSelect.closest(".field").classList.remove("is-invalid");
    $("#quote").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    setTimeout(() => $("#fName").focus({ preventScroll: true }), 700);
  }

  /* ---------- gallery ---------- */
  const CATS = { holiday: "Holiday lighting", roofing: "Roofing & snow", interior: "Repairs & interiors", outdoor: "Outdoor" };
  PHOTOS.forEach((p) => { if (p.cat === "tools") p.cat = "interior"; });
  const items = PHOTOS.filter((p) => CATS[p.cat]);
  const grid = $("#galleryGrid"), chips = $("#galleryChips"), more = $("#galleryMore");
  let filter = "all", expanded = false, shown = [];
  if (!S.samplePhotos) $("#galleryNote").hidden = true;

  items.forEach((p, i) => {
    const li = document.createElement("li");
    const r = p.w / p.h;
    if (r < 0.85) li.classList.add("tall"); else if (r > 1.6) li.classList.add("wide");
    li.dataset.cat = p.cat;
    li.innerHTML = `<button type="button" aria-label="Open photo: ${esc(p.alt)}"><img src="images/${p.slug}-sm.jpg" alt="${esc(p.alt)}" width="640" height="${Math.round(640 / r)}" loading="lazy" decoding="async"></button>`;
    li.querySelector("button").addEventListener("click", () => openLB(shown.indexOf(p)));
    li._p = p;
    grid.appendChild(li);
  });
  const chipDefs = [["all", "All", items.length], ...Object.keys(CATS).map((k) => [k, CATS[k], items.filter((p) => p.cat === k).length]).filter((c) => c[2])];
  chipDefs.forEach(([k, label, n]) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "chip"; b.setAttribute("aria-pressed", k === "all");
    b.innerHTML = `${label} <b>${n}</b>`;
    b.addEventListener("click", () => { filter = k; expanded = false; chips.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", c === b)); applyGallery(); });
    chips.appendChild(b);
  });
  function applyGallery() {
    let n = 0; shown = [];
    grid.querySelectorAll("li").forEach((li) => {
      const match = filter === "all" || li.dataset.cat === filter;
      const vis = match && (expanded || n < 12);
      if (match) n++;
      li.hidden = !vis;
      if (vis) shown.push(li._p);
    });
    more.hidden = expanded || n <= 12;
    more.textContent = `Show all ${n} photos`;
  }
  more.addEventListener("click", () => { expanded = true; applyGallery(); });
  applyGallery();

  /* ---------- lightbox (small image first, then large) ---------- */
  const lb = $("#lightbox"), lbImg = $("#lbImg"), lbCap = $("#lbCap"), lbCredit = $("#lbCredit"), lbCount = $("#lbCount");
  let cur = 0, lastFocus = null;
  function show(i) {
    cur = (i + shown.length) % shown.length;
    const p = shown[cur];
    lbImg.classList.add("is-loading");
    lbImg.src = `images/${p.slug}-sm.jpg`; lbImg.alt = p.alt;
    const big = new Image(); big.onload = () => { if (shown[cur] === p) { lbImg.src = big.src; lbImg.classList.remove("is-loading"); } };
    big.src = `images/${p.slug}-lg.jpg`;
    lbCap.textContent = p.alt;
    lbCredit.innerHTML = `Photo: ${esc(p.artist)} · ${esc(p.license)} · <a href="${esc(p.page)}" target="_blank" rel="noopener">source</a>`;
    lbCount.textContent = `${cur + 1} / ${shown.length}`;
  }
  function openLB(i) { lastFocus = document.activeElement; show(i); if (lb.showModal) lb.showModal(); else lb.setAttribute("open", ""); $("#lbClose").focus(); }
  function closeLB() { lb.close ? lb.close() : lb.removeAttribute("open"); }
  lb.addEventListener("close", () => lastFocus && lastFocus.focus());
  $("#lbClose").addEventListener("click", closeLB);
  $("#lbPrev").addEventListener("click", () => show(cur - 1));
  $("#lbNext").addEventListener("click", () => show(cur + 1));
  lb.addEventListener("click", (e) => { if (e.target === lb || e.target.tagName === "FIGURE") closeLB(); });
  lb.addEventListener("keydown", (e) => { if (e.key === "ArrowLeft") show(cur - 1); if (e.key === "ArrowRight") show(cur + 1); });
  let sx = null;
  lb.addEventListener("touchstart", (e) => (sx = e.touches[0].clientX), { passive: true });
  lb.addEventListener("touchend", (e) => { if (sx === null) return; const dx = e.changedTouches[0].clientX - sx; if (Math.abs(dx) > 50) show(cur + (dx < 0 ? 1 : -1)); sx = null; });

  /* ---------- reviews + trust (only render real data) ---------- */
  if (S.reviews && S.reviews.length) {
    $("#reviews").hidden = false;
    $("#reviewList").innerHTML = S.reviews.map((r) => `<figure class="review reveal">${r.rating ? `<div class="review__stars" aria-label="${r.rating} out of 5 stars">${"★".repeat(r.rating)}</div>` : ""}<blockquote>“${esc(r.text)}”</blockquote><cite>${esc(r.name)}${r.source ? " · " + esc(r.source) : ""}</cite></figure>`).join("");
  }
  if (S.trust && S.trust.length) {
    $("#trust").hidden = false;
    $("#badgeList").innerHTML = S.trust.map((t) => `<li><b>${esc(t.title)}</b><span>${esc(t.text || "")}</span></li>`).join("");
  }

  /* ---------- reveal on scroll ---------- */
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("is-in"); io.unobserve(e.target); } }), { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
  document.querySelectorAll(".reveal").forEach((el, i) => { el.style.transitionDelay = (el.classList.contains("card") ? (i % 3) * 70 : 0) + "ms"; io.observe(el); });

  /* ---------- form ---------- */
  const form = $("#quoteForm"), status = $("#formStatus"), submit = $("#fSubmit");
  const today = new Date(); $("#fDate").min = new Date(today - today.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
  $("#year").textContent = today.getFullYear();
  const messages = { name: "Please add your name.", phone: "Please add a phone number we can reach you on.", email: "That email doesn’t look right.", zip: "Please enter a 5-digit ZIP code.", service: "Please choose a service." };
  function check(el) {
    const f = el.closest(".field"); if (!f) return true;
    let ok = el.checkValidity(), msg = messages[el.name] || "";
    if (el.name === "phone" && el.value && (el.value.match(/\d/g) || []).length < 7) ok = false;
    if (el.type === "file" && el.files[0] && el.files[0].size > 5 * 1024 * 1024) { ok = false; msg = "That photo is over 5 MB. Please choose a smaller one."; }
    f.classList.toggle("is-invalid", !ok);
    f.querySelector(".err") && (f.querySelector(".err").textContent = ok ? "" : msg);
    el.setAttribute("aria-invalid", !ok);
    return ok;
  }
  form.querySelectorAll("input:not([type=hidden]),select").forEach((el) => {
    el.addEventListener("blur", () => el.value && check(el));
    el.addEventListener("change", () => check(el));
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fields = [...form.querySelectorAll(".field input, .field select")];
    const bad = fields.filter((el) => !check(el));
    if (bad.length) { bad[0].focus(); status.textContent = "Please check the highlighted fields."; status.className = "form__status is-error"; return; }
    submit.disabled = true; submit.textContent = "Sending…"; status.textContent = ""; status.className = "form__status";
    try {
      const res = await fetch("/", { method: "POST", body: new FormData(form) });
      if (!res.ok) throw new Error(res.status);
      form.hidden = true;
      const ok = $("#formSuccess"); ok.hidden = false; ok.focus();
    } catch (err) {
      status.innerHTML = 'Sorry, that didn’t send. Please try again, or call <a href="tel:+15550100199">(555) 010-0199</a>.';
      status.className = "form__status is-error";
    } finally { submit.disabled = false; submit.textContent = "Send quote request"; }
  });
})();
