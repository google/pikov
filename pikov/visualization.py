# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Helpers for visualizing pikov networks."""

import math

try:
    import networkx
except ImportError:
    networkx = None


# TODO: calculate sizes based on number of nodes in graph.
LINE_WIDTH = 0.006
IMAGE_SIZE = 0.04
# LINE_WIDTH = 0.03
# IMAGE_SIZE = 0.3
LINE_COLOR = '#83769c'  # 'lightblue'
ARROW_WIDTH = LINE_WIDTH * 4
ARROW_POINT = ARROW_WIDTH / 3.0

# Radius to the corner of the image.
IMAGE_RADIUS = (IMAGE_SIZE / 2.0) * math.sqrt(2.0)
IMAGE_MARGIN = 0
# IMAGE_MARGIN = -0.03
IMAGE_RADIUS += IMAGE_MARGIN
VIEWBOX_COORDS = -1.0 - (IMAGE_SIZE / 2)
VIEWBOX_SIZE = 2.0 * abs(VIEWBOX_COORDS)


def arrow_head(x, y, angle):
    x_start = x + (
        -1.0 * math.cos(angle) * ARROW_POINT +
        -1.0 * math.sin(angle) * ARROW_WIDTH / 2.0
    )
    x_end = x + (
        -1.0 * math.cos(angle) * ARROW_POINT +
        math.sin(angle) * ARROW_WIDTH / 2.0
    )
    y_start = y + (
        math.cos(angle) * ARROW_WIDTH / 2.0 +
        -1.0 * math.sin(angle) * ARROW_POINT
    )
    y_end = y + (
        -1.0 * math.cos(angle) * ARROW_WIDTH / 2.0 +
        -1.0 * math.sin(angle) * ARROW_POINT
    )
    return (
        f'<path d="M {x_start} {y_start} L {x} {y} {x_end} {y_end}" '
        f'stroke="{LINE_COLOR}" stroke-width="{LINE_WIDTH}" fill="none" />'
    )


def render_svg(graph, positions=None):
    """Render a graph of frames as an SVG.

    Args:
        graph (networkx.DiGraph):
            A networkx graph, where nodes are pikov.Frame objects.
        positions (Optional[Dict[pikov.Frame, Tuple[float, float]]]):
            Positions of the nodes, assumed to be in -1 to 1 x/y coordinate
            space. If not specified, uses the
            :func:`networkx.drawing.layout.kamada_kawai_layout` layout.
    """
    if positions is None:
        positions = networkx.drawing.layout.kamada_kawai_layout(graph)

    lines = []
    for source, target in graph.edges:
        if source != target:
            x1, y1 = positions[source]
            x2, y2 = positions[target]
            ydiff = y2 - y1
            xdiff = x2 - x1
            angle = math.atan2(ydiff, xdiff)
            xo = math.cos(angle) * IMAGE_RADIUS
            yo = math.sin(angle) * IMAGE_RADIUS
            line = (
                f'<line x1="{x1 + xo}" y1="{y1 + yo}" '
                f'x2="{x2 - xo}" y2="{y2 - yo}" '
                f'stroke="{LINE_COLOR}" stroke-width="{LINE_WIDTH}" />'
            )
            line += arrow_head(x2 - xo, y2 - yo, angle)
        else:
            x, y = positions[source]
            line = (
                f'<path d="M {x} {y - IMAGE_RADIUS} '
                f'A {IMAGE_RADIUS} {IMAGE_RADIUS} 0 0 0 '
                f'{x - 2 * IMAGE_RADIUS} {y - IMAGE_RADIUS} '
                f'{IMAGE_RADIUS} {IMAGE_RADIUS} 0 0 0 {x - IMAGE_RADIUS} {y}" '
                f'stroke="{LINE_COLOR}" '
                f'stroke-width="{LINE_WIDTH}" fill="none" />'
            )
            line += arrow_head(x - IMAGE_RADIUS, y, 0)
        lines.append(line)
    images = []
    for frame in graph.nodes:
        x, y = positions[frame]
        imgurl = frame.image._to_data_url()
        image = (
            f'<image href="{imgurl}" image-rendering="optimizeSpeed" '
            f'x="{x - IMAGE_SIZE / 2}" y="{y - IMAGE_SIZE / 2}" '
            f'height="{IMAGE_SIZE}" width="{IMAGE_SIZE}" />'
        )
        images.append(image)
    linesstr = '\n'.join(lines)
    imagesstr = '\n'.join(images)
    view = f'{VIEWBOX_COORDS} {VIEWBOX_COORDS} {VIEWBOX_SIZE} {VIEWBOX_SIZE}'
    return f"""
    <svg viewBox="{view}" xmlns="http://www.w3.org/2000/svg">
    {linesstr}
    {imagesstr}
    </svg>
    """
