# Bevnetic POS — clickable UI/UX prototype

A single-file, no-build prototype of the liquor store POS, based on the
*POS Proposed Feature Deck (12 Aug 2026)*. Open `index.html` in any browser.
All figures are demo data.

## Screens

| Screen | Deck page | What you can try |
| --- | --- | --- |
| Reports | New | End of day (Z-report; X-report while the day is open): gross → net sales, tax, CRV, payments by type, cash drawer float / paid outs / safe drops / expected / counted / over-short, activity, ID checks, sales by hour / category / cashier; Date range (day-by-day table + chart + totals); Monthly (12 months vs last year, margin, basket); Yearly; Accounting & tax (QuickBooks / Xero connection, sales tax report for the month ready for the CDTFA return, balanced daily journal entry). Print preview in full page or 80 mm receipt format (simulated in the online preview; prints for real when index.html is opened in a browser); email at close toggle |
| All Stores | New | Head office view for several stores: store switcher in the top bar (owners switch; managers and cashiers are tied to their store). Overview compares each store live (sales today vs last Friday, margin, staff on shift, over/short, low stock, alerts, online or offline with queued cards) plus a 7-day sales table. Stock & transfers: stock of any product at every store, AI "move stock before you reorder" suggestions, transfers Requested → Picked → In transit → Received that move the stock. Prices & offers: same prices everywhere or per store, price differences highlighted, match all to head office, pick which stores run each offer. Store setup: licence, tax rate (switching store changes the tax on the register), lanes, manager; add a store by copying another's setup. The register's sold-out window shows which store has it |
| Customer Display | New | The screen facing the customer mirrors the register live: offers while waiting, then each item, savings, CRV, tax, total, "Please have your ID ready" and rewards sign-up; the amount due and tap prompt while paying; then the receipt choice (Text, Email, Print, No receipt; walk-in customers type their number or email). Preview any stage, switch what the customer sees, and see the digital receipt (text or email, return barcode, savings, next-visit offer, rating). A monitor button on the Register shows a small live customer screen over the till, including during payment. Members can get their receipt texted automatically; Sales & Returns shows how each receipt was sent and resends it by text or email |
| Sign-in and roles | New | Top-bar user button: pick a person and enter a PIN (demo PINs shown). Owner sees everything, manager everything except Store Settings, cashier only Register, Sales & Returns, Shifts, Damaged Goods and Receiving; other screens show "A manager needs to open this" |
| Shifts & Staff | New | Open the till by counting the float; close it with a blind count (expected cash shown only after submitting, over/short added to history); time clock with weekly hours; cashiers see only their own clock and no cash history; "Who can do what" table built from the same access rules the app enforces (every screen per role, plus actions that need a manager PIN or go to a manager), with your own role highlighted |
| Sales & Returns | New | Find any sale by receipt #, card, product or cashier; reprint the receipt; return items to the original payment or store credit, or exchange (credit applied on the Register); reason decides back-on-shelf vs Damaged Goods; manager PIN over $50 for cashiers |
| Receiving & Counts | New | Receive a PO case by case (scan, received, damaged); completing updates stock, keeps short POs open and opens supplier claims for damage. Count stock by area with live differences; a manager approves the adjustment, recorded as shrink |
| Store Settings | New | Store details (shown on receipts and the menu), sales tax % (used by the next sale), CRV rates, alcohol sale hours, receipt header/footer with preview, users and roles, printers |
| Command Center | p.11 | KPI strip, AI "5 things today" list; every item links to the screen that fixes it; weekly vendor deals summary |
| Register | p.2–5 | Product cards with drawn bottle and package art, separate Mixers and Snacks tabs (chips, jerky, nuts, candy, cups), a "No tax" badge on items that aren't taxed (tax is worked out only on taxable items) and quantity left in inventory on every card (green in stock, orange only X left, red out of stock; counts down as items go into the order, can't add more than on hand, stock drops when the sale completes), category counts, AI add-on suggestions, sold-out swap to the best alternative, one-tap refuse sale, after-hours lock. Add items, offers applied automatically, line or whole-sale discounts (manager PIN over 15%, blocked over 30% so alcohol never sells below cost), 21+ lock, scan by barcode (an unknown barcode opens a window to link it to an existing product, suggesting products with the same maker's prefix; try "Demo: new label"), ID scan (pass and underage demo), no-scan options: approve by eye when the customer is clearly over the store's age (logged) and type the date of birth when an ID won't scan (manager PIN, under-21 always blocked), card / tap / cash / split tender, CRV + tax |
| Purchasing | New | Deal check: each product comes from its one distributor; compare that vendor's options (buy just what you need, or each of its deals: free cases, discounted extra case, volume tiers) as the real cost per case. AI picks the option and quantity with the lowest cost per case without more than 30 days of extra stock, and flags deal traps. Different products from different vendors are grouped into one draft PO per vendor. PO tracker. Vendor deals tab: drop a deal sheet or flyer, forward rep emails, or let reps post in a vendor portal; AI reads each line, matches it to the catalog and says whether it is the best option, not worth it, a price increase or a product you don't sell; confirmed deals raise alerts |
| Vendors | New | Vendor list with search, amount owed and on-time rate; vendor detail with licence, contact, terms, delivery days, minimum order, balance, products supplied, purchase orders and active deals. Add vendor form: licence check (required), rep, email, terms, delivery days, how POs are sent, products they supply; warns when a brand moves from its current distributor and hands it over in Deal check |
| Pricing | New | New costs from vendor POs, price sheets and invoices → cost per unit → suggested shelf price from the product's target margin: a product rule beats a brand/group rule, which beats the category default (all editable; AI suggests product margins; the Inventory detail shows each product's target), .99 or .49 endings, 10% change flag, below-cost block; margin and markup shown; approve now or at 6 AM; register updates and shelf tags are queued for the label printer |
| Damaged Goods | p.7 (extended) | Report breakage / expiry / returns with photo, stock adjusts, supplier claims move Draft → Submitted → Credited, damage log, loss pattern |
| Compliance | New | Legal sale-hours timeline with demo clock (locks the register after 2 AM), rules the register enforces, store ID policy switch (scan everyone / under 40 / under 30), log of sales without an ID scan, cashier scorecard, refusal log, inspection report |
| Inventory | p.9–10 | + Add product form (also opened from an invoice line or an unknown barcode; cashiers send it to a manager): pick what you're adding (spirits, wine, beer & seltzer, mixers & ice, snacks) and the form sets sensible defaults for size, vendor, reorder point and package; name, brand, size, ABV (hidden for mixers and snacks, which sell any hour with no ID), 21+ and taxable switches (snacks default to not taxed as food in California; cups and other non-food can be switched on; ice and fruit not taxed), CRV worked out from size and pack for beer and mixer drink containers only, barcodes and vendor code, vendor with one-distributor warning, case cost → cost per unit → suggested shelf price from the target margin (editable, never below cost), starting stock, reorder point, location, bottle shape or snack package (chip bag, pouch, jar, candy bar, cups, soda bottle, fruit, ice bag) and colours with a live register-card preview; "Fill in with AI" recognises snacks and mixers from the name; duplicate check offers "Use existing instead"; saved products appear on the Register, in Inventory, Pricing tags and the vendor's list. Heat map filtered by state; each product holds several codes (store SKU, bottle and case barcodes, vendor item codes) shown in the detail panel; possible duplicates are flagged and can be merged (stock, codes and history combined); each tile shows stock left, days left, vendor and last order (date · quantity); tile detail adds reorder point, delivery time, open order, cost / price / margin and last sale, with Reorder; List view shows the same details as a table sorted by urgency; AI action list |
| Forecasting | p.8 | 28-day history + 14-day forecast band, stockout marker, drivers, reorder recommendation |
| Shelf Optimizer | New (extends p.9–10) | Dead stock: each product with no sale in months gets a clearance plan and a replacement that sells on the same shelf in similar stores, with profit per month; one tap starts the clearance offer and adds a trial case to a draft PO. Best sellers: top 10 by profit, revenue or units over 7 / 30 / 90 days, trend, days of stock left, reorder buttons |
| Invoices | p.6 | 8-step flow, OCR source view, per-line approve / edit / reject, price and quantity variances; an unknown item code that looks like an existing product gets "Link to existing product" (saves the code to that product) or "It's a new product" |
| Alerts | p.7 | All 7 alert types plus vendor deal alerts, with resolving actions and filters |
| Customers | p.2 | Member profile, AI segments, SMS campaign preview |
| Offers & Discounts | p.2 (extended) | Offer cards with pause/activate (changes the register live), AI-suggested offers, offer builder with state-rule compliance checks and receipt preview |
| Devices & Offline | p.3–5 | ID provider comparison, lane terminals, offline limits, store-and-forward queue |

## Guided demo

Press **▶ Demo** in the top bar (or open the page with `#demo` at the end of the URL).
A 22-step tour opens each screen, sets up the example, highlights the feature and shows
presenter notes under "What to say". Use **Next / Back** or the arrow keys; everything
stays clickable during the tour. The story runs:

1. Morning briefing → 2. End of day report → 3. All stores → 4. Shifts and blind count → 5. Alerts → 6. Forecast →
7. Deal check → 8. Deal trap skipped → 9. Vendor deals from a deal sheet → 10. Vendors → 11. AI invoice →
12. New costs become shelf prices → 13. Liquor checkout → 14. Customer display and digital receipt → 15. Sold-out swap → 16. ID check →
17. Offline payment → 18. Returns and exchanges → 19. Compliance lock → 20. Damaged goods →
21. Dead stock swaps → 22. Inventory details

## Controls in the top bar

- **Store pill**: switch between stores (owners) or open the All Stores view.
- **Online / Offline pill**: simulates an internet outage. The register keeps
  selling, cards are queued (limit $250 per sale), and reconnecting uploads the queue.
- **Pencil**: wireframe notes mode. Shows the deck reference, data on screen and
  build notes for each screen, and outlines each component with its label.
- **Moon / sun**: light and dark theme.

## Moving to the real application

The notes mode on each screen lists the API calls and integrations that screen
needs. The sample data at the top of the `<script>` block (`PRODUCTS`, `HEAT`,
`FC`, `INVOICE`, `ALERTS`) is shaped like the payloads the backend should return.
