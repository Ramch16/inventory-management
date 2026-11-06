# Build the day -> dusk -> lights-on hero from two ALIGNED photos of the same house (same framing).
#   pip install pillow numpy scipy
#   python3 build_hero_daynight.py day.jpg night_lit.jpg ../handyman-holiday-site/images/hero
# Outputs: day.jpg, off.jpg (dusk, lights still off), lit.jpg (real night photo),
#          map.png (R = when each pixel switches on, G = how bulb-like it is), lit-sm.jpg
import sys, numpy as np
from PIL import Image
from scipy import ndimage as nd
day_p, night_p, out = sys.argv[1:4]
D = Image.open(day_p).convert("RGB"); N = Image.open(night_p).convert("RGB")
if D.size != N.size: D = D.resize(N.size, Image.LANCZOS)
if N.width > 1920:
    N = N.resize((1920, round(N.height*1920/N.width)), Image.LANCZOS); D = D.resize(N.size, Image.LANCZOS)
d = np.asarray(D).astype(np.float32)/255; n = np.asarray(N).astype(np.float32)/255
H, W, _ = n.shape; k = W/1870
lum = lambda a: 0.2126*a[...,0]+0.7152*a[...,1]+0.0722*a[...,2]

# --- sky mask from the day photo (clear blue sky), softened
sky = ((d[...,2]-d[...,0]) > 0.18) & (d[...,2] > 0.55)
sky = nd.binary_opening(sky, iterations=2)
lab, nlab = nd.label(sky)                      # keep only regions touching the top edge
top = set(np.unique(lab[0])) - {0}
sky = np.isin(lab, list(top))
skyf = np.clip(nd.gaussian_filter(sky.astype(np.float32), 2*k), 0, 1)[..., None]

# --- dusk, lights off: day photo graded down to blue hour, night sky dropped in
Y = lum(d)[..., None]
dusk = (Y*0.55 + d*0.45)               # partial desaturation
dusk = np.power(dusk, 1.15) * np.array([0.20, 0.235, 0.36]) + 0.006
dusk = dusk*(1-skyf) + n*0.92*skyf     # the real night sky
# a touch of residual skylight on the upper walls/roofs so the house still reads
dusk += (1-skyf) * np.linspace(0.02, 0, H)[:, None, None] * np.array([0.4, 0.5, 1.0])
dusk = np.clip(dusk, 0, 1)

# --- bulbs in the night photo
Yn = lum(n); loc = nd.gaussian_filter(Yn, 4*k)
mask = ((Yn > 0.72) & ((Yn-loc) > 0.05)) | (Yn > 0.95)
mask &= ~sky
mask = nd.binary_opening(mask, iterations=1)
mask = nd.binary_dilation(mask, iterations=max(1, int(1.2*k)))
mf = mask.astype(np.float32)

# --- switch-on order: left-to-right along the rooflines, then down the facade, garden last
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
sweep = 0.68*(xx/W) + 0.32*(yy/H)
cw, ch = max(4, int(W*0.009)), max(4, int(H*0.03))
cx, cy = xx//cw, yy//ch
rnd = np.sin(cx*12.9898 + cy*78.233)*43758.5453; rnd -= np.floor(rnd)
order_b = 0.68*((cx+.5)*cw/W) + 0.32*((cy+.5)*ch/H) + (rnd-.5)*0.05
num = nd.gaussian_filter(mf*order_b, 26*k); den = nd.gaussian_filter(mf, 26*k)
glow = np.where(den > 0.002, num/np.maximum(den, 1e-6), sweep) + 0.035
w8 = np.clip(den/0.02, 0, 1); glow = glow*w8 + (sweep+0.06)*(1-w8)
order = np.where(mask, order_b, glow)
order = np.where(sky, 0.0, order)       # the sky is already night after the dusk phase
lo, hi = np.percentile(order[~sky], 0.5), np.percentile(order[~sky], 99.5)
order = np.where(sky, 0.0, np.clip((order-lo)/(hi-lo), 0, 1)*0.86 + 0.04)
bulb = np.clip(nd.gaussian_filter(mf, 0.8*k), 0, 1)

save = lambda a, f, q=84: Image.fromarray((np.clip(a, 0, 1)*255+.5).astype(np.uint8)).save(f"{out}/{f}", quality=q, optimize=True, progressive=True)
save(d, "day.jpg"); save(dusk, "off.jpg"); save(n, "lit.jpg")
Image.fromarray((np.stack([order, bulb, np.zeros_like(order)], -1)*255+.5).astype(np.uint8)).resize((W//2, H//2), Image.BILINEAR).save(f"{out}/map.png", optimize=True)
Image.fromarray((n*255+.5).astype(np.uint8)).resize((640, round(640*H/W)), Image.LANCZOS).save(f"{out}/lit-sm.jpg", quality=78)
print(W, H, "bulb%", round(mf.mean()*100, 2), "sky%", round(sky.mean()*100, 1))
