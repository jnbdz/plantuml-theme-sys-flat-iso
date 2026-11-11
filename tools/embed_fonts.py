#!/usr/bin/env python3
"""Embed a Latin subset of Open Sans into an SVG, so that it renders the same in every viewer.

Usage: embed_fonts.py <fonts dir> <svg>...   (rewrites the files in place)
"""
import base64
import io
import os
import re
import sys

from fontTools import subset
from fontTools.ttLib import TTFont

FACES = [("OpenSans-Regular.ttf", "normal", "normal"), ("OpenSans-Bold.ttf", "bold", "normal"),
         ("OpenSans-Italic.ttf", "normal", "italic"), ("OpenSans-BoldItalic.ttf", "bold", "italic")]
UNICODES = "U+0020-007E,U+00A0-00FF,U+2013-2014,U+2018-201D,U+2026,U+00AB,U+00BB,U+2192,U+2190"


def woff2(path):
    font = TTFont(path)
    options = subset.Options(flavor="woff2", hinting=False, desubroutinize=True)
    sub = subset.Subsetter(options)
    sub.populate(unicodes=subset.parse_unicodes(UNICODES))
    sub.subset(font)
    font.flavor = "woff2"
    out = io.BytesIO()
    font.save(out)
    return base64.b64encode(out.getvalue()).decode("ascii")


def main():
    fonts, files = sys.argv[1], sys.argv[2:]
    rules = []
    for name, weight, style in FACES:
        data = woff2(os.path.join(fonts, name))
        rules.append("@font-face{font-family:'Open Sans';font-weight:%s;font-style:%s;src:url(data:font/woff2;base64,%s) format('woff2')}"
                     % (weight, style, data))
    block = "<style>%s</style>" % "".join(rules)
    for f in files:
        s = open(f, encoding="utf-8").read()
        s = re.sub(r"<style>@font-face\{font-family:'Open Sans'.*?</style>", "", s, flags=re.S)
        s = re.sub(r"(<svg\b[^>]*>)", r"\1" + block.replace("\\", "\\\\"), s, count=1)
        open(f, "w", encoding="utf-8").write(s)
    print("embedded Open Sans in %d files" % len(files))


if __name__ == "__main__":
    main()
