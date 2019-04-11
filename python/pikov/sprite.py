# Copyright 2019 Google LLC
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

"""Pikov sprite editor classes

These classes are the core resources used in defining a "Pikov" file.

Note: ideally these classes could be derived from the graph itself, but I
don't (yet) encode type or field information in the `pikov.json` semantic
graph.
"""

import base64
import functools
import io
import typing

from PIL import Image, ImageChops

from .core import GuidNode
from .properties import StringProperty, Int64Property, make_guid_property
from .pikov import SemanticGraphNode


PIXEL_ART_CSS = (
    'image-rendering: -moz-crisp-edges; '
    'image-rendering: crisp-edges; '
    'image-rendering: pixelated; '
)

MICROS_12_FPS = int(1e6 / 12)  # 12 frames per second
MICROS_24_FPS = int(1e6 / 24)

names = {
    'Clip': 'e8cec171b1f5462297f2e81ab606b687',
    'Clip.frames': '7c03dc958d8642b4be3417e69e36695c',
    'EmptyList': '51fb7a7a95d4486bb197509fd53dec2d',
    'NonemptyList': 'f0408beb29c74dc7bc20dc461104e949',
    'NonemptyList.head': 'a74851b7a58f4e52b72ee719b258a7b1',
    'NonemptyList.tail': 'e53f14ab72eb40f590e5ae53fb53e988',
    'bitmap': 'bc7e9e34c3464292ba39c2b1b9dc8902',
    'bitmap.crop': '995607dcd31e477994333565511c1de2',
    'bitmap.resource': '0de9d2d0679945ca9e6957f049cc982c',
    'ctor': 'aba6ac79fd3d409da860a77c90942852',
    'frame': '8b057dd7a9c84b7180cb2d8d6015b833',
    'frame.bitmap': 'c6b725e0c8bb419ca9408eec5febbde8',
    'frame.duration_microseconds': 'a2be632d888143e89ddfd4b1b8c8492d',
    'gamekitty': 'b463421ad4374bda8e088b9602fd8794',
    'name': '169a81aefca74e92b45e3fa03c7021df',
    'origin': '01188e000bae49ec8c08891e16d25091',
    'point': 'bfa8113cb5e5436ebd76ab5418b7efd1',
    'point.x': '825142afc2934fbcb5126e149ac5ba31',
    'point.y': '66b25e276cfb4d83a7032baaa4369b6f',
    'rectangle': 'c5f33d38b1104896ba54d09dba3d0acf',
    'rectangle.anchor': '667901a1e1c54035b7e586a05fffed2e',
    'rectangle.height': '68b5d34bb7954ad6850cd55cbae05ccf',
    'rectangle.width': '1f22dbb5504344fb93f57f0f0eb0ba6f',
    'resource': '6ecf1345ea0b4865b92569971b100b09',
    'resource.relative_path': '4e09f9df1fdf4eb4964ff9ed1b375dbb',
    'sprite': '158aafa594b44474a7da66a8cfa419f0',
    'sprite.frame': '4b079607f347492c8250059b5c0b2ef6',
    'sprite.position': '2175a23088d347cb9256b7f6c6eae310',
    'spritesheet': '710af736fb3945e28b07e0ac3a8e53d6',
    'transition': '8fe06c0750344322bd773f56bdd73b0a',
    'transition.offset': '9c8708a5228d42918017d5da96cf0327',
    'transition.source': '8ea9b7bc02e748ae9dc2e169590e71e3',
    'transition.target': 'ff7abe687a764f9d80d67a70424c329a',
    'vector': 'db5b02f92e5f489ea34cb66a5b5c9e75',
    'vector.x': '9b3dcb8dd2984ed6b126cd0287a4523a',
    'vector.y': 'aa3ed66ad6564addb41415ae681ffd05',
}


class Resource(SemanticGraphNode):
    def __init__(self, graph, guid=None):
        super().__init__(names["resource"], graph, guid=guid)
        self._image = None

    relative_path = StringProperty(names["resource.relative_path"])

    @property
    def image(self):
        if self._image is None:
            self._image = Image.open(
                self._graph.filepath.parent / self.relative_path
            )
        return self._image


ResourceProperty = make_guid_property(Resource)


class Point(SemanticGraphNode):
    def __init__(self, guid_map, guid=None):
        super().__init__(names["point"], guid_map, guid=guid)

    x = Int64Property(names["point.x"])
    y = Int64Property(names["point.y"])

    def __repr__(self):
        return "Point(guid='{}', x={}, y={})".format(
            self.guid,
            repr(self.x),
            repr(self.y),
        )


PointProperty = make_guid_property(Point)


class Vector(SemanticGraphNode):
    def __init__(self, guid_map, guid=None):
        super().__init__(names["vector"], guid_map, guid=guid)

    x = Int64Property(names["vector.x"])
    y = Int64Property(names["vector.y"])


VectorProperty = make_guid_property(Vector)


class Rectangle(SemanticGraphNode):
    def __init__(self, guid_map, guid=None):
        super().__init__(names["rectangle"], guid_map, guid=guid)

    anchor = PointProperty(names["rectangle.anchor"])
    width = Int64Property(names["rectangle.width"])
    height = Int64Property(names["rectangle.height"])

    def __repr__(self):
        return "Rectangle(guid='{}', anchor={}, width={}, height={})".format(
            self.guid,
            repr(self.anchor),
            repr(self.width),
            repr(self.height),
        )


RectangleProperty = make_guid_property(Rectangle)


class Bitmap(SemanticGraphNode):
    def __init__(self, guid_map, guid=None):
        super().__init__(names["bitmap"], guid_map, guid=guid)
        self._image = None

    resource = ResourceProperty(names["bitmap.resource"])
    crop = RectangleProperty(names["bitmap.crop"])

    @property
    def image(self):
        if self._image is None:
            left = self.crop.anchor.x
            top = self.crop.anchor.y
            right = left + self.crop.width
            bottom = top + self.crop.height
            box = (left, top, right, bottom)
            self._image = self.resource.image.crop(
                box
            )
        return self._image

    def _to_data_url(self):
        image = self.image
        if not image:
            return None

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        contents_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{contents_base64}"


BitmapProperty = make_guid_property(Bitmap)


class Frame(SemanticGraphNode):
    def __init__(self, guid_map, guid=None):
        super().__init__(names["frame"], guid_map, guid=guid)

    duration_microseconds = Int64Property(names["frame.duration_microseconds"])
    bitmap = BitmapProperty(names["frame.bitmap"])

    def _to_img(self):
        image_url = self.bitmap._to_data_url()
        if not image_url:
            return None

        return (
            f'<img alt="clip preview" '
            f'src="{image_url}" '
            f'style="width: 5em; {PIXEL_ART_CSS}">'
        )


FrameProperty = make_guid_property(Frame)


class FrameList(GuidNode):
    def __init__(self, graph, guid=None):
        super().__init__(graph, guid=guid)

        graph.set_value(
            self,
            names["ctor"],
            GuidNode(graph, guid=names["EmptyList"]))

        # Cache list so we can index by integer.
        # self._nodes = [self]

    head = FrameProperty(names["NonemptyList.head"])

    @property
    def tail(self):
        node = self._graph.get_value(self, names["NonemptyList.tail"])
        if node is None:
            return None
        return FrameList(self._graph, node.guid)

    def _set_tail(self, value):
        self._graph.set_value(
            self,
            names["NonemptyList.tail"],
            value)

    def append(self, value, guid=None):
        end_node = list(self._nodes())[-1]

        self._graph.set_value(
            end_node,
            names["ctor"],
            GuidNode(self._graph, guid=names["NonemptyList"]))
        end_node.head = value

        # New end node.
        new_end_node = FrameList(self._graph, guid=guid)
        end_node._set_tail(new_end_node)
        return new_end_node

    def __bool__(self):
        return self.tail is not None

    __nonzero__ = __bool__

    def __getitem__(self, key):
        if isinstance(key, int):
            frames = [frame for frame in self]
            return frames[key]
        return super().__getitem__(key)

    def _nodes(self):
        current_node = self
        while current_node:
            yield current_node
        yield current_node

    def __iter__(self):
        current_node = self
        while current_node:
            yield current_node.head
            current_node = current_node.tail


FrameListProperty = make_guid_property(FrameList)


class Transition(SemanticGraphNode):
    def __init__(self, guid_map, guid=None):
        super().__init__(names["transition"], guid_map, guid=guid)

    source = FrameProperty(names["transition.source"])
    target = FrameProperty(names["transition.target"])

    def _to_html(self) -> str:
        source_img = self.source._to_img()
        target_img = self.target._to_img()
        return (
            '<table>'
            '<tr><th>Transition</th><th></th></tr>'
            f'<tr><td>guid</td><td>{self.guid}</td></tr>'
            f'<tr><td>name</td><td>{self.name}</td></tr>'
            f'<tr><td>source.guid</td><td>{self.source.guid}</td></tr>'
            f'<tr><td>source.image</td><td>{source_img}</td></tr>'
            f'<tr><td>target.guid</td><td>{self.target.guid}</td></tr>'
            f'<tr><td>target.image</td><td>{target_img}</td></tr>'
            '</table>'
        )

    def __repr__(self) -> str:
        return (
            'Transition('
            f'id={repr(self.guid)}, '
            f'source={repr(self.source)}, '
            f'target{repr(self.target)})'
        )

    def _repr_mimebundle_(self, include=None, exclude=None, **kwargs):
        data = {}
        should_include = functools.partial(
            _should_include, include=include, exclude=exclude)

        if should_include('text/html'):
            data['text/html'] = self._to_html()

        return data


TransitionProperty = make_guid_property(Transition)


class Sprite(SemanticGraphNode):
    def __init__(self, guid_map, guid=None):
        super().__init__(names["sprite"], guid_map, guid=guid)

    frame = FrameProperty(names["sprite.frame"])
    position = PointProperty(names["sprite.position"])


SpriteProperty = make_guid_property(Sprite)


def _should_include(mime, include=None, exclude=None):
    if not mime:
        return False
    included = not include or mime in include
    not_excluded = not exclude or mime not in exclude
    return included and not_excluded


class Clip(SemanticGraphNode):
    def __init__(self, guid_map, guid=None):
        super().__init__(names["Clip"], guid_map, guid=guid)

    frames = FrameListProperty(names["Clip.frames"])

    def save_gif(self, fp):
        """Save this clip as a GIF to file pointer ``fp``."""
        if not self.frames:
            raise ValueError('No frames to write to GIF.')

        imgs = []
        durations = []
        previous_image = None
        for frame in self.frames:
            duration_microseconds = (
                frame.duration_microseconds or MICROS_12_FPS
            )
            duration = duration_microseconds / 1000  # Micros to millis

            # Increase the duration if the image is the same as the previous.
            # The GIF renderer crashes if it gets two duplicate frames.
            current_image = frame.bitmap.image
            if previous_image and equal_images(previous_image, current_image):
                durations[-1] = durations[-1] + duration
                # print("got duplicate image")
                continue
            # if previous_image == frame.image.key:
            #     durations[-1] = durations[-1] + duration
            #     continue
            # previous_image = frame.image.key

            # New image, add it to the list.
            previous_image = current_image
            imgs.append(current_image)
            durations.append(duration)

        # print("got {} imgs".format(len(imgs)))
        imgs[0].save(
            fp, format='gif', save_all=(len(imgs) > 1), append_images=imgs[1:],
            duration=durations if len(durations) > 1 else durations[0],
            # Always loop since this the GIF is used to preview the clip.
            loop=0)

    def _to_gif(self) -> typing.Optional[bytes]:
        """Write a sequence of frames to a GIF (requires Pillow).

        Returns:
            Optional[bytes]:
                Contents of a GIF rendering of the clip or ``None`` if the clip
                contains no image frames.
        """
        if not self.frames:
            return None

        output = io.BytesIO()
        self.save_gif(output)
        return output.getvalue()

    def _to_img(self):
        gif_contents = self._to_gif()
        if not gif_contents:
            return None

        contents_base64 = base64.b64encode(gif_contents).decode('utf-8')
        return (
            f'<img alt="clip preview" '
            f'src="data:image/gif;base64,{contents_base64}" '
            f'style="width: 5em; {PIXEL_ART_CSS}">'
        )

    def _to_html(self):
        # frames_repr = ', '.join((repr(frame) for frame in self.frames))
        return (
            '<table>'
            f'<tr><th>Clip</th><th></th></tr>'
            # f'<tr><td>frames</td><td>{frames_repr}</td></tr>'
            f'<tr><td>preview</td><td>{self._to_img()}</td></tr>'
            '</table>'
        )

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.frames[key]
        return super().__getitem__(key)

    # def __repr__(self):
    #     return f"Clip(frames={repr(self.frames)}')"

    def _repr_mimebundle_(self, include=None, exclude=None, **kwargs):
        data = {}
        should_include = functools.partial(
            _should_include, include=include, exclude=exclude)

        # Clip can be represented by just a GIF.
        if should_include('image/gif'):
            gif_contents = self._to_gif()
            if gif_contents:
                data['image/gif'] = gif_contents

        if should_include('text/html'):
            data['text/html'] = self._to_html()

        return data


# https://stackoverflow.com/a/6204954/101923
def equal_images(im1, im2):
    return ImageChops.difference(im1, im2).getbbox() is None

