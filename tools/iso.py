#!/usr/bin/env python3
"""Rewrite a PlantUML SVG into a static isometric SVG.

The floor of the diagram is tilted into the isometric plane. Every filled shape becomes a
block: its top face keeps the original fill, and two shaded side faces give it depth. Lines,
arrows and the text that sits on a block are projected too, so the result needs no script
to display. Only the Python standard library is used.

Usage: iso.py [--variant light|dark] [--depth N] input.svg output.svg
"""
import argparse
import math
import re
import xml.etree.ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

COS = math.cos(math.radians(30))
SIN = math.sin(math.radians(30))

# the projection matrix (a, b, c, d): screen x = a*x + c*y, screen y = b*x + d*y
LEAN = {
    "right": (COS, SIN, -COS, SIN),  # the x axis of the floor runs down to the right
    "left": (COS, -SIN, COS, SIN),  # the x axis of the floor runs up to the right
}
M = LEAN["right"]


def project(x, y):
    """Map a floor point to the screen."""
    a, b, c, d = M
    return a * x + c * y, b * x + d * y


def parse_style(el):
    style = {}
    for part in el.get("style", "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            style[k.strip()] = v.strip()
    for k in ("fill", "stroke", "stroke-width"):
        if el.get(k) is not None:
            style[k] = el.get(k)
    return style


def color_to_rgb(value):
    value = value.strip()
    if not value.startswith("#"):
        return None
    hexpart = value[1:]
    if len(hexpart) == 3:
        hexpart = "".join(c * 2 for c in hexpart)
    if len(hexpart) < 6:
        return None
    return tuple(int(hexpart[i:i + 2], 16) for i in (0, 2, 4))


def shade(value, factor):
    rgb = color_to_rgb(value)
    if rgb is None:
        return value
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * factor))) for c in rgb)


def tag(el):
    return el.tag.split("}")[-1]


def points_of(el):
    """The floor outline of a shape, as a list of points."""
    t = tag(el)
    if t == "rect":
        x, y = float(el.get("x", 0)), float(el.get("y", 0))
        w, h = float(el.get("width", 0)), float(el.get("height", 0))
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    if t == "polygon":
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", el.get("points", ""))]
        return list(zip(nums[0::2], nums[1::2]))
    if t == "ellipse":
        cx, cy = float(el.get("cx", 0)), float(el.get("cy", 0))
        rx, ry = float(el.get("rx", 0)), float(el.get("ry", 0))
        return [(cx + rx * math.cos(a), cy + ry * math.sin(a))
                for a in (math.radians(d) for d in range(0, 360, 10))]
    return None


def bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def is_block(el, background):
    """A filled shape with a visible area is a block. Arrow heads and bars stay flat."""
    points = points_of(el)
    if not points:
        return False
    style = parse_style(el)
    fill = style.get("fill", "none")
    if fill in ("none", "transparent") or fill.lower() == background.lower():
        return False
    x0, y0, x1, y1 = bbox(points)
    if tag(el) == "ellipse":
        return (x1 - x0) >= 24 and (y1 - y0) >= 24  # small circles are decorations, such as circled letters
    return (x1 - x0) >= 14 and (y1 - y0) >= 10


def fmt(n):
    return ("%.2f" % n).rstrip("0").rstrip(".")


def polygon(points, fill, stroke=None, width=None):
    el = ET.Element("{%s}polygon" % SVG)
    el.set("points", " ".join("%s,%s" % (fmt(x), fmt(y)) for x, y in points))
    el.set("fill", fill)
    if stroke:
        el.set("stroke", stroke)
        el.set("stroke-width", fmt(width or 1))
        el.set("stroke-linejoin", "round")
    return el


def clockwise(points):
    """The outline in screen orientation, so that the outward normals point out."""
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]))
    return points if area >= 0 else list(reversed(points))


def side_faces(points, depth, fill, stroke, smooth=False):
    """Side faces for the edges that face the viewer. The face turned to the right is lighter.
    With smooth, the visible edges form one face, as for the side of a cylinder."""
    faces = []
    points = clockwise(points)
    n = len(points)
    if smooth:
        visible = []
        for i in range(n):
            (ax, ay), (bx, by) = points[i], points[(i + 1) % n]
            nx, ny = (by - ay), -(bx - ax)
            if project(nx, ny)[1] > 0:
                visible.append(i)
        if not visible:
            return faces
        # rotate so that the visible run starts at its first edge
        start = next((i for i in visible if (i - 1) % n not in visible), visible[0])
        run = [start]
        while (run[-1] + 1) % n in visible and len(run) < len(visible):
            run.append((run[-1] + 1) % n)
        floor = [project(*points[i]) for i in run] + [project(*points[(run[-1] + 1) % n])]
        top = [(x, y - depth) for x, y in reversed(floor)]
        faces.append(polygon(floor + top, shade(fill, 0.74), stroke, 0.8))
        return faces
    for i in range(n):
        (ax, ay), (bx, by) = points[i], points[(i + 1) % n]
        sax, say = project(ax, ay)
        sbx, sby = project(bx, by)
        nx, ny = (by - ay), -(bx - ax)  # outward normal of the edge, in floor space
        snx, sny = project(nx, ny)  # the same normal on the screen
        if sny <= 0:
            continue  # the face is turned away from the viewer
        lit = snx > 0
        quad = [(sax, say), (sbx, sby), (sbx, sby - depth), (sax, say - depth)]
        faces.append(polygon(quad, shade(fill, 0.82 if lit else 0.66), stroke, 0.8))
    return faces


def iso_transform(lift):
    a, b, c, d = M
    return "translate(0,%s) matrix(%s %s %s %s 0 0)" % (fmt(-lift), fmt(a), fmt(b), fmt(c), fmt(d))


def anchor_of(el):
    """The floor point that decides which blocks an element sits on."""
    t = tag(el)
    if t == "text":
        return float(el.get("x", 0)), float(el.get("y", 0)) - 4
    if t == "image":
        return (float(el.get("x", 0)) + float(el.get("width", 0)) / 2,
                float(el.get("y", 0)) + float(el.get("height", 0)) / 2)
    pts = points_of(el)
    if pts:
        x0, y0, x1, y1 = bbox(pts)
        return (x0 + x1) / 2, (y0 + y1) / 2
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", el.get("d", "") or
                                         "%s %s" % (el.get("x1", 0), el.get("y1", 0)))]
    if len(nums) >= 2:
        return nums[0], nums[1]
    return None


def contains(outer, inner):
    ox0, oy0, ox1, oy1 = outer
    x0, y0, x1, y1 = inner
    return ox0 <= x0 and oy0 <= y0 and ox1 >= x1 and oy1 >= y1 and \
        (ox1 - ox0) * (oy1 - oy0) > (x1 - x0) * (y1 - y0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=("light", "dark"), default="light")
    ap.add_argument("--depth", type=float, default=16.0)
    ap.add_argument("--lean", choices=("right", "left"), default="right")
    ap.add_argument("src")
    ap.add_argument("dst")
    args = ap.parse_args()
    global M
    M = LEAN[args.lean]

    tree = ET.parse(args.src)
    root = tree.getroot()
    vb_attr = root.get("viewBox")
    if vb_attr:
        vb = [float(n) for n in vb_attr.split()]
    else:
        vb = [0, 0, float(root.get("width", "0").rstrip("px")), float(root.get("height", "0").rstrip("px"))]
    background = "#121212" if args.variant == "dark" else "#ffffff"
    floor_fill = "#1b2028" if args.variant == "dark" else "#eef1f6"
    floor_stroke = "#2d343e" if args.variant == "dark" else "#d9dee8"
    depth = args.depth

    elements = list(root.iter())
    blocks = []
    for el in elements:
        if tag(el) in ("rect", "polygon", "ellipse") and is_block(el, background):
            pts = points_of(el)
            blocks.append((el, pts, bbox(pts)))

    def is_band(box):
        """A shape that spans the full width of a block from its top edge is a header band, not a block."""
        x0, y0, x1, y1 = box
        for _, _, (ox0, oy0, ox1, oy1) in blocks:
            if (ox0, oy0, ox1, oy1) == box:
                continue
            if abs(ox0 - x0) <= 1.5 and abs(ox1 - x1) <= 1.5 and abs(oy0 - y0) <= 1.5 and oy1 > y1:
                return True
        return False

    bands = [b for b in blocks if is_band(b[2])]
    blocks = [b for b in blocks if not is_band(b[2])]

    def containers_of(box, me=None):
        return sum(1 for other, _, obox in blocks if other is not me and contains(obox, box))

    def level_at(px, py):
        """How many blocks a floor point is inside."""
        return sum(1 for _, _, (x0, y0, x1, y1) in blocks if x0 <= px <= x1 and y0 <= py <= y1)

    def level_of(el):
        """How many blocks an element is inside. A block itself counts its containers."""
        if any(el is b[0] for b in blocks):
            return containers_of(bbox(points_of(el)), el)
        anchor = anchor_of(el)
        return level_at(*anchor) if anchor else 0

    def endpoints(group):
        """The first and the last point of the lines in a link group."""
        pts = []
        for el in group.iter():
            t = tag(el)
            if t == "line":
                pts += [(float(el.get("x1", 0)), float(el.get("y1", 0))), (float(el.get("x2", 0)), float(el.get("y2", 0)))]
            elif t == "path":
                nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", el.get("d", ""))]
                if len(nums) >= 4:
                    pts += [(nums[0], nums[1]), (nums[-2], nums[-1])]
        return pts

    # Every element gets a level: the number of blocks it stands in. A link group shares one level, the
    # highest of its two ends, so that the arrowhead stays on its line and a link leaving a package runs
    # over the floor at the height of the package top.
    link_groups = [g for g in root.iter("{%s}g" % SVG) if (g.get("class") or "").split()[:1] in (["link"], ["message"])]
    in_link = {id(el): g for g in link_groups for el in g.iter() if el is not g}
    link_level = {}
    for g in link_groups:
        pts = endpoints(g)
        link_level[id(g)] = max((level_at(x, y) for x, y in pts), default=0)

    items = []  # (level, kind, order, element); kind 0 = band on a block top, 1 = filled flat shape, 2 = line, text, icon, 3 = block

    def draw_band(el, pts, level):
        style = parse_style(el)
        stroke = style.get("stroke") if style.get("stroke", "none") != "none" else None
        face = polygon([project(x, y) for x, y in pts], style.get("fill", "#ffffff"), stroke,
                       float(style.get("stroke-width", "1").rstrip("px") or 1))
        face.set("transform", "translate(0,%s)" % fmt(-level * depth))
        return face

    def draw_block(el, pts, level, smooth):
        style = parse_style(el)
        fill = style.get("fill", "#ffffff")
        stroke = style.get("stroke") if style.get("stroke", "none") != "none" else None
        width = float(style.get("stroke-width", "1").rstrip("px") or 1)
        group = ET.Element("{%s}g" % SVG)
        group.set("transform", "translate(0,%s)" % fmt(-level * depth))
        for face in side_faces(pts, depth, fill, stroke, smooth=smooth):
            group.append(face)
        top = [(px, py - depth) for px, py in (project(x, y) for x, y in pts)]
        group.append(polygon(top, fill, stroke, width))
        return group

    def front_y(el):
        """The screen y of the nearest edge, used to paint from back to front."""
        pts = points_of(el)
        if not pts and tag(el) == "path":
            nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", el.get("d", ""))]
            pts = list(zip(nums[0::2], nums[1::2]))
        if not pts:
            a = anchor_of(el)
            pts = [a] if a else [(0, 0)]
        return max(project(x, y)[1] for x, y in pts)

    def flat_kind(el):
        """Filled flat shapes, such as the body of a composite state, go under lines and text."""
        if tag(el) in ("path", "rect", "polygon", "ellipse") and parse_style(el).get("fill", "none") != "none":
            return 1
        return 2

    def flat_order(el):
        """Filled flat shapes paint from large to small, so that a dot stays visible on a sheet."""
        if flat_kind(el) == 1:
            pts = points_of(el)
            if not pts and tag(el) == "path":
                nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", el.get("d", ""))]
                pts = list(zip(nums[0::2], nums[1::2]))
            if pts:
                x0, y0, x1, y1 = bbox(pts)
                return -(x1 - x0) * (y1 - y0)
        return front_y(el)

    for el in elements:
        t = tag(el)
        if t in ("svg", "g", "defs", "style", "title", "desc"):
            continue
        if id(el) in in_link:
            g = in_link[id(el)]
            level = link_level[id(g)]
            wrapper = ET.Element("{%s}g" % SVG)
            wrapper.set("transform", iso_transform(level * depth))
            wrapper.append(el)
            items.append((level, 2, front_y(el), wrapper))
            continue
        level = level_of(el)
        band = next((b for b in bands if b[0] is el), None)
        if band is not None:
            items.append((level, 0, front_y(el), draw_band(el, band[1], level)))
            continue
        block = next((b for b in blocks if b[0] is el), None)
        if block is not None:
            items.append((level, 3, front_y(el), draw_block(el, block[1], level, t == "ellipse")))
            continue
        wrapper = ET.Element("{%s}g" % SVG)
        wrapper.set("transform", iso_transform(level * depth))
        wrapper.append(el)
        items.append((level, flat_kind(el), flat_order(el), wrapper))

    out = ET.Element("{%s}svg" % SVG)
    corners = [project(vb[0], vb[1]), project(vb[0] + vb[2], vb[1]),
               project(vb[0] + vb[2], vb[1] + vb[3]), project(vb[0], vb[1] + vb[3])]
    max_lift = (max((lvl for lvl, _, _, _ in items), default=0) + 1) * depth
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    margin = 24
    x0, y0 = min(xs) - margin, min(ys) - margin - max_lift
    x1, y1 = max(xs) + margin, max(ys) + margin + 8
    out.set("viewBox", "%s %s %s %s" % (fmt(x0), fmt(y0), fmt(x1 - x0), fmt(y1 - y0)))
    out.set("width", fmt(x1 - x0))
    out.set("height", fmt(y1 - y0))

    bg = ET.SubElement(out, "{%s}rect" % SVG)
    bg.set("x", fmt(x0)); bg.set("y", fmt(y0)); bg.set("width", fmt(x1 - x0)); bg.set("height", fmt(y1 - y0))
    bg.set("fill", background)
    # the floor plate with a thin edge
    floor_pts = [(vb[0], vb[1]), (vb[0] + vb[2], vb[1]), (vb[0] + vb[2], vb[1] + vb[3]), (vb[0], vb[1] + vb[3])]
    plate = ET.SubElement(out, "{%s}g" % SVG)
    plate.set("transform", "translate(0,6)")  # the plate hangs 6 below the floor level
    for face in side_faces(floor_pts, 6, floor_fill, floor_stroke):
        plate.append(face)
    plate.append(polygon([(x, y - 6) for x, y in corners], floor_fill, floor_stroke, 1))

    for el in list(root):
        if tag(el) in ("defs", "style"):
            out.append(el)

    # Paint order: level by level; on each level first the header bands, then filled flat shapes, then
    # lines, text and icons, then the blocks that stand on it, from back to front. A link that points at
    # a block ends under its base.
    for _, _, _, node in sorted(items, key=lambda i: (i[0], i[1], i[2])):
        out.append(node)

    ET.ElementTree(out).write(args.dst, xml_declaration=True, encoding="UTF-8")


if __name__ == "__main__":
    main()
