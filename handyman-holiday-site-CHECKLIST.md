# Lumen & Level site: client checklist (before going live)

The site is in `handyman-holiday-site/`. It has **not been deployed or published** anywhere.

No source website, logo or contact details were supplied, so **every business fact on the page is a placeholder**. Nothing below has been verified.

## 1. Find and replace (all files in `handyman-holiday-site/`)

| Placeholder | Replace with | Where it appears |
|---|---|---|
| `Lumen & Level` / `Lumen &amp; Level` | Real business name | Title, nav, footer, JSON-LD, form text, credits page |
| `(555) 010-0199` | Real phone, display format | Nav, hero, contact list, call bar, form error, footer |
| `+15550100199` / `+1-555-010-0199` | Real phone, tel/JSON format | `tel:` links, JSON-LD |
| `hello@example.com` | Real email | Contact list, footer, JSON-LD |
| `Your City & Surrounding Towns` / `Your City` | Exact service-area wording | Hero, meta description, footer, JSON-LD, map |
| `Mon–Fri 9am–5pm · Sat 9am–1pm` | Real hours | Contact list, footer and JSON-LD `openingHoursSpecification` |
| `https://www.google.com/maps?q=Your%20City&output=embed` | Real town or address | Footer map |

Also: replace the placeholder logo (an SVG house with four bulbs, inline in `index.html` and in `favicon.svg`), and adjust the brand colours in `css/styles.css` (`:root` tokens) to match the real logo.

## 2. The client must confirm

- **Services list and wording** (`js/config.js`): 5 holiday and 11 handyman services, all drafted generically. Remove anything they don't offer.
  - Electrical (light fixtures, ceiling fans) and plumbing (faucets, toilets, drains) may need a licence in their state. Confirm they're allowed to advertise these.
  - "Takedown & packing": confirm they pack and/or store lights.
  - "Storefront & commercial displays": confirm they take commercial jobs.
- **Promise line**: "Careful hands. Bright, even lines. A clear quote before we start."
- **How it works, step 2**: "send a written price before any work is booked". Confirm that's their process.
- **How it works, step 3**: "leave the place tidy". Confirm.
- **Hero trust row**: "Design, install & takedown", "Repairs big and small". Confirm they do all of these.
- **Reviews**: hidden. Add **real** reviews only (first name + last initial) to `reviews: []` in `js/config.js`, and the section appears automatically.
- **Trust badges**: hidden. Add only claims they can prove (insured, licence number, years in business, guarantees) to `trust: []` in `js/config.js`.

## 3. Photos (important)

- **None of the photos are the client's work.** They're openly licensed images from Wikimedia Commons and Flickr (via Openverse), used as placeholders. The gallery says so publicly and links to `credits.html`.
- Several are CC BY / CC BY-SA, so **keep `credits.html` linked** while any of them remain. Two are U.S. military public-domain photos: fine to use, but they must not imply endorsement.
- Replace them with the client's own job photos as soon as possible. After that, set `samplePhotos: false` in `js/config.js` and update `js/photos.js` (slug, category, alt text).
- **Hero photo resolution:** Wikimedia rate-limited downloads, so the hero source is only 960 px wide. Film grain and a dark grade hide most of this, but it's softer than ideal on large screens. Best fix: one sharp night photo of a house the client has lit, run through `handyman-holiday-site-tools/build_hero.py`.
- Designer sample houses (`sample-cottage`, `sample-green-house`) are also placeholders. If they're swapped, the preset strand coordinates in `js/designer.js` (`SAMPLES`) need updating.

## 4. Left to do before launch

1. Complete sections 1–3 above.
2. Deploy to Netlify (drag-and-drop the folder works; no build step).
3. Netlify → Forms: confirm the `quote` form was detected. Add an email notification to the client's inbox. Note the limit of 8 MB per submission (customer photo + design image).
4. Test a real submission on the live URL. Locally the form shows its error state, because a plain local server can't accept the POST.
5. Add the production domain: absolute `og:image` URL, `"url"` and full address/geo in the JSON-LD (if they have a public address), plus `robots.txt`, `sitemap.xml` and `404.html`.
6. Test on a real mid-range phone (hero scroll, light designer, photo upload from the camera roll).
