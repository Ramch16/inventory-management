/*
  Cellaxs — Natick Mall
  ---------------------------------------------------------------
  All editable business content lives in this file. Change it here
  and the page re-renders; no HTML editing needed.

  Sources (copied Nov 2026):
    [N] cellaxs.com/locations/cellaxs-phone-repair-in-natick-mall-ma/
    [H] cellaxs.com (home page)
    [R] cellaxsrepair.com (newer site)
  Anything marked CONFIRM has not been verified with the owner.
*/
window.SITE = {
  name: "Cellaxs",
  longName: "Cellaxs Phone Repair — Natick Mall",
  phone: "508-893-4214",                      // [N]
  phoneHref: "+15088934214",
  email: "",                                  // CONFIRM: only hello@cellaxsrepair.com appears, next to placeholder data on [R]. Left blank until confirmed.
  address: {
    street: "1245 Worcester St, STE #1022",   // [N]
    city: "Natick",
    region: "MA",
    zip: "01760",
    place: "Natick Mall"
  },
  area: "Natick & Greater Boston, MA",        // wording based on [N]: "Natick, greater Boston area of Massachusetts"
  mapQuery: "Cellaxs, Natick Mall, 1245 Worcester St, Natick, MA 01760",
  timezone: "America/New_York",

  // [N] Store Hours. CONFIRM: check against current Natick Mall hours and holidays.
  hours: [
    { day: 0, label: "Sunday",    open: "11:00", close: "18:00" },
    { day: 1, label: "Monday",    open: "11:00", close: "19:00" },
    { day: 2, label: "Tuesday",   open: "11:00", close: "19:00" },
    { day: 3, label: "Wednesday", open: "11:00", close: "19:00" },
    { day: 4, label: "Thursday",  open: "11:00", close: "19:00" },
    { day: 5, label: "Friday",    open: "11:00", close: "20:00" },
    { day: 6, label: "Saturday",  open: "11:00", close: "20:00" }
  ],

  /*
    Services. Names come from [N] and [R]. Warranty notes are quoted from [R].
    No prices are shown: neither site lists real prices.
    "photoNote" marks cards that reuse a general photo; replace when the shop sends real ones.
  */
  services: [
    { id: "screen", name: "Screen Repair", device: ["iphone", "samsung", "android"], img: "cracked-screen",
      line: "Cracked glass or a dead touch layer replaced, fitted flush and tested before you pick it up.",
      warranty: "OLED screens include lifetime warranty for defects and touch issues. Accidental damage, cracks, water, or physical damage are not covered." },
    { id: "iphone", name: "iPhone Repair", device: ["iphone"], img: "iphone-cracked",
      line: "Older models and newer ones: broken screens, dead buttons, antenna faults and the rest.",
      warranty: "" },
    { id: "ipad", name: "iPad Repair", device: ["ipad"], img: "ipad-cracked",
      line: "Original iPad, iPad mini and iPad Air screens, glass and buttons, with a free evaluation first.",
      warranty: "" },
    { id: "samsung", name: "Samsung Galaxy Repair", device: ["samsung"], img: "galaxy-cracked",
      line: "Most flagship Galaxy phones, repaired with OEM Samsung screens so colour and brightness match.",
      warranty: "" },
    { id: "battery", name: "Battery Replacement", device: ["iphone", "samsung", "android", "ipad", "watch"], img: "part-battery",
      line: "A fresh battery, installed and health-tested, so the phone lasts the day again.",
      warranty: "" },
    { id: "water", name: "Water Damage Repair", device: ["iphone", "samsung", "android", "ipad", "watch"], img: "logic-board",
      line: "Board-level diagnosis and ultrasonic cleaning for devices that met water, coffee or worse.",
      warranty: "Water damage repairs cover the completed repair only. New corrosion, repeat liquid exposure, and unrelated component failures are excluded." },
    { id: "port", name: "Charging Port Repair", device: ["iphone", "samsung", "android", "ipad"], img: "part-port",
      line: "A loose, slow or dead connector replaced so charging, syncing and accessories work again.",
      warranty: "Charging port repairs include a workmanship warranty for charging and data connection faults related to the replaced part. Bent pins, debris, and physical damage are excluded." },
    { id: "camera", name: "Camera Repair", device: ["iphone", "samsung", "android", "ipad"], img: "part-camera",
      line: "Front and rear cameras restored and checked for focus, stabilisation and a clean sensor.",
      warranty: "Camera repairs include warranty coverage for focus and image issues tied to the replaced module. Lens scratches, impact damage, and moisture intrusion are excluded." },
    { id: "backglass", name: "Back Glass Repair", device: ["iphone", "samsung"], img: "part-backglass",
      line: "Shattered rear glass on iPhone and premium Samsung models taken off and replaced.",
      warranty: "Back glass repairs are covered for installation defects only. New cracks, drops, frame bends, and impact damage are excluded." },
    { id: "macbook", name: "MacBook Repair", device: ["macbook"], img: "technician-bench", photoNote: true,
      line: "Hardware faults on MacBook Air and MacBook Pro traced to the part and fixed there.",
      warranty: "MacBook repairs include warranty coverage only for the replaced component and labor performed. Liquid damage, accidental damage, and unrelated future faults are not covered." },
    { id: "ps5", name: "PS5 Repair", device: ["ps5"], img: "bench-tools", photoNote: true,
      line: "HDMI port, overheating, fan and power faults on PlayStation 5 consoles.",
      warranty: "PS5 repairs include warranty coverage for the repaired fault only. Surge damage, liquid exposure, overheating caused by dust buildup, and new impact damage are excluded." },
    { id: "watch", name: "Apple Watch Repair", device: ["watch"], img: "iphone-parts", photoNote: true,
      line: "Screens, batteries and liquid damage on recent Apple Watch models.",
      warranty: "Apple Watch repairs cover the replaced part and labor only. New cracks, water ingress after impact, and housing damage are not covered." },
    { id: "unlock", name: "Phone Unlocking", device: ["iphone", "samsung", "android"], img: "apple-lineup", photoNote: true,
      line: "Ask us whether your phone can be unlocked to use with another carrier.",
      warranty: "" },
    { id: "diagnostics", name: "Free Evaluation & Diagnostics", device: ["iphone", "samsung", "android", "ipad", "macbook", "watch", "ps5"], img: "technician-bench",
      line: "Not sure it can be saved? We look at it for free and tell you straight.",
      warranty: "" },
    { id: "used", name: "Used Phones for Sale", device: [], img: "apple-lineup", photoNote: true,
      line: "Tested pre-owned phones in store. Call to ask what is in stock today.",
      warranty: "" }
  ],

  // Gallery = every real photo taken from their sites. tag drives the filter chips.
  gallery: [
    { img: "technician-bench", tag: "At the bench", alt: "Technician in gloves working on an opened iPhone at a repair bench" },
    { img: "bench-tools",      tag: "At the bench", alt: "Hands opening a cracked white iPhone with precision screwdrivers on a wooden bench" },
    { img: "cracked-screen",   tag: "Broken screens", alt: "Hand holding an iPhone with a badly shattered screen" },
    { img: "iphone-cracked",   tag: "Broken screens", alt: "Two iPhones with cracked front glass" },
    { img: "ipad-cracked",     tag: "Broken screens", alt: "iPad and iPad mini, one with a shattered display" },
    { img: "galaxy-cracked",   tag: "Broken screens", alt: "Samsung Galaxy phone with a cracked screen, front and back" },
    { img: "iphone-parts",     tag: "Parts", alt: "iPhone taken apart: battery, logic board, display, charging flex and housing laid out" },
    { img: "logic-board",      tag: "Parts", alt: "Close view of a phone logic board inside its frame" },
    { img: "apple-lineup",     tag: "Devices", alt: "Line-up of iPads and iPhones of different generations" }
  ],

  /*
    Reviews: real ones only, first name + last initial.
    The section stays hidden while this array is empty.
    NOTE: the Natick page shows one 5-star review ("Michael Ford, Reviewer on Google"),
    but its text describes a shop near the Miami airport, so it was left out.
    Example entry: { name: "Jane D.", stars: 5, text: "…", source: "Google" }
  */
  reviews: [],

  // Only claims the business makes on its own sites.
  trust: [
    { title: "Free evaluation", text: "Free diagnostics on most devices, iPhones included, before you commit to anything." },
    { title: "OEM-quality parts", text: "Original-manufacturer and OEM-quality parts, so screens keep the same colour and touch." },
    { title: "Parts & workmanship guarantee", text: "Every repair is backed by the Cellaxs repair guarantee on parts and workmanship." },
    { title: "Fixed while you wait", text: "Walk in at Natick Mall and wait for most common repairs." }
  ],
  disclaimer: "Cellaxs is an independent repair shop and is not affiliated with, endorsed by, or an authorized service center for Apple, Samsung, Google, Sony or any other manufacturer."
};
