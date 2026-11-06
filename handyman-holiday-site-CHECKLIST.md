# Metro West All Power Handyman Services: client checklist (before going live)

The site is in `handyman-holiday-site/`. It has **not been deployed or published** anywhere.

The **name and logo** come from the client's logo ("Metro West All Power Handyman Services", "Est. 2023"), and the site colours are taken from it (navy `#1a3a59`, copper `#c07f55`). No contact details or website were supplied, so **everything else is still a placeholder**. Nothing below has been verified.

## 1. Find and replace (all files in `handyman-holiday-site/`)

| Placeholder | Replace with | Where it appears |
|---|---|---|
| `(555) 010-0199` | Real phone, display format | Nav, hero, contact list, call bar, form error, footer |
| `+15550100199` / `+1-555-010-0199` | Real phone, tel/JSON format | `tel:` links, JSON-LD |
| `hello@example.com` | Real email | Contact list, footer, JSON-LD |
| `Your City & Surrounding Towns` / `Your City` | Exact service-area wording | Hero, meta description, footer, JSON-LD, map |
| `Mon–Fri 9am–5pm · Sat 9am–1pm` | Real hours | Contact list, footer and JSON-LD `openingHoursSpecification` |
| `https://www.google.com/maps?q=Your%20City&output=embed` | Real town or address | Footer map |

Logo files (made from the supplied logo): `images/logo.png`, `logo-240.png` and `logo-480.png` (original colours, transparent). The nav and footer show them on a cream tile so the navy lettering stays clear on the dark design. Also `favicon-32.png`, `favicon-48.png` and `apple-touch-icon.png`. If the client has a vector (SVG/AI/EPS) version, swap it in for a sharper result.

- **Service area:** the logo says "Metro West". Confirm the exact area wording (for example "MetroWest, Massachusetts" or specific towns) and use it everywhere `Your City & Surrounding Towns` appears.
- **"Est. 2023"** is on the logo and is in the JSON-LD as `foundingDate`. If the client wants it, it can also go in `trust` in `js/config.js`.

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
- **Hero images (client-supplied day + night pair):** the hero scrolls from the day photo, through dusk, to the night photo with the lights switching on. Confirm the client has the rights to use these two images. If they're renders or concept images rather than a real job, the client should be comfortable presenting them as illustrative. To swap in a new aligned pair, run `handyman-holiday-site-tools/build_hero_daynight.py day.jpg night.jpg ../handyman-holiday-site/images/hero`.

## 4. Left to do before launch

1. Complete sections 1–3 above.
2. Deploy to Netlify (drag-and-drop the folder works; no build step).
3. Netlify → Forms: confirm the `quote` form was detected. Add an email notification to the client's inbox. Note the limit of 8 MB per submission (the customer's photo).
4. Test a real submission on the live URL. Locally the form shows its error state, because a plain local server can't accept the POST.
5. Add the production domain: absolute `og:image` URL, `"url"` and full address/geo in the JSON-LD (if they have a public address), plus `robots.txt`, `sitemap.xml` and `404.html`.
6. Test on a real mid-range phone (hero scroll, photo upload from the camera roll).
