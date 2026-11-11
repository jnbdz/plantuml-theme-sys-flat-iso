# plantuml-theme-sys-flat-iso

Two looks for PlantUML diagrams, each in a light and a dark variant, and the isometric one leaning right or left:

- **sys-flat**: a flat theme in the Quarkus palette. Soft cards, thin borders, one accent colour, no shadows.
- **sys-iso**: the same diagrams as isometric blocks on a tilted floor. The theme renders the diagram, and a small script rewrites the SVG. The result is a static SVG that needs no JavaScript.

The look is a marriage of [Langfuse](https://langfuse.com/) and the [Quarkus](https://quarkus.io/) light and dark styles. The isometric variant takes its idea from projects such as [Arc](https://github.com/hudsonkit/arc) and [Anatomy](https://github.com/wheresryan22/anatomy). No code or asset comes from them.

See the [gallery](gallery/README.md) for every diagram type in the four variants.

## Use the flat theme

```
@startuml
!theme sys-flat from https://raw.githubusercontent.com/jnbdz/plantuml-theme-sys-flat-iso/main/themes
...
@enduml
```

Use `sys-flat-dark` for the dark variant. For a local copy, point `from` at the `themes` directory.

C4 diagrams need one more include, after the C4 include and after the theme, because the C4 library sets its own element styles:

```
!include <C4/C4_Container>
!theme sys-flat from https://raw.githubusercontent.com/jnbdz/plantuml-theme-sys-flat-iso/main/themes
!include https://raw.githubusercontent.com/jnbdz/plantuml-theme-sys-flat-iso/main/themes/c4-sys-flat.puml
```

The theme names its colours as variables, for example `$SYS_ACCENT` and `$SYS_CARD`. A diagram can use them for its own colours.

## Make an isometric diagram

Render the diagram with the flat theme to SVG, then run the script:

```
plantuml -tsvg diagram.puml
python3 tools/iso.py --variant light diagram.svg diagram-iso.svg
```

`--variant dark` matches `sys-flat-dark`. `--lean left` tilts the floor the other way, so that the x axis runs up to the right. `--depth` sets the height of the blocks, 16 by default. The script uses only the Python standard library.

What the script does:

- It tilts the floor into the isometric plane.
- Every filled rectangle, polygon or ellipse becomes a block. The top keeps the fill of the shape, and the side faces take darker shades of it. An ellipse becomes a cylinder.
- A block inside another block stands on top of it. Text, icons and lines inside a block rise with it.
- A band across the top of a block, such as a class header, stays on the top face. Small circles, such as the circled letters of a class, stay flat.
- A link keeps one height with its arrowhead and label: the height of the higher of its two ends. Blocks paint over the links that point at them, so an arrow ends at the base of its target instead of crossing it.
- Lines and arrows stay on the surface they belong to.

Limits of the first version:

- Shapes that PlantUML draws as paths, such as databases, clouds and actors, stay flat on the floor.
- Text is projected with the floor, so it is slanted. An option for upright labels is a possible next step.
- Curved lines keep their shape; the projection does not bend them.

## Render the gallery

`tools/render.sh` renders every file in `examples` in the six variants with the PlantUML container image and writes the result to `gallery`. It needs `podman` or `docker`, `python3` and, for the PNG previews, `rsvg-convert`.

```
tools/render.sh
```

Set `CONTAINER_RUNNER=docker` to use Docker. The script mounts the `fonts` directory of the repository, which holds Open Sans (OFL 1.1), the font of the Quarkus site and of the Quarkus PlantUML theme; set `FONTS_DIR` to another directory to use other fonts.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Fonts

The themes use Open Sans, the font of the Quarkus site and of the Quarkus PlantUML theme. The `fonts/open-sans` directory holds the font files under the SIL Open Font License 1.1 (see `fonts/open-sans/COPYRIGHT`). Install them, or mount them into the PlantUML container as `tools/render.sh` does, so that PlantUML measures the text with the same font that shows it.
