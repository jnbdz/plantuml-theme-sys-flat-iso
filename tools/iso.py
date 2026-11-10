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


def project(x, y):
    """Map a floor point to the screen."""
    return (x - y) * COS, (x + y) * SIN


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


def side_faces(points, depth, fill, stroke):
    """Side faces for the edges that face the viewer, darker on the left than on the right."""
    faces = []
    n = len(points)
    for i in range(n):
        (ax, ay), (bx, by) = points[i], points[(i + 1) % n]
        sax, say = project(ax, ay)
        sbx, sby = project(bx, by)
        # the outward normal of this edge, in floor space (clockwise outline)
        nx, ny = (by - ay), -(bx - ax)
        # faces whose normal points down the screen are visible
        screen_ny = (nx + ny) * SIN
        if screen_ny <= 0:
            continue
        lit = (nx - ny) > 0  # faces turned to the right catch more light
        quad = [(sax, say), (sbx, sby), (sbx, sby - depth), (sax, say - depth)]
        faces.append(polygon(quad, shade(fill, 0.82 if lit else 0.66), stroke, 0.8))
    return faces


def iso_transform(lift):
    return "translate(0,%s) matrix(%s %s %s %s 0 0)" % (fmt(-lift), fmt(COS), fmt(SIN), fmt(-COS), fmt(SIN))


def contains(outer, inner):
    ox0, oy0, ox1, oy1 = outer
    x0, y0, x1, y1 = inner
    return ox0 <= x0 and oy0 <= y0 and ox1 >= x1 and oy1 >= y1 and \
        (ox1 - ox0) * (oy1 - oy0) > (x1 - x0) * (y1 - y0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=("light", "dark"), default="light")
    ap.add_argument("--depth", type=float, default=16.0)
    ap.add_argument("src")
    ap.add_argument("dst")
    args = ap.parse_args()

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

    def containers_of(box, me=None):
        return sum(1 for other, _, obox in blocks if other is not me and contains(obox, box))

    def lift_of(el):
        """One depth per block that contains the element. Text and lines on a block rise with it."""
        t = tag(el)
        if t == "text":
            px, py = float(el.get("x", 0)), float(el.get("y", 0)) - 4
            count = sum(1 for _, _, (x0, y0, x1, y1) in blocks if x0 <= px <= x1 and y0 <= py <= y1)
            return count * depth
        pts = points_of(el)
        if pts:
            return containers_of(bbox(pts), el) * depth
        if t in ("line", "path"):
            nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", el.get("d", "") or
                                                 "%s %s %s %s" % (el.get("x1", 0), el.get("y1", 0), el.get("x2", 0), el.get("y2", 0)))]
            if len(nums) >= 2:
                mx, my = nums[0], nums[1]
                count = sum(1 for _, _, (x0, y0, x1, y1) in blocks if x0 <= mx <= x1 and y0 <= my <= y1)
                return count * depth
        return 0

    out = ET.Element("{%s}svg" % SVG)
    corners = [project(vb[0], vb[1]), project(vb[0] + vb[2], vb[1]),
               project(vb[0] + vb[2], vb[1] + vb[3]), project(vb[0], vb[1] + vb[3])]
    max_lift = max((containers_of(b, el) for el, _, b in blocks), default=0) * depth + depth
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
    for i in (1, 2):
        (ax, ay), (bx, by) = corners[i], corners[(i + 1) % 4]
        out.append(polygon([(ax, ay), (bx, by), (bx, by + 6), (ax, ay + 6)], shade(floor_fill, 0.85 if i == 1 else 0.75), floor_stroke, 1))
    out.append(polygon(corners, floor_fill, floor_stroke, 1))

    for el in list(root):
        if tag(el) in ("defs", "style"):
            out.append(el)

    for el in elements:
        t = tag(el)
        if t in ("svg", "g", "defs", "style", "title", "desc"):
            continue
        lift = lift_of(el)
        block = next((b for b in blocks if b[0] is el), None)
        if block is not None:
            _, pts, _ = block
            style = parse_style(el)
            fill = style.get("fill", "#ffffff")
            stroke = style.get("stroke") if style.get("stroke", "none") != "none" else None
            width = float(style.get("stroke-width", "1").rstrip("px") or 1)
            group = ET.SubElement(out, "{%s}g" % SVG)
            group.set("transform", "translate(0,%s)" % fmt(-lift))
            for face in side_faces(pts, depth, fill, stroke):
                group.append(face)
            top = [(px, py - depth) for px, py in (project(x, y) for x, y in pts)]
            group.append(polygon(top, fill, stroke, width))
            continue
        on_block = lift > 0 or (t == "text" and any(
            bx0 <= float(el.get("x", 0)) <= bx1 and by0 <= float(el.get("y", 0)) - 4 <= by1
            for _, _, (bx0, by0, bx1, by1) in blocks))
        total = lift + (depth if on_block else 0)
        wrapper = ET.SubElement(out, "{%s}g" % SVG)
        wrapper.set("transform", iso_transform(total))
        wrapper.append(el)

    ET.ElementTree(out).write(args.dst, xml_declaration=True, encoding="UTF-8")


if __name__ == "__main__":
    main()
