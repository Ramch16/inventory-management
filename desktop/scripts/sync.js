// Copies the prototype into app/ for the desktop build:
// - swaps the Google Fonts link for bundled font files, so the app works with no internet
// - replaces the "printing is simulated" notes, since the desktop app prints for real
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const src = path.join(root, '..', 'design', 'pos-wireframes', 'index.html');
const out = path.join(root, 'app');
const fontsOut = path.join(out, 'fonts');
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(fontsOut, { recursive: true });

// family, fontsource package, [weight, style] pairs used by the prototype
const FONTS = [
  ['Saira', 'saira', [[500, 'normal'], [600, 'normal'], [700, 'normal'], [700, 'italic'], [800, 'italic']]],
  ['Manrope', 'manrope', [[400, 'normal'], [500, 'normal'], [600, 'normal'], [700, 'normal']]],
  ['JetBrains Mono', 'jetbrains-mono', [[400, 'normal'], [500, 'normal'], [600, 'normal']]],
];
let css = '';
for (const [family, pkg, faces] of FONTS) {
  const dir = path.join(root, 'node_modules', '@fontsource', pkg, 'files');
  for (const [weight, style] of faces) {
    const file = `${pkg}-latin-${weight}-${style}.woff2`;
    fs.copyFileSync(path.join(dir, file), path.join(fontsOut, file));
    css += `@font-face{font-family:'${family}';font-style:${style};font-weight:${weight};font-display:swap;src:url(fonts/${file}) format('woff2')}\n`;
  }
}
fs.writeFileSync(path.join(out, 'fonts.css'), css);

let html = fs.readFileSync(src, 'utf8');
const fontLinks = /<link rel="preconnect" href="https:\/\/fonts\.googleapis\.com">\s*<link rel="preconnect" href="https:\/\/fonts\.gstatic\.com" crossorigin>\s*<link rel="stylesheet" href="https:\/\/fonts\.googleapis\.com\/css2[^"]*">/;
if (!fontLinks.test(html)) throw new Error('Google Fonts links not found in index.html');
html = html.replace(fontLinks, '<link rel="stylesheet" href="fonts.css">');
html = html.replace('<title>Bevnetic POS Prototype</title>', '<title>Bevnetic POS</title>');

const printNotes = [
  [/This online prototype can’t open your printer, so printing here is simulated\.[^<]*(<span class="mono">index\.html<\/span>[^<]*)?/, 'Prints to the printer you choose in the print window.'],
  ['Printing is simulated in the online prototype. Open index.html in a browser to print for real.', 'Prints to the printer you choose in the print window.'],
];
for (const [from, to] of printNotes) html = html.replace(from, to);

fs.writeFileSync(path.join(out, 'index.html'), html);

// standalone Shelf Labels page, same font swap
const labelsSrc = path.join(root, '..', 'design', 'pos-wireframes', 'shelf-labels.html');
let labels = fs.readFileSync(labelsSrc, 'utf8');
if (!fontLinks.test(labels)) throw new Error('Google Fonts links not found in shelf-labels.html');
fs.writeFileSync(path.join(out, 'shelf-labels.html'), labels.replace(fontLinks, '<link rel="stylesheet" href="fonts.css">'));
console.log(`app/ ready: index.html, shelf-labels.html + ${fs.readdirSync(fontsOut).length} font files`);
