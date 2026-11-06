# Rebuild the hero from a NEW night photo of the client's own lit-up job:
#   pip install pillow numpy scipy
#   python3 build_hero.py path/to/photo.jpg ../handyman-holiday-site/images/hero
# Outputs lit.jpg, off.jpg (lights removed, dark night grade), map.png (switch-on order) and lit-sm.jpg.
# Tune the crop on the "im.crop" line if the photo has cars or clutter at the bottom.
# Build hero assets: lit.jpg (graded real photo), off.jpg (lights-off dusk), map.png (R=reveal order, G=bulb mask)
import sys, numpy as np
from PIL import Image
from scipy import ndimage as nd
src, out = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGB")
W0,H0 = im.size
im = im.crop((0,0,W0,int(H0*0.90)))           # trim the bottom (parked cars)
if im.width>1920: im = im.resize((1920, round(im.height*1920/im.width)), Image.LANCZOS)
a = np.asarray(im).astype(np.float32)/255.0
H,W,_ = a.shape; k = W/960.0
# --- lit grade: gentle contrast + warmth, keep texture
lit = np.clip((a-0.5)*1.06+0.5,0,1)
lit = np.clip(lit*np.array([1.03,1.0,0.96]),0,1)
Y = 0.2126*lit[...,0]+0.7152*lit[...,1]+0.0722*lit[...,2]
# --- bulb / light-source mask
loc = nd.gaussian_filter(Y, 5*k)
mask = ((Y>0.70)&((Y-loc)>0.06)) | (Y>0.93)
mask = nd.binary_opening(mask, iterations=1)
mask = nd.binary_dilation(mask, iterations=max(1,int(1.5*k)))
mf = mask.astype(np.float32)
# --- lights-off dusk version
base = lit.copy()
# remove bulbs: fill masked pixels with blurred surroundings
wsum = nd.gaussian_filter(1-mf, 6*k)+1e-4
for c in range(3):
    fill = nd.gaussian_filter(base[...,c]*(1-mf), 6*k)/wsum
    base[...,c] = base[...,c]*(1-mf*0.8)+fill*mf*0.8
# the facade is lit by the decorations: crush it to ambient dusk light
Yb = 0.2126*base[...,0]+0.7152*base[...,1]+0.0722*base[...,2]
gray = Yb[...,None]
desat = gray*0.6 + base*0.4
off = np.power(desat,1.35)*0.115 + 0.008
off = off*np.array([0.78,0.90,1.30])               # blue-hour tint
sky = np.linspace(1,0,H)[:,None,None]**2.2          # faint residual skylight at top
off = off + sky*np.array([0.010,0.018,0.040])
off = np.clip(off,0,1)
# --- reveal order: sweep left->right, roofline first, then facade, then garden
yy,xx = np.mgrid[0:H,0:W].astype(np.float32)
xn,yn = xx/W, yy/H
sweep = 0.62*xn + 0.38*yn
cw, ch = max(4,int(W*0.011)), max(4,int(H*0.035))   # "bulb clusters" that pop on together
cx, cy = (xx//cw), (yy//ch)
rnd = np.sin(cx*12.9898+cy*78.233)*43758.5453; rnd = rnd-np.floor(rnd)
cell_sweep = 0.62*((cx+0.5)*cw/W)+0.38*((cy+0.5)*ch/H)
order_b = cell_sweep + (rnd-0.5)*0.05
num = nd.gaussian_filter(mf*order_b, 28*k); den = nd.gaussian_filter(mf, 28*k)
glow = np.where(den>0.002, num/np.maximum(den,1e-6), sweep) + 0.03
w = np.clip(den/0.02,0,1); glow = glow*w + (sweep+0.06)*(1-w)
order = np.where(mask, order_b, glow)
lo,hi = np.percentile(order,0.5), np.percentile(order,99.5)
order = np.clip((order-lo)/(hi-lo),0,1)*0.86+0.03
bulb = np.clip(nd.gaussian_filter(mf,0.8*k),0,1)
Image.fromarray((lit*255+0.5).astype(np.uint8)).save(f"{out}/lit.jpg", quality=84, optimize=True, progressive=True)
Image.fromarray((off*255+0.5).astype(np.uint8)).save(f"{out}/off.jpg", quality=84, optimize=True, progressive=True)
m = np.stack([order, bulb, np.zeros_like(order)],-1)
Image.fromarray((m*255+0.5).astype(np.uint8)).resize((W//2,H//2), Image.BILINEAR).save(f"{out}/map.png", optimize=True)
# small poster for no-JS / reduced motion / mobile first paint
Image.fromarray((lit*255+0.5).astype(np.uint8)).resize((640,round(640*H/W)),Image.LANCZOS).save(f"{out}/lit-sm.jpg",quality=78)
print(W,H,"mask%",round(mf.mean()*100,2))
