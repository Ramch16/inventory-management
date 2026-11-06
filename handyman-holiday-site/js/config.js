/* ==========================================================================
   SITE CONTENT: edit here.
   Every service below is a DRAFT for the client to confirm (no source website was supplied).
   ========================================================================== */
window.SITE = {
  /* Services. `photo` = file stem in /images (both -sm.jpg and -lg.jpg exist). */
  holiday: [
    { id: "roofline", name: "Roofline & eave lighting", photo: "holiday-roofline", tone: "amber",
      text: "Even, straight runs along gutters, gables and peaks that make the whole house read clearly from the street." },
    { id: "trees", name: "Tree & shrub wrapping", photo: "holiday-tree-trunk", tone: "pine",
      text: "Trunks wrapped tight and branches traced so your trees glow from the ground up." },
    { id: "entry", name: "Wreaths, garland & entryways", photo: "holiday-wreath-red-door", tone: "holly",
      text: "Doors, porches and railings dressed so the welcome starts at the front step." },
    { id: "commercial", name: "Storefront & commercial displays", photo: "holiday-hotel-facade", tone: "ice",
      text: "Shopfronts and entrances lit to stand out on the street after dark." },
    { id: "takedown", name: "Takedown & packing", photo: "holiday-twilight-porch", tone: "plum",
      text: "When the season ends, everything comes down carefully and is packed ready for next year." }
  ],
  /* Roofing & snow: services confirmed by the client. */
  roofing: [
    { id: "rubber", name: "Rubber roof repairs", photo: "roof-rubber-flat",
      text: "Leaks, splits and lifted seams on commercial and residential rubber (EPDM) flat roofs found and repaired." },
    { id: "shingles", name: "Asphalt shingle repair & replacement", photo: "roof-shingles-roofer",
      text: "Missing, cracked or curling shingles replaced, or a full new asphalt shingle roof when repairs no longer make sense." },
    { id: "snow", name: "Roof snow removal", photo: "snow-roof-rake",
      text: "Snow and ice cleared from any type of roof, flat or pitched, home or commercial, before the weight becomes a problem." }
  ],
  handyman: [
    { id: "drywall", name: "Drywall repair", photo: "repair-drywall-ceiling",
      text: "Holes, cracks and water marks patched, taped and sanded until the wall reads as one surface again." },
    { id: "painting", name: "Painting & prep", photo: "repair-wall-prep",
      text: "Walls, trim and doors prepped properly first, so the finish looks clean and lasts." },
    { id: "doors", name: "Doors & trim", photo: "interior-french-doors",
      text: "Sticking doors adjusted, new doors hung and trim fitted with tight, tidy joints." },
    { id: "mounting", name: "TV & wall mounting", photo: "interior-tv-mount",
      text: "TVs, shelves, mirrors and art hung level and fixed into the right anchors for the wall." },
    { id: "fixtures", name: "Light fixtures & ceiling fans", photo: "interior-ceiling-fan",
      text: "Tired fixtures swapped and ceiling fans fitted so rooms feel brighter and cooler." },
    { id: "plumbing", name: "Faucet, toilet & drain fixes", photo: "interior-sink-repair",
      text: "Drips, running toilets and slow drains sorted before they turn into bigger problems." },
    { id: "decks", name: "Deck & railing repair", photo: "outdoor-deck-new",
      text: "Loose boards, wobbly rails and tired steps made solid and safe to use again." },
    { id: "gutters", name: "Gutter cleaning", photo: "outdoor-gutter",
      text: "Leaves and debris cleared so rainwater runs off the roof instead of over it." },
    { id: "washing", name: "Pressure washing", photo: "outdoor-pressure-wash",
      text: "Driveways, paths and decks washed back to a clean, even surface." },
    { id: "assembly", name: "Furniture assembly", photo: "interior-furniture",
      text: "Flat-pack desks, beds and cabinets built square and placed where you want them." },
    { id: "tile", name: "Tile & caulking", photo: "interior-tile-install",
      text: "Cracked tiles replaced and tired caulk renewed around tubs, sinks and counters." }
  ],

  /* REVIEWS: real reviews only, first name + last initial. Section stays hidden while empty.
     Example: { name: "Sam R.", text: "…exact words from the review…", source: "Google", rating: 5 } */
  reviews: [],

  /* TRUST BADGES: only claims the business can prove (license no., insurance, years, guarantees).
     Section stays hidden while empty. Example: { title: "Fully insured", text: "Liability coverage on every job." } */
  trust: [],

  /* Gallery: set to false once the sample photos are replaced with the client's own. */
  samplePhotos: true
};
