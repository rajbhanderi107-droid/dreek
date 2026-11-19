"""Parametric, Vastu-aware furniture layout for the 4BHK duplex (DWG 'b9a43800-4bhk').

Geometry is built in the Unit-A (left unit) frame, in mm, in DWG coordinates.
`compass` maps drawing sides 'T','B','L','R' to compass directions 'N','E','S','W'
as seen from inside that unit.  Unit B is the mirror of Unit A, so it is built with
L/R compass values swapped and then mirrored about the party wall.
"""
import math

# ------------------------------------------------------------------ standards (mm)
KING = (1830, 1980)    # Indian king mattress 72" x 78"
QUEEN = (1525, 1980)   # Indian queen mattress 60" x 78"
FRAME_W, FRAME_L = 100, 150        # bed frame adds to mattress (width, length incl. headboard)
SIDE = 450                          # bedside table 450 x 450
WARD_D = 600                        # wardrobe depth
MIN_PASS = 750                      # minimum clear passage beside furniture
DOOR_ZONE = 900

WOOD = '#efe0c8'; SOFT = '#e6ddd0'; BED = '#f6f1e8'; LINEN = '#ffffff'; STONE = '#e3e3e0'
GREEN = '#cfe3c4'; METAL = '#dfe4ea'; POOJA = '#f7e3b5'


def ft(mm):
    inch = round(mm / 25.4)
    return f"{inch // 12}'{inch % 12}\""


class Layout:
    def __init__(self, compass, unit='A'):
        self.c = compass
        self.unit_name = unit
        self.F = []          # drawing primitives
        self.FOOT = []       # (name, floor, x0, y0, x1, y1, kind)
        self.KEEP = []       # clear zones: (name, floor, shape...)
        self.choices = {}
        self.notes = []
        self.wards = []
        self.placed, self.skipped = [], []
        self.last_bed = None
        self.beds = []
        self.labels = []

    # ---------------------------------------------------------- primitives
    def poly(self, pts, layer, fill=None, closed=True, lw=0.5, ls='-'):
        self.F.append(dict(kind='poly', pts=[tuple(p) for p in pts], layer=layer, fill=fill, closed=closed, lw=lw, ls=ls))

    def circ(self, c, r, layer, fill=None, lw=0.5):
        self.F.append(dict(kind='circle', c=tuple(c), r=r, layer=layer, fill=fill, lw=lw))

    def text(self, p, s, h=110, layer='A-FURN-TEXT', bold=False, color='#333'):
        self.F.append(dict(kind='text', p=tuple(p), s=s, h=h, layer=layer, bold=bold, color=color))

    def rect(self, x0, y0, x1, y1, layer='A-FURN', fill=WOOD, lw=0.5, ls='-'):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer, fill, True, lw, ls)

    def reg(self, name, floor, x0, y0, x1, y1, kind='furn'):
        self.FOOT.append((name, floor, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), kind))

    def frame(self, x0, y0, x1, y1, front):
        return Frame(self, x0, y0, x1, y1, front)

    def dirs(self, side):
        return self.c[side]

    # ---------------------------------------------------------- furniture items
    def bed(self, floor, name, x0, y0, x1, y1, head):
        front = {'W': 'E', 'E': 'W', 'N': 'S', 'S': 'N', 'L': 'E', 'R': 'W', 'T': 'S', 'B': 'N'}[head]
        f = self.frame(x0, y0, x1, y1, front); W, D = f.W, f.D
        f.rect(0, 0, W, D, 'A-FURN-BED', BED, 0.6)
        f.rect(0, 0, W, 90, 'A-FURN-BED', WOOD, 0.6)
        f.rect(50, 90, W - 50, D - 50, 'A-FURN-BED', LINEN, 0.4)
        pw = (W - 100 - 3 * 60) / 2
        for i in range(2):
            u = 50 + 60 + i * (pw + 60)
            f.rect(u, 150, u + pw, 520, 'A-FURN-BED', '#f2ece2', 0.4)
        f.line(50, D * 0.45, W - 50, D * 0.45, 'A-FURN-BED', 0.4)
        f.line(W - 50, D * 0.45, W - 400, D * 0.45 + 350, 'A-FURN-BED', 0.3)
        f.line(W - 400, D * 0.45 + 350, W - 50, D * 0.45 + 350, 'A-FURN-BED', 0.3)
        f.rect(50, D * 0.74, W - 50, D * 0.74 + 260, 'A-FURN-BED', '#e9dcc6', 0.3)
        self.reg(name, floor, x0, y0, x1, y1)
        self.last_bed = (floor, x0, y0, x1, y1, front)
        self.beds.append((name, self.last_bed))
        # premium: full-height fluted / upholstered wall panel behind bed and bedside tables
        n0 = len(self.F)
        f.rect(-SIDE - 120, -70, W + SIDE + 120, 0, 'A-FURN-PANEL', '#c9ab7f', 0.5)
        for k in range(int((W + 2 * SIDE + 240) / 70)):
            u = -SIDE - 120 + 35 + k * 70
            f.line(u, -70, u, 0, 'A-FURN-PANEL', 0.18)
        panel = self.F[n0:]; del self.F[n0:]
        self.F[0:0] = panel

    def bench_for(self, bed):
        floor, x0, y0, x1, y1, front = bed
        f = self.frame(x0, y0, x1, y1, front); W, D = f.W, f.D
        pts = [f.t(150, D + 60), f.t(W - 150, D + 460)]
        bx0, by0 = min(p[0] for p in pts), min(p[1] for p in pts)
        bx1, by1 = max(p[0] for p in pts), max(p[1] for p in pts)
        def draw():
            self.rect(bx0, by0, bx1, by1, 'A-FURN-SOFA', '#d8c8b4', 0.6)
            self.rect(bx0 + 40, by0 + 40, bx1 - 40, by1 - 40, 'A-FURN-SOFA', '#e9dfd2', 0.3)
            self.text(((bx0 + bx1) / 2, (by0 + by1) / 2), 'BENCH', 50)
        return self.optional('bed-end bench', floor, (bx0, by0, bx1, by1), draw)

    def optional(self, name, floor, r, draw, kind='furn'):
        """premium accessory: placed only if it collides with nothing and blocks no clear zone."""
        for it in self.FOOT:
            if it[1] == floor and it[6] == 'furn' and _overlap(r, it[2:6]):
                self.skipped.append(name); return False
        for k in self.KEEP:
            if k[1] != floor: continue
            if (k[2] == 'rect' and _overlap(r, k[3])) or (k[2] == 'arc' and _rect_hits_arc(r, k[3])):
                self.skipped.append(name); return False
        draw(); self.reg(name, floor, *r, kind); self.placed.append(name)
        return True

    def side_table(self, floor, x0, y0, s=SIDE):
        self.rect(x0, y0, x0 + s, y0 + s, 'A-FURN', WOOD)
        self.circ((x0 + s / 2, y0 + s / 2), s * 0.28, 'A-FURN', '#fff', 0.3)
        self.circ((x0 + s / 2, y0 + s / 2), s * 0.10, 'A-FURN', None, 0.3)
        self.reg('side table', floor, x0, y0, x0 + s, y0 + s)

    def wardrobe(self, floor, x0, y0, x1, y1, front, label='WARDROBE', loft=True, sliding=False):
        f = self.frame(x0, y0, x1, y1, front); W, D = f.W, f.D
        f.rect(0, 0, W, D, 'A-FURN-WARD', WOOD, 0.6)
        f.line(0, D - 25, W, D - 25, 'A-FURN-WARD', 0.3)
        if sliding:
            f.line(0, D - 60, W * 0.55, D - 60, 'A-FURN-WARD', 0.3)
        n = max(2, round(W / 500))
        for i in range(1, n):
            f.line(W * i / n, D - 25, W * i / n, D, 'A-FURN-WARD', 0.3)
        f.line(30, D * 0.5, W - 30, D * 0.5, 'A-FURN-WARD', 0.3, '--')
        for i in range(int(W / 170)):
            u = 85 + i * 170
            if u < W - 60:
                f.line(u - 60, D * 0.5 - 150, u + 60, D * 0.5 + 150, 'A-FURN-WARD', 0.2)
        self.reg(label.lower(), floor, x0, y0, x1, y1)
        self.wards.append((floor, (x0, y0, x1, y1), self.frame(x0, y0, x1, y1, front), label, loft, W))

    def sofa(self, floor, x0, y0, x1, y1, front, seats=3, name='sofa'):
        f = self.frame(x0, y0, x1, y1, front); W, D = f.W, f.D
        f.rect(0, 0, W, D, 'A-FURN-SOFA', SOFT, 0.6)
        f.rect(150, 0, W - 150, 220, 'A-FURN-SOFA', '#d9cdbd', 0.4)
        f.rect(0, 0, 150, D, 'A-FURN-SOFA', '#d9cdbd', 0.4)
        f.rect(W - 150, 0, W, D, 'A-FURN-SOFA', '#d9cdbd', 0.4)
        cw = (W - 300) / seats
        for i in range(seats):
            f.rect(150 + i * cw + 15, 235, 150 + (i + 1) * cw - 15, D - 25, 'A-FURN-SOFA', '#efe7dc', 0.35)
        f.rect(170, 230, 370, 330, 'A-FURN-SOFA', '#b9a58a', 0.3)
        f.rect(W - 370, 230, W - 170, 330, 'A-FURN-SOFA', '#b9a58a', 0.3)
        self.reg(name, floor, x0, y0, x1, y1)

    def armchair(self, floor, x0, y0, x1, y1, front, name='armchair'):
        f = self.frame(x0, y0, x1, y1, front); W, D = f.W, f.D
        f.rect(0, 0, W, D, 'A-FURN-SOFA', SOFT, 0.6)
        f.rect(110, 0, W - 110, 180, 'A-FURN-SOFA', '#d9cdbd', 0.4)
        f.rect(0, 0, 110, D, 'A-FURN-SOFA', '#d9cdbd', 0.4)
        f.rect(W - 110, 0, W, D, 'A-FURN-SOFA', '#d9cdbd', 0.4)
        f.rect(125, 195, W - 125, D - 25, 'A-FURN-SOFA', '#efe7dc', 0.35)
        self.reg(name, floor, x0, y0, x1, y1)

    def chair(self, floor, cx, cy, facing, s=450):
        x0, y0 = cx - s / 2, cy - s / 2
        f = self.frame(x0, y0, x0 + s, y0 + s, facing)
        f.rect(0, 0, s, s, 'A-FURN', WOOD, 0.5)
        f.rect(0, 0, s, 70, 'A-FURN', '#c9a77d', 0.4)
        self.reg('chair', floor, x0, y0, x0 + s, y0 + s)

    def unit(self, floor, x0, y0, x1, y1, front, label, fill=WOOD, cross=False, shelves=0, name=None, h=58, kind='furn'):
        f = self.frame(x0, y0, x1, y1, front)
        f.rect(0, 0, f.W, f.D, 'A-FURN', fill, 0.6)
        if cross:
            f.line(0, 0, f.W, f.D, 'A-FURN', 0.25); f.line(f.W, 0, 0, f.D, 'A-FURN', 0.25)
        for i in range(1, shelves):
            f.line(f.W * i / shelves, 0, f.W * i / shelves, f.D, 'A-FURN', 0.2)
        if label:
            self.text(f.t(f.W / 2, f.D / 2), label, h)
        self.reg(name or label.lower(), floor, x0, y0, x1, y1, kind)
        return f

    def tv_unit(self, floor, x0, y0, x1, y1, front, tv=1450):
        f = self.frame(x0, y0, x1, y1, front); W, D = f.W, f.D
        f.rect(0, 0, W, D, 'A-FURN', WOOD, 0.5)
        f.line(0, D - 30, W, D - 30, 'A-FURN', 0.3)
        f.rect(W / 2 - tv / 2, 40, W / 2 + tv / 2, 100, 'A-FURN', '#555', 0.4)
        self.text(f.t(W / 2, D * 0.62), 'TV UNIT', 62)
        self.reg('tv unit', floor, x0, y0, x1, y1)

    def rug(self, x0, y0, x1, y1, fill='#ede4f1'):
        self.rect(x0, y0, x1, y1, 'A-FURN-RUG', fill, 0.4)
        self.rect(x0 + 80, y0 + 80, x1 - 80, y1 - 80, 'A-FURN-RUG', None, 0.3, '--')

    def plant(self, floor, cx, cy, r=220):
        self.circ((cx, cy), r, 'A-FURN-PLANT', GREEN, 0.4)
        for a in range(0, 360, 45):
            self.poly([(cx, cy), (cx + r * .85 * math.cos(math.radians(a)), cy + r * .85 * math.sin(math.radians(a)))], 'A-FURN-PLANT', None, False, 0.25)
        self.circ((cx, cy), r * 0.3, 'A-FURN-PLANT', '#a9c99b', 0.3)
        self.reg('planter', floor, cx - r, cy - r, cx + r, cy + r)

    def round_table(self, floor, cx, cy, r, name='side table'):
        self.circ((cx, cy), r, 'A-FURN', WOOD, 0.5)
        self.reg(name, floor, cx - r, cy - r, cx + r, cy + r)

    def ac(self, x0, y0, x1, y1, label='AC 1.5T'):
        self.rect(x0, y0, x1, y1, 'A-FURN-AC', '#ffffff', 0.5, '--')
        self.text(((x0 + x1) / 2, (y0 + y1) / 2), label, 50, color='#2a6fa8')

    def curtain(self, x0, y0, x1, y1, blind=False):
        """wavy curtain line along the longer axis of the given strip."""
        if blind:
            self.poly([(x0, y0), (x1, y1)], 'A-FURN-CURTAIN', None, False, 0.6, '--')
            return
        horiz = abs(x1 - x0) > abs(y1 - y0)
        L = abs(x1 - x0) if horiz else abs(y1 - y0)
        n = max(4, int(L / 120))
        pts = []
        for i in range(n * 4 + 1):
            t = i / (n * 4)
            w = 35 * math.sin(t * n * 2 * math.pi)
            pts.append((x0 + (x1 - x0) * t, y0 + w) if horiz else (x0 + w, y0 + (y1 - y0) * t))
        self.poly(pts, 'A-FURN-CURTAIN', None, False, 0.45)

    def counter(self, floor, x0, y0, x1, y1, front, name='counter'):
        f = self.frame(x0, y0, x1, y1, front)
        f.rect(0, 0, f.W, f.D, 'A-FURN-KIT', STONE, 0.6)
        f.line(0, f.D - 40, f.W, f.D - 40, 'A-FURN-KIT', 0.25, '--')
        self.reg(name, floor, x0, y0, x1, y1)
        return f

    def hob(self, f, u, chimney='wall'):
        f.rect(u, 60, u + 860, 540, 'A-FURN-KIT', '#cfd2d6', 0.4)
        for du, dv, r in [(200, 170, 85), (660, 170, 85), (200, 420, 70), (660, 420, 105)]:
            f.circ(u + du, dv, r, 'A-FURN-KIT', None, 0.4)
            f.circ(u + du, dv, r * 0.45, 'A-FURN-KIT', None, 0.25)
        f.rect(u - 20, -10, u + 880, 500, 'A-FURN-KIT', None, 0.3, '--')
        self.text(f.t(u + 430, 700), 'HOB + ' + ('ISLAND ' if chimney == 'island' else '') + 'CHIMNEY', 50)

    def sink(self, f, u, w=1000):
        f.rect(u, 70, u + w, 520, 'A-FURN-KIT', METAL, 0.4)
        f.rect(u + 40, 110, u + w * 0.55, 480, 'A-FURN-KIT', '#fff', 0.35)
        f.rect(u + w * 0.6, 110, u + w - 40, 480, 'A-FURN-KIT', '#fff', 0.35)
        f.circ(u + w * 0.58, 50, 25, 'A-FURN-KIT', None, 0.3)
        self.text(f.t(u + w / 2, 700), 'SINK', 50)

    def label(self, x, y, name, w=None, d=None, h=150, sub=None):
        self.labels.append((x, y, name, w, d, h, sub))

    def _draw_label(self, x, y, name, w=None, d=None, h=150, sub=None):
        self.text((x, y + 70), name, h, 'A-ROOM-TEXT', True, '#1d2b4f')
        if w:
            self.text((x, y - 110), f"{ft(w)} x {ft(d)}", h * 0.68, 'A-ROOM-TEXT', False, '#4a5a80')
        if sub:
            self.text((x, y - 250), sub, h * 0.6, 'A-ROOM-TEXT', False, '#8a4b00')

    def keep_rect(self, name, floor, x0, y0, x1, y1):
        self.KEEP.append((name, floor, 'rect', (x0, y0, x1, y1)))

    def keep_arc(self, name, floor, hx, hy, r, x0, y0, x1, y1):
        """door swing: quarter circle centred on hinge, restricted to bbox."""
        self.KEEP.append((name, floor, 'arc', (hx, hy, r, x0, y0, x1, y1)))


class Frame:
    """Local frame on a rectangle: u along the back wall, v from back (0) to front (D)."""
    def __init__(self, L, x0, y0, x1, y1, front):
        self.L = L
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.f = {'T': 'S', 'B': 'N', 'L': 'E', 'R': 'W'}.get(front, front)
        self.W = (x1 - x0) if self.f in 'NS' else (y1 - y0)
        self.D = (y1 - y0) if self.f in 'NS' else (x1 - x0)

    def t(self, u, v):
        f = self.f
        if f == 'S': return (self.x0 + u, self.y1 - v)
        if f == 'N': return (self.x0 + u, self.y0 + v)
        if f == 'E': return (self.x0 + v, self.y0 + u)
        return (self.x1 - v, self.y0 + u)

    def rect(self, u0, v0, u1, v1, layer, fill=None, lw=0.5, ls='-'):
        self.L.poly([self.t(u0, v0), self.t(u1, v0), self.t(u1, v1), self.t(u0, v1)], layer, fill, True, lw, ls)

    def line(self, u0, v0, u1, v1, layer, lw=0.4, ls='-'):
        self.L.poly([self.t(u0, v0), self.t(u1, v1)], layer, None, False, lw, ls)

    def circ(self, u, v, r, layer, fill=None, lw=0.4):
        self.L.circ(self.t(u, v), r, layer, fill, lw)

    def arc(self, u, v, r, a0, a1, layer, n=16, lw=0.4):
        pts = [self.t(u + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), v + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        self.L.poly(pts, layer, None, False, lw)


# ======================================================================== rules
HEAD_PREF = {'S': 0, 'E': 1, 'W': 2, 'N': 9}     # strict Vastu: S best, E good, W compromise, N never


def pick_head(L, options):
    """options: list of drawing sides that are geometrically feasible, in design order."""
    ranked = sorted(options, key=lambda s: (HEAD_PREF[L.c[s]], options.index(s)))
    return ranked[0]


# ======================================================================== rooms
def bedroom1(L):
    """Parents' bedroom, lower floor. x 3919-7884, y 3416-7686. Door hinge (7884,7686), swing into room."""
    fl = 'lower'
    L.keep_arc('BR-1 door swing', fl, 7884, 7686, 900, 6984, 6786, 7884, 7686)
    L.keep_rect('BR-1 entry approach', fl, 6984, 6786, 7884, 7686)
    kw, kl = KING[0] + FRAME_W, KING[1] + FRAME_L          # 1930 x 2130
    head = pick_head(L, ['L', 'T', 'R'])
    L.choices['Bedroom-1 bed head'] = head
    if head == 'L':
        cy = 5450
        L.bed(fl, 'BR-1 bed', 3919, cy - kw / 2, 3919 + kl, cy + kw / 2, 'L')
        L.side_table(fl, 3919, cy - kw / 2 - SIDE); L.side_table(fl, 3919, cy + kw / 2)
        L.wardrobe(fl, 7284, 4500, 7884, 6736, 'R')
        L.unit(fl, 4569, 7236, 5769, 7686, 'T', 'DRESSER', name='dresser'); L.round_table(fl, 5169, 6950, 170, 'stool')
        L.armchair(fl, 7084, 3570, 7834, 4320, 'R', 'recliner'); L.text((7459, 4430), 'RECLINER', 52)
        L.ac(5950, 7456, 6900, 7686)
    elif head == 'T':
        cx = 5515
        L.bed(fl, 'BR-1 bed', cx - kw / 2, 7686 - kl, cx + kw / 2, 7686, 'T')
        L.side_table(fl, cx - kw / 2 - SIDE, 7686 - SIDE); L.side_table(fl, cx + kw / 2, 7686 - SIDE)
        L.wardrobe(fl, 7284, 4500, 7884, 6736, 'R')
        L.unit(fl, 3919, 4600, 4369, 5800, 'L', 'DRESSER', name='dresser')
        L.armchair(fl, 4100, 3620, 4850, 4370, 'B', 'recliner'); L.text((4475, 4480), 'RECLINER', 52)
        L.ac(3919, 5900, 4149, 6900)
    else:
        cy = 5265
        L.bed(fl, 'BR-1 bed', 7884 - kl, cy - kw / 2, 7884, cy + kw / 2, 'R')
        L.side_table(fl, 7884 - SIDE, cy - kw / 2 - SIDE); L.side_table(fl, 7884 - SIDE, cy + kw / 2)
        L.wardrobe(fl, 3919, 4500, 4519, 6936, 'L')
        L.unit(fl, 4900, 7236, 6100, 7686, 'T', 'DRESSER', name='dresser'); L.round_table(fl, 5500, 6950, 170, 'stool')
        L.armchair(fl, 3969, 3570, 4719, 4320, 'L', 'recliner'); L.text((4344, 4430), 'RECLINER', 52)
        L.ac(4700, 7456, 5650, 7686)
    L.curtain(3969, 3416 + 130, 7834, 3416 + 130)
    L.label(5900 if head != 'R' else 5100, 5900 if head == 'L' else (5000 if head == 'T' else 6250), 'BEDROOM-1', 3965, 4270, sub='PARENTS')


def bedroom2(L):
    """Son / guest bedroom, upper floor. x 42776-46741, y 3636-7906. Entry from passage at top-right."""
    fl = 'upper'
    L.keep_rect('BR-2 entry zone', fl, 45750, 7006, 46741, 7906)
    kw, kl = KING[0] + FRAME_W, KING[1] + FRAME_L
    head = pick_head(L, ['L', 'T', 'R'])
    L.choices['Bedroom-2 bed head'] = head
    if head == 'L':
        cy = 5671
        L.bed(fl, 'BR-2 bed', 42776, cy - kw / 2, 42776 + kl, cy + kw / 2, 'L')
        L.side_table(fl, 42776, cy - kw / 2 - SIDE); L.side_table(fl, 42776, cy + kw / 2)
        L.wardrobe(fl, 46141, 4600, 46741, 6956, 'R')
        L.unit(fl, 43526, 7456, 44926, 7906, 'T', 'STUDY / DRESSER', name='study'); L.chair(fl, 44226, 7180, 'N')
        L.armchair(fl, 45991, 3700, 46691, 4400, 'R')
        L.ac(43700 - 600, 7676, 44700 - 600, 7906)
    elif head == 'T':
        cx = 44265
        L.bed(fl, 'BR-2 bed', cx - kw / 2, 7906 - kl, cx + kw / 2, 7906, 'T')
        L.side_table(fl, cx - kw / 2 - SIDE, 7906 - SIDE); L.side_table(fl, cx + kw / 2, 7906 - SIDE)
        L.wardrobe(fl, 46141, 4600, 46741, 6956, 'R')
        L.unit(fl, 42776, 4000, 43376, 5400, 'L', 'STUDY', name='study'); L.chair(fl, 43650, 4700, 'W')
        L.armchair(fl, 45991, 3700, 46691, 4400, 'R')
        L.ac(42776, 5800, 43006, 6800)
    else:
        cy = 5265
        L.bed(fl, 'BR-2 bed', 46741 - kl, cy - kw / 2, 46741, cy + kw / 2, 'R')
        L.side_table(fl, 46741 - SIDE, cy - kw / 2 - SIDE); L.side_table(fl, 46741 - SIDE, cy + kw / 2)
        L.wardrobe(fl, 42776, 4600, 43376, 7056, 'L')
        L.unit(fl, 43700, 7456, 45100, 7906, 'T', 'STUDY / DRESSER', name='study'); L.chair(fl, 44400, 7180, 'N')
        L.armchair(fl, 42826, 3700, 43526, 4400, 'L')
        L.ac(45200, 7676, 46200, 7906)
    L.curtain(42826, 3636 + 130, 46691, 3636 + 130)
    L.label(45300 if head == 'L' else (44300 if head == 'T' else 44000), 5900 if head != 'T' else 4900, 'BEDROOM-2', 3965, 4270, sub='SON / GUEST')


def bedroom3(L):
    """Kids' bedroom, upper. x 42776-46625, y 12126-16581. Door hinge (46625,12126). Toilet door R wall y 13026-13786."""
    fl = 'upper'
    L.keep_arc('BR-3 door swing', fl, 46625, 12126, 900, 45725, 12126, 46625, 13026)
    L.keep_rect('BR-3 toilet approach', fl, 45875, 13026, 46625, 13786)
    qw, ql = QUEEN[0] + FRAME_W, QUEEN[1] + FRAME_L       # 1625 x 2130
    head = pick_head(L, ['L', 'B', 'R'])
    L.choices['Bedroom-3 bed head'] = head
    if head == 'L':
        cy = 14218
        L.bed(fl, 'BR-3 bed', 42776, cy - qw / 2, 42776 + ql, cy + qw / 2, 'L')
        L.side_table(fl, 42776, cy - qw / 2 - SIDE); L.side_table(fl, 42776, cy + qw / 2)
        L.wardrobe(fl, 46025, 13886, 46625, 16481, 'R')
        L.unit(fl, 44050, 15981, 45250, 16581, 'T', 'STUDY TABLE', name='study'); L.chair(fl, 44650, 15700, 'N')
        L.unit(fl, 43376, 16281, 43976, 16581, 'T', '', shelves=4, name='bookshelf')
        L.ac(43400, 12126, 44400, 12356)
        L.curtain(43435, 16581 - 120, 45635, 16581 - 120, blind=True)
    elif head == 'B':
        cx = 44089
        L.bed(fl, 'BR-3 bed', cx - qw / 2, 12126, cx + qw / 2, 12126 + ql, 'B')
        L.side_table(fl, cx - qw / 2 - SIDE, 12126); L.side_table(fl, cx + qw / 2, 12126)
        L.wardrobe(fl, 46025, 13886, 46625, 16481, 'R')
        L.unit(fl, 44050, 15981, 45250, 16581, 'T', 'STUDY TABLE', name='study'); L.chair(fl, 44650, 15700, 'N')
        L.unit(fl, 42876, 16281, 43376, 16581, 'T', '', shelves=4, name='bookshelf')
        L.ac(42776, 14600, 43006, 15600)
        L.curtain(43435, 16581 - 120, 45635, 16581 - 120, blind=True)
    else:
        cy = 15118
        L.bed(fl, 'BR-3 bed', 46625 - ql, cy - qw / 2, 46625, cy + qw / 2, 'R')
        L.side_table(fl, 46625 - SIDE, cy - qw / 2 - SIDE); L.side_table(fl, 46625 - SIDE, cy + qw / 2)
        L.wardrobe(fl, 42776, 12226, 43376, 14826, 'L')
        L.unit(fl, 42776, 15050, 43376, 16250, 'L', 'STUDY', name='study'); L.chair(fl, 43650, 15650, 'W')
        L.unit(fl, 43535, 16281, 44235, 16581, 'T', '', shelves=4, name='bookshelf')
        L.ac(43600, 12126, 44600, 12356)
        L.curtain(44300, 16581 - 120, 45635, 16581 - 120, blind=True)
    L.label(44700 if head != 'R' else 44300, 13250 if head == 'L' else (14900 if head == 'B' else 13300), 'BEDROOM-3', 3850, 4455, sub='KIDS')


def bedroom4(L):
    """Master bedroom, upper. main x 50630-54365, y 9761-14636; dress x 48685-50630, y 9761-12011."""
    fl = 'upper'
    L.keep_arc('BR-4 entry door swing', fl, 48685, 12011, 990, 48685, 11021, 49675, 12011)
    L.keep_rect('BR-4 toilet approach', fl, 49755, 11261, 50515, 12011)
    L.keep_rect('Slider to master balcony', fl, 50630, 13836, 51580, 14636)
    kw, kl = KING[0] + FRAME_W, KING[1] + FRAME_L
    # 'L' (toilet wall) is rejected: the bed would block the balcony slider.
    head = pick_head(L, ['R', 'B'])
    L.choices['Master bed head'] = head
    L.wardrobe(fl, 48735, 9761, 50580, 10361, 'B', 'WARDROBE')
    if head == 'R':
        cy = 12200
        L.bed(fl, 'BR-4 bed', 54365 - kl, cy - kw / 2, 54365, cy + kw / 2, 'R')
        L.side_table(fl, 54365 - SIDE, cy - kw / 2 - SIDE); L.side_table(fl, 54365 - SIDE, cy + kw / 2)
        L.wardrobe(fl, 50630, 9761, 52530, 10361, 'B', 'WARDROBE')
        L.tv_unit(fl, 50630, 12000, 51030, 13800, 'L', 1250)
        L.sofa(fl, 52800, 13900, 54300, 14500, 'B', 2, 'chaise lounge'); L.text((53550, 14200), 'CHAISE LOUNGE', 46)
        L.rug(51300, 11400, 52150, 13000, '#efe4da')
        L.ac(50630, 12450, 50860, 13450, 'AC 1.5T (above TV)')
    else:
        cx = 52950
        L.bed(fl, 'BR-4 bed', cx - kw / 2, 9761, cx + kw / 2, 9761 + kl, 'B')
        L.side_table(fl, cx - kw / 2 - SIDE, 9761); L.side_table(fl, cx + kw / 2, 9761)
        L.wardrobe(fl, 50630, 12111, 51230, 13736, 'L', 'WARDROBE')
        L.text((49000, 10700), 'FULL-LENGTH MIRROR\nON WALL', 42, color='#777')
        L.unit(fl, cx - 700, 9761 + kl + 50, cx + 700, 9761 + kl + 500, 'T', 'BED-END BENCH', fill=SOFT, name='bench')
        L.sofa(fl, 52800, 13900, 54300, 14500, 'B', 2, 'chaise lounge'); L.text((53550, 14200), 'CHAISE LOUNGE', 46)
        L.ac(54135, 12500, 54365, 13500)
        L.text((52300, 13300), 'TV (OPTIONAL) ON\nWARDROBE PANEL', 50, color='#777')
    L.curtain(50680, 14636 - 120, 54315, 14636 - 120)
    # master balcony
    L.armchair(fl, 50900, 15300, 51550, 15950, 'L'); L.armchair(fl, 52150, 15300, 52800, 15950, 'R')
    L.round_table(fl, 51850, 15625, 220, 'balcony table'); L.plant(fl, 52700, 15000, 140)
    L.rect(52931, 14800, 53081, 16100, 'A-FURN-PLANT', '#9fc48f', 0.5)
    L.label(52500, 13400 if head == 'R' else 12700, 'MASTER BED-4', 3735, 4875)
    L.label(49650, 10800, 'DRESS', 1945, 2250, 110)


def kitchen(L):
    """Lower floor kitchen, x 3919-6779, y 11900-16361. West (L) wall: window y 13445-15276.
    Cook faces EAST: the hob sits on whichever side is East, near its South end (Agni corner)."""
    fl = 'lower'
    L.keep_arc('Wash door swing', fl, 6836, 14531, 990, 6894, 14531, 7884, 15521)
    L.keep_rect('Kitchen aisle', fl, 4600, 12700, 5500, 15600)
    E = [s for s in 'LTRB' if L.c[s] == 'E'][0]
    S = [s for s in 'LTRB' if L.c[s] == 'S'][0]
    L.choices['Hob wall (cook faces East)'] = E
    # ---- L counter on the west wall (always: sink under window)
    wl = L.counter(fl, 3919, 11900, 4519, 16361, 'L', 'counter W')
    sink_u = 1650 if (E == 'L' and S == 'T') else 2050      # keep sink >= 750 from hob
    L.sink(wl, sink_u, 1000)
    L.unit(fl, 3919, 11900 + sink_u - 620, 4519, 11900 + sink_u - 20, 'L', 'DW', fill='#d9dee6', name='dishwasher', h=48, kind='inbuilt')
    L.text((4219, 11900 + sink_u + 1150), 'RO', 50)
    fridge = (6129, 11900, 6779, 12620); tall = (6179, 12620, 6779, 13250)
    if E == 'L':
        u = 3380 if S == 'T' else 150
        L.hob(wl, u)
        L.counter(fl, 4519, 15761, 6779, 16361, 'T', 'counter N')
        L.text((5650, 16060), 'PREP · MICROWAVE · OTG', 50)
    elif E == 'T':
        tn = L.counter(fl, 4519, 15761, 6779, 16361, 'T', 'counter N')
        L.hob(tn, 1300 if S == 'R' else 120)
    elif E == 'R':
        # peninsula along the open east edge, island chimney; fridge moves to the NE corner
        pe = L.counter(fl, 6179, 12000, 6779, 13900, 'R', 'peninsula')
        L.hob(pe, 1000 if S == 'T' else 60, chimney='island')
        L.counter(fl, 4519, 15761, 6079, 16361, 'T', 'counter N')
        fridge = (6079, 15561, 6779, 16361); tall = None
        L.notes.append('Kitchen: hob on a peninsula along the open east edge (cook faces East) with an island chimney.')
    else:  # E == 'B'
        bc = L.counter(fl, 4519, 11900, 6129, 12500, 'B', 'counter S')
        L.hob(bc, 80 if S == 'L' else 700)
        L.counter(fl, 4519, 15761, 6779, 16361, 'T', 'counter N')
        L.notes.append('Kitchen: build a full-height wall between kitchen and stair behind the south counter (hob + chimney).')
    L.unit(fl, *fridge, 'R' if fridge[0] == 6129 else 'T', 'DOUBLE-DOOR\nFRIDGE', fill='#d9dee6', name='fridge', h=50)
    if tall:
        L.unit(fl, *tall, 'R', 'TALL UNIT\nPANTRY', name='tall unit', h=50)
    # wall cabinets (dashed, above counter, not over window)
    L.rect(3919, 11900, 4269, 13400, 'A-FURN-KIT', None, 0.3, '--')
    L.rect(4519, 16011, 6079, 16361, 'A-FURN-KIT', None, 0.3, '--')
    L.text((4950, 12250), 'WALL CAB.\n(dashed)', 45, color='#888')
    L.curtain(3919 + 70, 13445, 3919 + 70, 15276, blind=True)
    L.poly([(6779, 13300), (6779, 14416)], 'A-FURN-KIT', None, False, 0.5, '--')
    L.text((7020, 13800), 'FLUTED GLASS\nSLIDER (OPT.)', 46, color='#777')
    L.label(5300, 14700, 'KITCHEN', 2860, 4570)


def living_dining(L):
    """Lower floor living/dining, x 6894-15509, y 9541-14416. Main door x 8494-9714 at y 9541 (hinge 8494)."""
    fl = 'lower'
    L.keep_arc('Main door swing', fl, 8494, 9541, 1220, 8494, 9541, 9714, 10761)
    L.keep_rect('Path door -> living', fl, 9714, 9991, 11100, 10850)
    L.keep_rect('Path door -> stair/dining', fl, 7300, 10761, 8800, 11250)
    L.keep_rect('Path to balcony slider', fl, 10014, 13450, 11100, 14416)
    c = L.c
    # ---------------- pooja in the North-East corner of the living/dining hall
    corners = {('L', 'T'): 'P1', ('R', 'T'): 'P2', ('R', 'B'): 'P3', ('L', 'B'): 'P4'}
    pooja = None
    for (h, v), p in corners.items():
        if {c[h], c[v]} == {'N', 'E'}:
            pooja = p
    L.choices['Pooja position'] = pooja
    P = {'P1': (7044, 13966, 8244, 14416, 'T'), 'P2': (15059, 13166, 15509, 14366, 'R'),
         'P3': (13824, 9541, 15024, 9991, 'B'), 'P4': (10964, 9541, 12164, 9991, 'B')}[pooja]
    f = L.frame(P[0], P[1], P[2], P[3], P[4])
    f.rect(0, 0, f.W, f.D, 'A-FURN-POOJA', POOJA, 0.7)
    f.arc(f.W / 2, 140, 330, 0, 180, 'A-FURN-POOJA', 20, 0.4)
    f.circ(f.W / 2, 170, 60, 'A-FURN-POOJA', '#e8a33d', 0.4)
    L.text(f.t(f.W / 2, 340), 'POOJA UNIT', 62, bold=True, color='#8a4b00')
    L.reg('pooja unit', fl, *P[:4])
    stand = {'P1': (7044, 13116, 8244, 13966), 'P2': (14259, 13166, 15059, 14366),
             'P3': (13824, 9991, 15024, 10791), 'P4': (10964, 9991, 12164, 10791)}[pooja]
    L.keep_rect('Pooja standing space', fl, *stand)
    faces = {'P1': c['T'], 'P2': c['R'], 'P3': c['B'], 'P4': c['B']}[pooja]
    L.choices['Devotee faces'] = faces
    # ---------------- entry: shoe cabinet (never next to pooja) + jaali screen
    if pooja == 'P4':
        L.unit(fl, 7999, 9541, 8444, 9941, 'B', 'SHOE\nUNIT', name='shoe cabinet', h=46)
    else:
        L.unit(fl, 9764, 9541, 10864, 9941, 'B', 'SHOE CABINET + MIRROR', cross=True, name='shoe cabinet', h=50)
    L.rect(8800, 11000, 9900, 11100, 'A-FURN', '#c9a77d', 0.6)
    L.reg('jaali screen', fl, 8800, 11000, 9900, 11100)
    L.text((9350, 11200), 'CNC JAALI SCREEN', 46, color='#6b4a2b')
    # ---------------- dining: 6 seater next to kitchen
    L.rect(8050, 11300, 8950, 13100, 'A-FURN', '#e2cba8', 0.7); L.rect(8110, 11360, 8890, 13040, 'A-FURN', None, 0.3)
    L.reg('dining table', fl, 8050, 11300, 8950, 13100)
    for cy in (11600, 12200, 12800):
        L.chair(fl, 7725, cy, 'E'); L.chair(fl, 9275, cy, 'W')
    L.text((8500, 12200), '6 SEATER\nDINING\n1800x900', 58)
    if pooja == 'P1':
        L.unit(fl, 8344, 13966, 9614, 14416, 'T', 'CROCKERY / BAR', shelves=2, name='crockery')
    else:
        L.unit(fl, 7044, 13966, 9614, 14416, 'T', 'CROCKERY + DISPLAY', shelves=4, name='crockery')
    L.ac(8300, 14186, 9300, 14416)
    # ---------------- living seating
    if pooja == 'P2':
        # TV on east (R) wall, low half; >1.2 m from pooja; seating shifted south
        L.tv_unit(fl, 15109, 9800, 15509, 11900, 'R', 1450)
        L.sofa(fl, 11450, 9750, 12400, 11950, 'L', 3)
        L.rug(12450, 9700, 14650, 12000)
        L.rect(12850, 10300, 13450, 11400, 'A-FURN', '#e2cba8', 0.6); L.reg('coffee table', fl, 12850, 10300, 13450, 11400)
        L.armchair(fl, 12800, 12150, 13600, 12950, 'T'); L.armchair(fl, 13800, 12150, 14600, 12950, 'T')
        L.plant(fl, 15200, 12450, 180)
        L.ac(15279, 10350, 15509, 11350)
        L.unit(fl, 10950, 11150, 11350, 12750, 'R', 'CONSOLE', name='console', h=48)
        L.text((15000, 12950), 'PLANTER\nSEPARATES\nTV & POOJA', 44, color='#777')
        sofa_face = c['R']
    elif pooja == 'P3':
        L.tv_unit(fl, 15109, 11700, 15509, 14100, 'R', 1450)
        L.sofa(fl, 11450, 11800, 12400, 14000, 'L', 3)
        L.rug(12450, 11700, 14650, 14000)
        L.rect(12850, 12300, 13450, 13500, 'A-FURN', '#e2cba8', 0.6); L.reg('coffee table', fl, 12850, 12300, 13450, 13500)
        L.armchair(fl, 12500, 10650, 13300, 11450, 'B')
        L.plant(fl, 15150, 11100, 180)
        L.ac(15279, 12400, 15509, 13400)
        L.unit(fl, 10950, 11900, 11350, 13400, 'R', 'CONSOLE', name='console', h=48)
        sofa_face = c['R']
    elif c['R'] in ('N', 'E'):
        # P1 / P4 with the party wall facing N/E: TV centred on the solid east (R) party wall
        L.tv_unit(fl, 15109, 10600, 15509, 13200, 'R', 1450)
        L.sofa(fl, 11450, 10900, 12400, 13000, 'L', 3)
        L.rug(12450, 10650, 14650, 13250)
        L.rect(12850, 11400, 13450, 12500, 'A-FURN', '#e2cba8', 0.6); L.reg('coffee table', fl, 12850, 11400, 13450, 12500)
        if pooja == 'P4':
            L.armchair(fl, 12800, 13350, 13600, 14150, 'T'); L.armchair(fl, 13800, 13350, 14600, 14150, 'T')
        else:
            L.armchair(fl, 12750, 9700, 13550, 10500, 'B'); L.armchair(fl, 13850, 9700, 14650, 10500, 'B')
            L.round_table(fl, 13700, 10100, 130)
        L.plant(fl, 15150, 13750 if pooja != 'P4' else 9950, 180)
        L.ac(15279, 11400, 15509, 12400, 'AC 2T (above TV)')
        L.unit(fl, 10950, 11150, 11350, 12750, 'R', 'CONSOLE', name='console', h=48)
        sofa_face = c['R']
    else:
        # P1 / P4 with the party wall facing S/W: sofa backs onto the solid party wall and faces
        # a floating TV partition between living and dining (owner faces N/E as Vastu asks).
        f = L.frame(10950, 11000, 11350, 12900, 'L')
        f.rect(0, 0, f.W, f.D, 'A-FURN', WOOD, 0.6)
        f.rect(f.W / 2 - 725, f.D - 60, f.W / 2 + 725, f.D, 'A-FURN', '#555', 0.4)
        L.text((11150, 11950), 'TV PARTITION\n(display on\ndining side)', 46)
        L.reg('tv partition', fl, 10950, 11000, 11350, 12900)
        L.sofa(fl, 14450, 10850, 15400, 13050, 'R', 3)
        L.rug(12000, 10650, 14400, 13250)
        L.rect(13250, 11400, 13850, 12500, 'A-FURN', '#e2cba8', 0.6); L.reg('coffee table', fl, 13250, 11400, 13850, 12500)
        if pooja == 'P4':
            L.armchair(fl, 12250, 13350, 13050, 14150, 'T'); L.armchair(fl, 13350, 13350, 14150, 14150, 'T')
            L.ac(13300, 9541, 14300, 9771, 'AC 2T')
        else:
            L.armchair(fl, 12250, 9700, 13050, 10500, 'B'); L.armchair(fl, 13350, 9700, 14150, 10500, 'B')
            L.round_table(fl, 13200, 10100, 0.1)
            L.ac(14450, 9541, 15450, 9771, 'AC 2T')
        L.plant(fl, 15200, 13700 if pooja != 'P4' else 10200, 170)
        L.text((12700, 12950), 'VIEWING 3.0 m', 48, color='#777')
        sofa_face = c['L']
        L.notes.append('Living: a floating TV partition between living and dining; the sofa backs onto the solid party wall so the owner faces ' + c['L'] + '.')
    L.choices['Sofa faces'] = sofa_face
    L.curtain(10064, 14416 - 120, 15459, 14416 - 120)
    ly = {'P1': 13800, 'P2': 13300, 'P3': 10300, 'P4': 12900}[pooja]
    lx = 13200 if c['R'] in ('N', 'E') or pooja in ('P2', 'P3') else 12950
    if pooja == 'P4' and c['R'] not in ('N', 'E'): ly = 10350
    L.label(lx, ly, 'LIVING', 4875, 4875)
    L.label(7550, 10300, 'DINING', 3300, 4875, 120)


def lower_misc(L):
    fl = 'lower'
    # wash area
    L.keep_arc('Wash door swing', fl, 6836, 14531, 990, 6894, 14531, 7884, 15521)
    L.counter(fl, 7950, 15761, 9149, 16361, 'T', 'utility counter')
    L.rect(8250, 15841, 8850, 16281, 'A-FURN-KIT', METAL, 0.4); L.text((8550, 15650), 'UTILITY SINK', 48)
    L.rect(9199, 15711, 9849, 16361, 'A-FURN-KIT', '#fff', 0.6); L.circ((9524, 16036), 230, 'A-FURN-KIT', None, 0.4)
    L.reg('washing machine', fl, 9199, 15711, 9849, 16361); L.text((9524, 15560), 'W.M.', 55)
    L.rect(7900, 14700, 9750, 15450, 'A-FURN', None, 0.3, '--'); L.text((8800, 15080), 'CEILING CLOTH DRYER', 48, color='#777')
    L.label(8300, 15350, 'WASH', 3005, 1830, 105)
    # balcony
    f = L.frame(13900, 15500, 15200, 16100, 'T'); f.rect(0, 0, f.W, f.D, 'A-FURN-SOFA', SOFT, 0.6); f.rect(0, 0, f.W, 150, 'A-FURN-SOFA', '#d9cdbd', 0.4)
    for u in (100, f.W - 100): f.line(u, -150, u, 0, 'A-FURN', 0.4)
    L.reg('jhula', fl, 13900, 15500, 15200, 16100)
    L.keep_rect('Jhula swing arc', fl, 13900, 14900, 15200, 15500)
    L.text((14550, 15350), 'JHULA (SWING)', 55)
    L.sofa(fl, 11800, 15500, 13500, 16250, 'T', 2, 'outdoor sofa'); L.text((12650, 15650), 'OUTDOOR SOFA', 46)
    L.rect(12350, 14850, 12950, 15250, 'A-FURN', WOOD, 0.6); L.reg('balcony table', fl, 12350, 14850, 12950, 15250)
    L.rect(15359, 14650, 15509, 16300, 'A-FURN-PLANT', '#9fc48f', 0.5); L.text((15250, 16380), 'VERTICAL GARDEN', 44, color='#3d6b2e')
    for x in (10300, 10800, 11300): L.plant(fl, x, 16050, 200)
    L.label(12000, 14900, 'BALCONY', 5495, 1830, 105)
    # lower toilet (parents use): glass shower partition + grab bars
    L.poly([(5350, 7801), (5350, 8700)], 'A-FURN-SAN', None, False, 0.8)
    L.text((4990, 8900), 'SHOWER', 48, color='#2a6fa8')
    L.poly([(5250, 8300), (5250, 8650)], 'A-FURN-SAN', None, False, 1.4)
    L.text((5700, 9230), 'GRAB BARS · ANTI-SKID', 44, color='#2a6fa8')
    L.label(5900, 8950, 'TOILET', 2135, 1625, 100)
    L.text((5350, 10200), 'UNDER-STAIR: PEBBLE COURT\n+ UPLIGHT / STORAGE', 48, color='#777')


def upper_misc(L):
    fl = 'upper'
    L.keep_arc('BR-2 passage door', fl, 45750, 9704, 900, 45750, 8804, 46650, 9704)
    L.keep_rect('Lobby path', fl, 45635, 11021, 48570, 12011)
    L.unit(fl, 46840, 9761, 48470, 10111, 'B', 'LOW BOOKSHELF / DISPLAY', shelves=8, name='bookshelf', h=48)
    L.armchair(fl, 46950, 10200, 47650, 10900, 'B'); L.armchair(fl, 47750, 10200, 48450, 10900, 'B')
    L.label(47100, 11450, 'FAMILY LOBBY', 3045, 2250, 105)
    # toilets
    L.poly([(44300, 9646), (44300, 8750)], 'A-FURN-SAN', None, False, 0.8)
    L.text((43900, 8550), 'SHOWER', 46, color='#2a6fa8')
    L.label(44700, 8420, 'TOILET', 2135, 1625, 95)
    # master toilet: bathtub with shower over + glass screen, double vanity
    L.rect(48745, 15791, 50455, 16521, 'A-FURN-SAN', '#ffffff', 0.7)
    L.rect(48845, 15871, 50355, 16441, 'A-FURN-SAN', '#e6f1f8', 0.4); L.circ((50155, 16156), 40, 'A-FURN-SAN', None, 0.4)
    L.text((49600, 16156), 'BATHTUB + SHOWER', 50, color='#2a6fa8')
    L.poly([(49300, 15791), (49300, 15400)], 'A-FURN-SAN', None, False, 0.8)
    L.rect(48685, 13300, 49235, 14800, 'A-FURN-SAN', STONE, 0.7)
    for yy in (13700, 14400):
        L.rect(48745, yy - 220, 49135, yy + 220, 'A-FURN-SAN', '#fff', 0.4); L.circ((48800, yy), 25, 'A-FURN-SAN', None, 0.3)
    L.text((49450, 14050), 'DOUBLE\nVANITY', 46, color='#2a6fa8')
    # kids toilet: vanity counter + glass shower
    L.rect(48020, 13300, 48570, 14800, 'A-FURN-SAN', STONE, 0.7)
    L.rect(48130, 13830, 48510, 14270, 'A-FURN-SAN', '#fff', 0.4)
    L.text((47450, 16150), 'WALK-IN SHOWER', 46, color='#2a6fa8')
    for x0, x1, lab in ((46740, 48570, 'TOILET'), (48685, 50515, 'TOILET')):
        L.label((x0 + x1) / 2, 13200 if x0 < 48000 else 13500, lab, 1830, 4455, 95)
    L.text((47450, 14050), 'VANITY', 46, color='#2a6fa8')
    L.label(51850, 15100, 'BALCONY', 2450, 1425, 95)
    L.text((44200, 10900), 'STAIR', 90, color='#777')


ROOMS = [   # name, floor, rect, zone, floor finish
    ('Living + Dining', 'lower', (6894, 9541, 15509, 14416), 'public', 'marble'),
    ('Kitchen', 'lower', (3919, 11850, 6779, 16361), 'service', 'tile'),
    ('Wash', 'lower', (6894, 14531, 9899, 16361), 'service', 'tile'),
    ('Balcony', 'lower', (10014, 14531, 15509, 16361), 'public', 'deck'),
    ('Bedroom-1 (Parents)', 'lower', (3919, 3416, 7884, 7686), 'private', 'wood'),
    ('Toilet', 'lower', (4644, 7801, 6779, 9426), 'service', 'wet'),
    ('Passage', 'lower', (6894, 7801, 7884, 9541), 'circulation', 'marble'),
    ('Staircase', 'lower', (3919, 9541, 6779, 11850), 'circulation', 'stair'),
    ('Bedroom-2 (Son/Guest)', 'upper', (42776, 3636, 46741, 7906), 'private', 'wood'),
    ('Passage', 'upper', (45750, 8021, 46740, 9646), 'circulation', 'wood'),
    ('Toilet BR-2', 'upper', (43500, 8021, 45635, 9646), 'service', 'wet'),
    ('Bedroom-3 (Kids)', 'upper', (42776, 12126, 46625, 16581), 'private', 'wood'),
    ('Toilet BR-3', 'upper', (46740, 12126, 48570, 16581), 'service', 'wet'),
    ('Toilet BR-4', 'upper', (48685, 12126, 50515, 16581), 'service', 'wet'),
    ('Family lobby', 'upper', (45525, 9761, 48570, 12011), 'circulation', 'marble'),
    ('Staircase', 'upper', (42776, 9761, 45525, 12011), 'circulation', 'stair'),
    ('Dress', 'upper', (48685, 9761, 50630, 12011), 'private', 'wood'),
    ('Master Bedroom-4', 'upper', (50630, 9761, 54365, 14636), 'private', 'wood'),
    ('Master balcony', 'upper', (50630, 14751, 53081, 16176), 'private', 'deck'),
]


def room_of(floor, r):
    cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
    for n, fl, rr, z, fin in ROOMS:
        if fl == floor and rr[0] - 5 <= cx <= rr[2] + 5 and rr[1] - 5 <= cy <= rr[3] + 5:
            return rr
    return None


def premium(L):
    # bed-end benches where the foot passage stays >= 750 mm (kids room keeps its play space)
    for name, bed in L.beds:
        if 'BR-3' not in name and 'BR-4' not in name or ('BR-4' in name and L.choices['Master bed head'] == 'R'):
            L.bench_for(bed)
    # living: sofa-end side tables + floor lamp, only where they fit
    sofa = [f for f in L.FOOT if f[0] == 'sofa'][0]
    x0, y0, x1, y1 = sofa[2:6]
    if (y1 - y0) > (x1 - x0):
        cx = (x0 + x1) / 2
        for r in ((cx - 225, y0 - 500, cx + 225, y0 - 50), (cx - 225, y1 + 50, cx + 225, y1 + 500)):
            L.optional('sofa side table', 'lower', r, lambda r=r: (L.rect(*r, 'A-FURN', WOOD, 0.6), L.circ(((r[0] + r[2]) / 2, (r[1] + r[3]) / 2), 120, 'A-FURN', '#fff', 0.3)))
    ct = [f for f in L.FOOT if f[0] == 'coffee table'][0]
    ccx, ccy = (ct[2] + ct[4]) / 2, (ct[3] + ct[5]) / 2
    L.circ((ccx, ccy), 380, 'A-CLG', None, 0.5); L.circ((ccx, ccy), 120, 'A-CLG', None, 0.4)
    L.text((ccx, ccy - 470), 'FEATURE LIGHT', 40, color='#8a7a9a')
    L.circ((8500, 12200), 520, 'A-CLG', None, 0.5)
    for a in range(0, 360, 45):
        L.circ((8500 + 420 * math.cos(math.radians(a)), 12200 + 420 * math.sin(math.radians(a))), 45, 'A-CLG', None, 0.4)
    L.text((8500, 11560), 'CHANDELIER', 40, color='#8a7a9a')
    # cove ceilings (dashed): living, dining, parents and master bedrooms
    for r in ((10464, 9991, 15059, 13966), (7344, 9991, 9564, 13966), (4369, 3866, 7434, 7236), (51080, 10211, 53915, 14186)):
        L.rect(*r, 'A-CLG', None, 0.45, ':')
    # brass inlay medallion at the main door (floor)
    for rr in (330, 230, 90):
        L.circ((9104, 10180), rr, 'A-FLOOR-INLAY', None, 0.5)
    for a in range(0, 360, 30):
        L.poly([(9104 + 90 * math.cos(math.radians(a)), 10180 + 90 * math.sin(math.radians(a))),
                (9104 + 330 * math.cos(math.radians(a)), 10180 + 330 * math.sin(math.radians(a)))], 'A-FLOOR-INLAY', None, False, 0.3)
    L.text((9104, 10600), 'BRASS INLAY', 40, color='#a07a2a')
    # premium specification call-outs
    pj = [f for f in L.FOOT if f[0] == 'pooja unit'][0]
    L.text(((pj[2] + pj[4]) / 2, (pj[3] + pj[5]) / 2 - 330 if pj[3] > 12000 else (pj[3] + pj[5]) / 2 + 330),
           'MARBLE BACKDROP · CNC JAALI\nSHUTTERS · BRASS BELLS', 38, color='#8a4b00')
    L.text((5350, 12350), 'QUARTZ TOP · BUILT-IN OVEN\n+ MW STACK · COFFEE STATION', 40, color='#777')
    L.text((47050, 11900), 'ART WALL + PICTURE LIGHT', 42, color='#777')


def place_labels(L):
    """move each room tag to the nearest spot (within 1.6 m) where it covers no furniture."""
    for x, y, name, w, d, h, sub in L.labels:
        if not name:
            continue
        floor = 'lower' if x < 30000 else 'upper'
        bw = max(len(name) * h * 0.72, 900 if w else 0) / 2
        top, bot = h * 1.0, (h * 0.9 if w else 0) + (h * 0.95 if sub else 0) + h * 0.4
        room = room_of(floor, (x, y, x, y))
        best = (x, y)
        cands = sorted(((x + dx, y + dy) for dx in range(-1600, 1601, 100) for dy in range(-1600, 1601, 100)),
                       key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
        for cx, cy in cands:
            box = (cx - bw, cy - bot, cx + bw, cy + top)
            if room and not (room[0] + 60 <= box[0] and box[2] <= room[2] - 60 and room[1] + 60 <= box[1] and box[3] <= room[3] - 60):
                continue
            if any(it[1] == floor and it[6] in ('furn', 'inbuilt') and _overlap(box, it[2:6], 0) for it in L.FOOT):
                continue
            best = (cx, cy); break
        L._draw_label(best[0], best[1], name, w, d, h, sub)


def finalize(L):
    place_labels(L)
    """wardrobe shutter logic: measure the clear floor in front; < 900 mm -> sliding, else hinged."""
    L.wardrobe_report = []
    for floor, r, f, label, loft, W in L.wards:
        room = room_of(floor, r) or r
        fr = f.f
        if fr == 'N': clear = room[3] - r[3]
        elif fr == 'S': clear = r[1] - room[1]
        elif fr == 'E': clear = room[2] - r[2]
        else: clear = r[0] - room[0]
        for it in L.FOOT:
            if it[1] != floor or it[6] != 'furn' or it[2:6] == r: continue
            a = it[2:6]
            if fr in 'NS' and a[0] < r[2] - 5 and a[2] > r[0] + 5:
                d = a[1] - r[3] if fr == 'N' else r[1] - a[3]
            elif fr in 'EW' and a[1] < r[3] - 5 and a[3] > r[1] + 5:
                d = a[0] - r[2] if fr == 'E' else r[0] - a[2]
            else:
                continue
            if d >= -5: clear = min(clear, max(d, 0))
        sliding = clear < 900
        if sliding:
            f.line(0, f.D - 60, f.W * 0.55, f.D - 60, 'A-FURN-WARD', 0.35)
        L.text(f.t(W / 2, f.D / 2 + 40), f"{label}{' + LOFT' if loft else ''}\n{'SLIDING' if sliding else 'HINGED'} · {int(W)} RM", 58)
        L.wardrobe_report.append((label, floor, int(W), int(clear), 'SLIDING' if sliding else 'HINGED'))


def build(compass, unit='A'):
    L = Layout(compass, unit)
    living_dining(L); kitchen(L); bedroom1(L); lower_misc(L)
    bedroom2(L); bedroom3(L); bedroom4(L); upper_misc(L)
    premium(L); finalize(L)
    return L


# ======================================================================== checks
def _overlap(a, b, tol=5):
    return a[0] < b[2] - tol and b[0] < a[2] - tol and a[1] < b[3] - tol and b[1] < a[3] - tol


def _rect_hits_arc(r, arc):
    hx, hy, R, x0, y0, x1, y1 = arc
    step = 25
    x = max(r[0], x0)
    while x <= min(r[2], x1):
        y = max(r[1], y0)
        while y <= min(r[3], y1):
            if (x - hx) ** 2 + (y - hy) ** 2 < (R - 10) ** 2 and r[0] + 5 < x < r[2] - 5 and r[1] + 5 < y < r[3] - 5:
                return True
            y += step
        x += step
    return False


def check(L):
    """Returns a list of problems (empty = every item clear of every other item and every keep-clear zone)."""
    probs = []
    items = [f for f in L.FOOT if f[6] == 'furn']
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if a[1] == b[1] and _overlap(a[2:6], b[2:6]):
                probs.append(f'{a[0]} overlaps {b[0]}')
        for k in L.KEEP:
            if k[1] != a[1]:
                continue
            if k[2] == 'rect' and _overlap(a[2:6], k[3]):
                probs.append(f'{a[0]} blocks {k[0]}')
            if k[2] == 'arc' and _rect_hits_arc(a[2:6], k[3]):
                probs.append(f'{a[0]} inside {k[0]}')
    return probs


# ======================================================================== orientation + Vastu audit
SIDES_CW = ['T', 'R', 'B', 'L']
COMPASS_CW = ['N', 'E', 'S', 'W']


def compass_for(north_side):
    """building compass: which compass direction each drawing side faces, given which side is North."""
    i = SIDES_CW.index(north_side)
    return {SIDES_CW[(i + k) % 4]: COMPASS_CW[k] for k in range(4)}


def mirror_compass(c):
    m = dict(c); m['L'], m['R'] = c['R'], c['L']
    return m


def zone(c, u, v):
    """u,v in 0..1 within the unit bbox -> compass zone name."""
    h = 'L' if u < 1 / 3 else ('R' if u > 2 / 3 else None)
    w = 'B' if v < 1 / 3 else ('T' if v > 2 / 3 else None)
    parts = [c[s] for s in (w, h) if s]
    if not parts:
        return 'Centre'
    order = 'NSEW'
    return ''.join(sorted(parts, key=order.index))


FIXED = {   # builder elements that cannot move: (floor bbox, centroid)
    'Kitchen': ('lower', (5349, 14130)),
    'Toilet (lower)': ('lower', (5711, 8613)),
    'Staircase': ('lower', (5349, 10670)),
    'Toilet BR-2': ('upper', (44568, 8833)),
    'Toilet BR-3': ('upper', (47655, 14353)),
    'Toilet BR-4': ('upper', (49600, 14353)),
}
BBOX = {'lower': (3919, 3416, 15509, 16361), 'upper': (42776, 3636, 54365, 16581)}
GOOD = {'Kitchen': ({'SE'}, {'NW', 'S', 'E'}),
        'Staircase': ({'S', 'W', 'SW'}, {'SE', 'NW'}),
        'Toilet': ({'W', 'NW'}, {'S', 'SE', 'E', 'N'})}
BAD_TOILET = {'NE', 'SW', 'Centre'}


def vastu_audit(c):
    rows = []
    for name, (fl, (x, y)) in FIXED.items():
        b = BBOX[fl]
        z = zone(c, (x - b[0]) / (b[2] - b[0]), (y - b[1]) / (b[3] - b[1]))
        key = 'Toilet' if name.startswith('Toilet') else name
        best, ok = GOOD[key]
        if z in best:
            r = 'IDEAL'
        elif z in ok:
            r = 'ACCEPTABLE'
        elif key == 'Toilet' and z not in BAD_TOILET:
            r = 'ACCEPTABLE'
        else:
            r = 'NOT IDEAL'
        rows.append((name, z, r))
    door = c['B']   # main door opens off the common lobby on the drawing-bottom side
    rows.append(('Main door faces', door, 'IDEAL' if door in ('N', 'E') else ('ACCEPTABLE' if door == 'W' else 'NOT IDEAL')))
    return rows
