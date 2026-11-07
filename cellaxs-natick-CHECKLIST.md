# Cellaxs Natick: confirm with the client before going live

This file sits outside `cellaxs-natick/` on purpose so it never gets deployed.

## Facts taken from their sites (please confirm)
- Phone **508-893-4214**, address **1245 Worcester St, STE #1022, Natick, MA 01760** (Natick Mall). Source: cellaxs.com Natick page.
- Hours: Mon–Thu 11–7, Fri–Sat 11–8, Sun 11–6. Source: the same page. Check these against current mall hours and holidays.
- Service list: the old cellaxs.com lists iPhone, iPad and Samsung Galaxy repair plus unlocking. The newer cellaxsrepair.com lists Screen, Battery, Water Damage, Charging Port, MacBook, Back Glass, PS5, Camera and Apple Watch repair, and used phones. Confirm all of these are offered **at Natick**.
- The warranty wording on each service is quoted from cellaxsrepair.com, including "OLED screens include lifetime warranty…". Confirm it is current.
- Trust claims used: free evaluation/diagnostics, OEM-quality parts, parts & workmanship guarantee, repairs while you wait. All appear on their sites.
- "Back in your hand the same visit" and "Most common repairs are done while you wait" paraphrase their "fast repairs while you wait". Confirm.
- "Area served" wording: **Natick & Greater Boston, MA**. Confirm it's what they want.

## Not used, because it couldn't be verified
- **Email**: hello@cellaxsrepair.com appears only next to placeholder data (a 555 phone number and a Los Angeles address). It is hidden until confirmed; set `email` in `js/content.js`.
- **Reviews**: the only review on their page (Michael Ford, 5★) talks about a shop near the Miami airport, so it was left out. The section stays hidden until real Natick reviews go into the `reviews` array in `js/content.js`.
- **Used phone listings and prices** on cellaxsrepair.com are placeholder data, so none are shown.
- **Prices**: neither site lists real prices, so no estimator numbers are shown. The planner books a free evaluation instead.
- "Certified techs" and "under an hour" claims on cellaxsrepair.com were not used.
- An AI-generated illustration on cellaxsrepair.com (`trust-*.jpeg`) was left out of the gallery.

## Photos needed
These services reuse a general bench/parts photo and need a real one: **MacBook, PS5, Apple Watch, Phone Unlocking, Used Phones** (`photoNote: true` in `content.js`). Photos of the actual Natick kiosk or store front would help a lot.

The hero now uses the two phone images you supplied (cracked and intact). Only the screen is taken from the intact image, so the background doesn't shift during the scroll. These are not the client's own photos and look computer-generated; confirm the client is happy to use them, and that you have the rights to them.

## Before going live
1. Deploy `cellaxs-natick/` to Netlify, then turn on form notifications (Forms → estimate → email to the owner).
2. Send one test form with a photo. Netlify's free plan has monthly submission limits.
3. Add the real domain to `og:image` and JSON-LD (they need absolute URLs) and add a `<link rel="canonical">`.
4. Confirm the Google Maps pin lands on the store inside the mall.
5. Optional: a privacy policy page (the old site had one).
