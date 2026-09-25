# Bevnetic POS — clickable UI/UX prototype

A single-file, no-build prototype of the liquor store POS, based on the
*POS Proposed Feature Deck (12 Aug 2026)*. Open `index.html` in any browser.
All figures are demo data.

## Screens

| Screen | Deck page | What you can try |
| --- | --- | --- |
| Command Center | p.11 | KPI strip, AI "5 things today" list; every item links to the screen that fixes it |
| Register | p.2–5 | Add items, offers applied automatically, line or whole-sale discounts (manager PIN over 15%, blocked over 30% so alcohol never sells below cost), 21+ lock, ID scan (pass and underage demo), card / tap / cash / split tender, CRV + tax |
| Damaged Goods | p.7 (extended) | Report breakage / expiry / returns with photo, stock adjusts, supplier claims move Draft → Submitted → Credited, damage log, loss pattern |
| Inventory | p.9–10 | Heat map filtered by state, tile detail, AI action list |
| Forecasting | p.8 | 28-day history + 14-day forecast band, stockout marker, drivers, reorder recommendation |
| Invoices | p.6 | 8-step flow, OCR source view, per-line approve / edit / reject, price and quantity variances |
| Alerts | p.7 | All 7 alert types with resolving actions and filters |
| Customers | p.2 | Member profile, AI segments, SMS campaign preview |
| Offers & Discounts | p.2 (extended) | Offer cards with pause/activate (changes the register live), AI-suggested offers, offer builder with state-rule compliance checks and receipt preview |
| Devices & Offline | p.3–5 | ID provider comparison, lane terminals, offline limits, store-and-forward queue |

## Controls in the top bar

- **Online / Offline pill**: simulates an internet outage. The register keeps
  selling, cards are queued (limit $250 per sale), and reconnecting uploads the queue.
- **Pencil**: wireframe notes mode. Shows the deck reference, data on screen and
  build notes for each screen, and outlines each component with its label.
- **Moon / sun**: light and dark theme.

## Moving to the real application

The notes mode on each screen lists the API calls and integrations that screen
needs. The sample data at the top of the `<script>` block (`PRODUCTS`, `HEAT`,
`FC`, `INVOICE`, `ALERTS`) is shaped like the payloads the backend should return.
