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

import argparse
import base64
import datetime
import hashlib
import io
import functools
import sqlite3
import typing

import PIL.Image
import PIL.ImageOps


PIXEL_ART_CSS = (
    'image-rendering: -moz-crisp-edges; '
    'image-rendering: crisp-edges; '
    'image-rendering: pixelated; '
)


class PikovError(Exception):
    pass


class NotFound(PikovError):
    pass


class Image:
    """An (immutable) image.

    Args:
        connection (sqlite3.Connection):
            A connection to the SQLite database this image belongs to.
        key (str): The image identifier.
    """
    def __init__(self, connection: sqlite3.Connection, key: str):
        self._connection = connection
        self._key = key
        self._content_type = None
        self._contents = None

    @property
    def key(self) -> str:
        return self._key

    @property
    def content_type(self) -> str:
        if self._content_type is not None:
            return self._content_type

        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'SELECT content_type FROM image WHERE key = ?;', (self._key,))
            row = cursor.fetchone()
            self._content_type = row[0]
            return self._content_type

    @property
    def contents(self) -> bytes:
        if self._contents is not None:
            return self._contents

        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'SELECT contents FROM image WHERE key = ?;', (self._key,))
            row = cursor.fetchone()
            self._contents = row[0]
            return self._contents

    def _as_html(self):
        return (
            '<table>'
            '<tr><th>Image</th><th></th></tr>'
            f'<tr><td>key</td><td>{self.key}</td></tr>'
            f'<tr><td>content_type</td><td>{self.content_type}</td></tr>'
            f'<tr><td>contents</td><td>{self._as_img()}</td></tr>'
            '</table>'
        )

    def _as_img(self):
        contents_base64 = base64.b64encode(self.contents).decode('utf-8')
        return (
            f'<img alt="image with key {self.key}" '
            f'src="data:{self.content_type};base64,{contents_base64}" '
            f'style="width: 5em; {PIXEL_ART_CSS}">'
        )

    def __repr__(self):
        return f"Image(key='{self._key}')"

    def _repr_mimebundle_(self, include=None, exclude=None, **kwargs):
        data = {}
        should_include = functools.partial(
            _should_include, include=include, exclude=exclude)

        if should_include(self.content_type) and self.contents:
            data[self.content_type] = self.contents

        if should_include('text/html'):
            data['text/html'] = self._as_html()

        return data


class Frame:
    """An animation frame.

    Args:
        connection (sqlite3.Connection):
            A connection to the SQLite database this frame belongs to.
        id (Tuple[int, int]):
            The primary key of this frame.
    """
    def __init__(
            self,
            connection: sqlite3.Connection,
            id: typing.Tuple[int, int]):
        self._connection = connection
        self._id = id

    @property
    def id(self) -> typing.Tuple[int, int]:
        return self._id

    @property
    def image(self) -> Image:
        """image (Image): Image content on the frame."""
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'SELECT image_key FROM frame '
                'WHERE clip_id = ? AND clip_order = ?;',
                self._id)
            row = cursor.fetchone()
            image_key = row[0]
            return Image(self._connection, image_key)

    @property
    def duration(self) -> datetime.timedelta:
        """duration (datetime.timedelta): Time duration to display the
        animation frame.
        """
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'SELECT duration_microseconds FROM frame '
                'WHERE clip_id = ? AND clip_order = ?;',
                self._id)
            row = cursor.fetchone()
            duration_microseconds = row[0]
            return datetime.timedelta(microseconds=duration_microseconds)

    def __add__(self, other):
        if hasattr(other, 'frames'):
            return MultiClip((self,) + other.frames)
        elif isinstance(other, Frame):
            return MultiClip((self, other))
        else:
            raise TypeError(f'Cannot add Frame and {str(type(other))}')

    def _as_html(self):
        image_key = None
        image_html = None
        if self.image is not None:
            image_key = self.image.key
            image_html = self.image._as_img()

        return (
            '<table>'
            f'<tr><th>Frame</th><th></th></tr>'
            f'<tr><td>id</td><td>{self._id}</td></tr>'
            '<tr><td>duration</td>'
            f'<td>{self.duration.total_seconds()} seconds</td></tr>'
            f'<tr><td>image.key</td><td>{image_key}</td></tr>'
            f'<tr><td>image.contents</td><td>{image_html}</td></tr>'
            '</table>'
        )

    def __repr__(self):
        return f"Frame(id='{self._id}')"

    def _repr_mimebundle_(self, include=None, exclude=None, **kwargs):
        data = {}
        should_include = functools.partial(
            _should_include, include=include, exclude=exclude)

        # Frame can be represented by just its image if the image content-type
        # is desired.
        if self.image and should_include(self.image.content_type) \
                and self.image.contents:
            data[self.image.content_type] = self.image.contents

        if should_include('text/html'):
            data['text/html'] = self._as_html()

        return data


class BaseClip:
    """An animation clip, which is a collection of frames."""

    @property
    def frames(self) -> typing.Tuple[Frame, ...]:
        """Collection[Frame]: A collection of frames in this clip."""
        raise NotImplementedError()

    def __add__(self, other):
        if hasattr(other, 'frames'):
            return MultiClip(self.frames + other.frames)
        elif isinstance(other, Frame):
            return MultiClip(self.frames + (other,))
        else:
            raise TypeError(f'Cannot add BaseClip and {str(type(other))}')

    def _as_gif(self):
        """Write a sequence of frames to a GIF (requires Pillow).

        Returns:
            Optional[bytes]:
                Contents of a GIF rendering of the clip or ``None`` if the clip
                contains no image frames.
        """
        if not self.frames:
            return None

        imgs = []
        for frame in self.frames:
            img_file = io.BytesIO(frame.image.contents)
            img = PIL.Image.open(img_file)
            img.duration = frame.duration.total_seconds() * 1000
            imgs.append(img)

        output = io.BytesIO()
        imgs[0].save(
            output, format='gif', save_all=True, append_images=imgs[1:],
            loop=0)
        return output.getvalue()

    def _as_img(self):
        gif_contents = self._as_gif()
        if not gif_contents:
            return None

        contents_base64 = base64.b64encode(gif_contents).decode('utf-8')
        return (
            f'<img alt="clip preview" '
            f'src="data:image/gif;base64,{contents_base64}" '
            f'style="width: 5em; {PIXEL_ART_CSS}">'
        )


class Clip(BaseClip):
    """An animation clip.

    Args:
        connection (sqlite3.Connection):
            A connection to the SQLite database this frame belongs to.
        id (int): The clip identifier.
    """
    def __init__(
            self,
            connection: sqlite3.Connection,
            id: int):
        self._connection = connection
        self._id = id

    @property
    def id(self) -> int:
        return self._id

    @property
    def frames(self) -> typing.Tuple[Frame, ...]:
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'SELECT clip_order '
                'FROM frame '
                'WHERE clip_id = ? '
                'ORDER BY clip_order ASC;',
                (self._id,))
            return tuple((
                Frame(self._connection, (self._id, row[0]))
                for row in cursor.fetchall()
            ))

    def append_frame(
            self,
            image_key: str,
            duration: typing.Optional[datetime.timedelta]=None):
        """Add a frame to the end of this clip.

        Args:
            image_key (str):
                An image to use as a frame in a clip.
            duration (datetime.timedelta, optional):
                Duration to display the frame within a clip. Defaults to
                100,000 microseconds (10 frames per second).

        Returns:
            Frame: The frame added.
        """
        if duration is None:
            duration = datetime.timedelta(microseconds=100000)
        duration_microseconds = int(duration.total_seconds() * 1000000)

        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute("BEGIN")

            # What should the next clip_order be?
            cursor.execute(
                'SELECT MAX(clip_order) '
                'FROM frame '
                'WHERE clip_id = ?;',
                (self._id,))
            row = cursor.fetchone()
            previous_clip_order = row[0]
            if previous_clip_order is None:
                previous_clip_order = -1
            clip_order = previous_clip_order + 1

            # Add the new Frame.
            cursor.execute(
                'INSERT INTO frame '
                '(clip_id, clip_order, image_key, duration_microseconds) '
                'VALUES (?, ?, ?, ?)',
                (self._id, clip_order, image_key, duration_microseconds))

        return Frame(self._connection, (self._id, clip_order))

    def _as_html(self):
        return (
            '<table>'
            f'<tr><th>Clip</th><th></th></tr>'
            f'<tr><td>id</td><td>{self._id}</td></tr>'
            f'<tr><td>frames</td><td>{self._as_img()}</td></tr>'
            '</table>'
        )

    def __repr__(self):
        return f"Clip(id='{self._id}')"

    def _repr_mimebundle_(self, include=None, exclude=None, **kwargs):
        data = {}
        should_include = functools.partial(
            _should_include, include=include, exclude=exclude)

        # Clip can be represented by just a GIF.
        if should_include('image/gif'):
            gif_contents = self._as_gif()
            if gif_contents:
                data['image/gif'] = gif_contents

        if should_include('text/html'):
            data['text/html'] = self._as_html()

        return data


class MultiClip(BaseClip):
    """A sequence of clips."""

    def __init__(self, frames):
        self._frames = tuple(frames)

    @property
    def frames(self):
        return self._frames

    def _as_html(self):
        return (
            '<table>'
            f'<tr><th>MultiClip</th><th></th></tr>'
            f'<tr><td>frames</td><td>{self._as_img()}</td></tr>'
            '</table>'
        )

    def __repr__(self):
        return f"MultiClip(frames={repr(self._frames)}')"

    def _repr_mimebundle_(self, include=None, exclude=None, **kwargs):
        data = {}
        should_include = functools.partial(
            _should_include, include=include, exclude=exclude)

        # Clip can be represented by just a GIF.
        if should_include('image/gif'):
            gif_contents = self._as_gif()
            if gif_contents:
                data['image/gif'] = gif_contents

        if should_include('text/html'):
            data['text/html'] = self._as_html()

        return data


class Pikov:
    def __init__(self, connection):
        self._connection = connection

    @classmethod
    def open(cls, path):
        connection = sqlite3.connect(path)
        # Allow for manual BEGIN/END transcactions.
        # https://stackoverflow.com/a/24374430/101923
        connection.isolation_level = None
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys = ON;')
        return cls(connection)

    @classmethod
    def create(cls, path):
        pikov = cls.open(path)
        cursor = pikov._connection.cursor()
        cursor.execute(
            'CREATE TABLE image ('
            'key TEXT PRIMARY KEY, '
            'contents BLOB, '
            'content_type STRING)')
        cursor.execute(
            'CREATE TABLE frame ('
            'clip_id INTEGER, '
            'clip_order INTEGER, '
            'image_key TEXT, '
            'duration_microseconds INTEGER, '
            'FOREIGN KEY(clip_id) REFERENCES clip(id), '
            'FOREIGN KEY(image_key) REFERENCES image(key), '
            'PRIMARY KEY (clip_id, clip_order));')
        cursor.execute(
            'CREATE TABLE clip ('
            'id INTEGER PRIMARY KEY)')
        pikov._connection.commit()
        return pikov

    def add_image(self, image):
        """Add an image to the Pikov file.

        Args:
            image (PIL.Image.Image):
                An image to add to the Pikov file.

        Returns:
            Tuple[str, bool]:
                The content-based address to the image and a boolean
                indicating True if the image was added or False for
                duplicates.
        """
        image_fp = io.BytesIO()
        image.save(image_fp, format='PNG')
        image_fp.seek(0)
        image_hash = hash_image(image)

        try:
            with self._connection:
                cursor = self._connection.cursor()
                cursor.execute(
                    'INSERT INTO image (key, contents, content_type) '
                    'VALUES (?, ?, ?)',
                    (image_hash, image_fp.read(), 'image/png'))
        except sqlite3.IntegrityError:
            return image_hash, False  # Frame already exists
        return image_hash, True

    def get_image(self, key):
        """Add an image to the Pikov file.

        Args:
            key (str): Content-based key for image file.

        Returns:
            Image: The image loaded from the Pikov file.

        Raises:
            NotFound: If image with ``key`` is not found.
        """
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute('SELECT key FROM image WHERE key = ?', (key,))
            image_row = cursor.fetchone()

            if not image_row:
                raise NotFound(
                    'Could not find image with key "{}"'.format(key))

        return Image(self._connection, key)

    def add_clip(self):
        """Add an animation clip to the Pikov file.

        Returns:
            Clip: The clip added.
        """
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute('INSERT INTO clip DEFAULT VALUES')
            return Clip(self._connection, cursor.lastrowid)

    def get_clip(self, clip_id):
        """Get the animation clip with a specific ID.

        Args:
            clip_id (int): Identifier of the animation clip to load.

        Returns:
            Clip: A clip containing all the clip's frames.

        Raises:
            NotFound: If clip with ``clip_id`` is not found.
        """
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'SELECT id FROM clip WHERE id = ?', (clip_id,))
            clip_row = cursor.fetchone()

            if not clip_row:
                raise NotFound(
                    'Could not find clip with clip_id "{}"'.format(clip_id))

        return Clip(self._connection, clip_id)


def _should_include(mime, include=None, exclude=None):
    if not mime:
        return False
    included = not include or mime in include
    not_excluded = not exclude or mime not in exclude
    return included and not_excluded


def hash_image(image):
    """Encode pixels as bytes and take the MD5 hash.

    Note: this is meant for de-duplication, not security purposes.
    """
    # Convert to common format for deterministic encoding.
    if image.getbands() != ('R', 'G', 'B', 'A'):
        image = image.convert(mode='RGBA')
    assert image.getbands() == ('R', 'G', 'B', 'A')

    md5 = hashlib.md5()

    for x in range(image.size[0]):
        for y in range(image.size[1]):
            # Format each pixel as a 4-byte string.
            # https://stackoverflow.com/a/31761722/101923
            md5.update(b"%c%c%c%c" % image.getpixel((x, y)))

    return 'md5-{}'.format(md5.hexdigest())


def import_clip(
        pikov_path, sprite_sheet_path, frame_width, frame_height, fps, frames,
        flip_x=False):
    duration = datetime.timedelta(seconds=1) / fps

    # Read the Pikov file.
    pikov = Pikov.open(pikov_path)

    # Chop the sprite sheet into frames.
    sheet = PIL.Image.open(sprite_sheet_path)
    sheet_width, _ = sheet.size
    cols = sheet_width // frame_width

    # Add images to Pikov.
    images = {}
    added = 0
    duplicates = 0
    frames_set = frozenset(frames)
    for spritesheet_frame in frames_set:
        row = spritesheet_frame // cols
        col = spritesheet_frame % cols
        frame = sheet.crop(box=(
            col * frame_width, row * frame_height,
            (col + 1) * frame_width, (row + 1) * frame_height,))

        if flip_x:
            frame = PIL.ImageOps.mirror(frame)
        image_key, image_added = pikov.add_image(frame)
        if image_added:
            added += 1
        else:
            duplicates += 1
        images[spritesheet_frame] = image_key

    # Create clip
    clip = pikov.add_clip()
    for spritesheet_frame in frames:
        image_key = images[spritesheet_frame]
        clip.append_frame(image_key, duration)

    print('Added {} of {} images ({} duplicates)'.format(
        added, len(frames_set), duplicates))
    print('Created clip {} with {} frames.'.format(clip.id, len(frames)))


def create(pikov_path):
    Pikov.create(pikov_path)


def main():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(title='Actions', dest='action')
    create_parser = subparsers.add_parser(
        'create', help='Create a new .pikov file.')
    create_parser.add_argument('pikov_path', help='Path to .pikov file.')

    import_clip_parser = subparsers.add_parser(
        'import-clip',
        help='Import a sprite sheet animation as a clip.')
    import_clip_parser.add_argument(
        '--fps', help='Frames per second.', type=int, default=12)
    import_clip_parser.add_argument(
        '--flip_x', help='Flip frames horizontally.', type=bool, default=False)
    import_clip_parser.add_argument('pikov_path', help='Path to .pikov file.')
    import_clip_parser.add_argument(
        'sprite_sheet_path', help='Path to sprite sheet.')
    import_clip_parser.add_argument(
        'frame_size', help='Size of frame. WIDTHxHEIGHT. Example: 8x8')
    import_clip_parser.add_argument(
        'frames',
        help=(
            'List of comma-separated frame IDs to include in clip. '
            'Frames are 0-indexed from left-to-right, top-to-bottom.'
        ))

    args = parser.parse_args()
    if args.action == 'create':
        create(args.pikov_path)
    elif args.action == 'import-clip':
        frame_width, frame_height = map(int, args.frame_size.split('x'))
        frames = list(map(int, args.frames.split(',')))
        import_clip(
            args.pikov_path, args.sprite_sheet_path, frame_width,
            frame_height, args.fps, frames, flip_x=args.flip_x)
    elif args.action is not None:
        raise NotImplementedError(
            'Got unknown action: {}'.format(args.action))


if __name__ == '__main__':
    main()
