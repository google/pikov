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
import functools
import hashlib
import io
import json
import os.path
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
    def clip(self) -> 'Clip':
        return Clip(self._connection, self._id[0])

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

    @property
    def next(self) -> typing.Optional['Frame']:
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'SELECT clip_id, MIN(clip_order) '
                'FROM frame '
                'WHERE clip_id = ? '
                'AND clip_order > ?;',
                self._id)
            next_id = cursor.fetchone()
            if next_id is None or next_id[1] is None:
                return None
            return Frame(self._connection, next_id)

    @property
    def transitions(self) -> typing.Tuple['Transition', ...]:
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'SELECT id '
                'FROM transition '
                'WHERE source_clip_id = ? '
                'AND source_clip_order = ?'
                'ORDER BY target_clip_id ASC, target_clip_order ASC;',
                self._id)
            return tuple((
                Transition(self._connection, row[0])
                for row in cursor.fetchall()
            ))

    def _get_properties(self, cursor) -> typing.Mapping[str, typing.Any]:
        cursor.execute(
            'SELECT properties '
            'FROM frame '
            'WHERE clip_id = ? '
            'AND clip_order = ?',
            self._id)
        row = cursor.fetchone()
        if not row[0]:
            return {}
        return json.loads(row[0])

    def get_property(self, key: str) -> typing.Any:
        with self._connection:
            cursor = self._connection.cursor()
            properties = self._get_properties(cursor)
            return properties.get(key)

    def set_property(self, key: str, value: typing.Any):
        with self._connection:
            cursor = self._connection.cursor()
            try:
                cursor.execute('BEGIN')
                properties = self._get_properties(cursor)
                properties[key] = value
                properties_json = json.dumps(properties)
                cursor.execute(
                    'UPDATE frame '
                    'SET properties = ? '
                    'WHERE clip_id = ? '
                    'AND clip_order = ?',
                    (properties_json,) + self._id)
                cursor.execute('COMMIT')
            except Exception:
                cursor.execute('ROLLBACK')
                raise

    def transition_to(self, target: 'Frame') -> 'Transition':
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'INSERT INTO transition '
                '(source_clip_id, source_clip_order,'
                ' target_clip_id, target_clip_order) '
                'VALUES (?, ?, ?, ?);',
                self.id + target.id)
            return Transition(self._connection, cursor.lastrowid)

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

        with self._connection:
            properties = self._get_properties(self._connection.cursor())

        return (
            '<table>'
            f'<tr><th>Frame</th><th></th></tr>'
            f'<tr><td>id</td><td>{self._id}</td></tr>'
            '<tr><td>duration</td>'
            f'<td>{self.duration.total_seconds()} seconds</td></tr>'
            f'<tr><td>image.key</td><td>{image_key}</td></tr>'
            f'<tr><td>image.contents</td><td>{image_html}</td></tr>'
            '<tr><td>properties</td><td style="text-align: left;">'
            f'<pre>{json.dumps(properties, indent=2)}</pre></td></tr>'
            '</table>'
        )

    def __eq__(self, other):
        return isinstance(other, Frame) and self.id == other.id

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

    def _as_gif(self) -> typing.Optional[bytes]:
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

    @property
    def transitions(self) -> typing.Tuple['Transition', ...]:
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'SELECT id '
                'FROM transition '
                'WHERE source_clip_id = ? '
                'ORDER BY source_clip_order,'
                ' target_clip_id ASC, target_clip_order ASC;',
                (self._id,))
            return tuple((
                Transition(self._connection, row[0])
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

    def transition_to(self, target: 'Clip') -> 'Transition':
        """Add a transition from this clip to the beginning of a target clip.

        Arguments:
            target (Clip): Destination clip for a transition.

        Returns:
            Transition:
                A transition from the last frame of this clip to the first
                frame of the ``target`` clip.
        """
        return self.frames[-1].transition_to(target.frames[0])

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
        frames_repr = '<br>'.join((repr(frame) for frame in self._frames))
        return (
            '<table>'
            f'<tr><th>MultiClip</th><th></th></tr>'
            f'<tr><td>frames</td><td>{frames_repr}</td></tr>'
            f'<tr><td>preview</td><td>{self._as_img()}</td></tr>'
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


class Transition:
    def __init__(self, connection: sqlite3.Connection, id: int):
        self._connection = connection
        self._id = id
        self._deleted = False
        # Source and Target are immutable for a Transition,
        # so we can cache the objects for them.
        self._source = None
        self._target = None

    @property
    def id(self) -> int:
        return self._id

    @property
    def source(self) -> Frame:
        if self._deleted:
            raise ValueError('Cannot fetch source on deleted transition.')

        if self._source is not None:
            return self._source

        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'SELECT source_clip_id, source_clip_order '
                'FROM transition WHERE id = ?;',
                (self._id,))
            row = cursor.fetchone()
            self._source = Frame(self._connection, row)
            return self._source

    @property
    def target(self) -> Frame:
        if self._deleted:
            raise ValueError('Cannot fetch target on deleted transition.')

        if self._target is not None:
            return self._target

        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'SELECT target_clip_id, target_clip_order '
                'FROM transition WHERE id = ?;',
                (self._id,))
            row = cursor.fetchone()
            self._target = Frame(self._connection, row)
            return self._target

    def delete(self):
        if self._deleted:
            raise ValueError('Cannot delete. Transition already deleted.')

        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'DELETE FROM transition WHERE id = ?;',
                (self._id,))
            self._deleted = True

    def _as_clip(self) -> MultiClip:
        current_frame = self.source.clip.frames[0]

        # Add all frames up to the current frame from the source clip.
        frames = []
        while current_frame != self.source:
            frames.append(current_frame)
            current_frame = current_frame.next

        frames.append(self.source)
        current_frame = self.target

        # Add all frames until the end of the target clip.
        while current_frame is not None:
            frames.append(current_frame)
            current_frame = current_frame.next

        return MultiClip(frames)

    def _as_gif(self) -> typing.Optional[bytes]:
        return self._as_clip()._as_gif()

    def _as_img(self) -> str:
        return self._as_clip()._as_img()

    def _as_html(self) -> str:
        source_img = self.source.image._as_img()
        target_img = self.target.image._as_img()
        return (
            '<table>'
            '<tr><th>Transition</th><th></th></tr>'
            f'<tr><td>id</td><td>{self.id}</td></tr>'
            f'<tr><td>source.id</td><td>{self.source.id}</td></tr>'
            f'<tr><td>source.image</td><td>{source_img}</td></tr>'
            f'<tr><td>target.id</td><td>{self.target.id}</td></tr>'
            f'<tr><td>target.image</td><td>{target_img}</td></tr>'
            f'<tr><td>preview</td><td>{self._as_img()}</td></tr>'
            '</table>'
        )

    def __repr__(self) -> str:
        return (
            'Transition('
            f'id={repr(self.id)}, '
            f'source={repr(self.source)}, '
            f'target{repr(self.target)})'
        )

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
            'CREATE TABLE clip ('
            'id STRING PRIMARY KEY)')
        cursor.execute(
            'CREATE TABLE frame ('
            'clip_id STRING, '
            'clip_order INTEGER, '
            'image_key TEXT, '
            'duration_microseconds INTEGER, '
            'properties TEXT, '
            'FOREIGN KEY(clip_id) REFERENCES clip(id), '
            'FOREIGN KEY(image_key) REFERENCES image(key), '
            'PRIMARY KEY (clip_id, clip_order));')
        cursor.execute(
            'CREATE TABLE transition ('
            'id INTEGER PRIMARY KEY, '
            'source_clip_id STRING, '
            'source_clip_order INTEGER, '
            'target_clip_id STRING, '
            'target_clip_order INTEGER, '
            'FOREIGN KEY(source_clip_id, source_clip_order) '
            '  REFERENCES frame(clip_id, clip_order), '
            'FOREIGN KEY(target_clip_id, target_clip_order) '
            '  REFERENCES frame(clip_id, clip_order));')
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

    def add_clip(self, clip_id):
        """Add an animation clip to the Pikov file.

        Returns:
            Clip: The clip added.
        """
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute('INSERT INTO clip (id) VALUES (?)', (clip_id,))
            return Clip(self._connection, clip_id)

    def get_clip(self, clip_id):
        """Get the animation clip with a specific ID.

        Args:
            clip_id (str): Identifier of the animation clip to load.

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

    def find_absorbing_frames(self) -> typing.Tuple[Frame, ...]:
        """Return all frames which are 'absorbing'.

        An absorbing frame is one with no connections outgoing connections to
        any other frame except itself. Once an animation reaches such a
        frame, it will be stuck there until reset.
        """
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                # Select the final frame in each clip.
                'SELECT f1.clip_id, f1.clip_order '
                'FROM frame AS f1 '
                'LEFT OUTER JOIN frame AS f2'
                ' ON f1.clip_id = f2.clip_id'
                ' AND f1.clip_order < f2.clip_order '
                # Join with transitions to find frames with no
                # transitions out.
                'LEFT OUTER JOIN transition'
                ' ON f1.clip_id = transition.source_clip_id'
                ' AND f1.clip_order = transition.source_clip_order'
                ' AND (f1.clip_id != transition.target_clip_id'
                ' OR f1.clip_order != transition.target_clip_order) '
                'WHERE f2.clip_order IS NULL'  # No next frame.
                # No transitions out.
                ' AND transition.source_clip_order IS NULL '
                'ORDER BY f1.clip_id, f1.clip_order ASC;')
            frame_ids = cursor.fetchall()
            return tuple((
                Frame(self._connection, frame_id)
                for frame_id in frame_ids
            ))


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
        pikov_path, clip_id, spritesheet_path, frame_width, frame_height,
        fps, frames, flip_x=False):
    # Normalize the paths for file relative path comparison.
    pikov_path = os.path.abspath(pikov_path)
    pikov_dir = os.path.dirname(pikov_path)
    spritesheet_path = os.path.abspath(spritesheet_path)
    relative_spritesheet_path = os.path.relpath(
        spritesheet_path, start=pikov_dir)

    # Convert FPS input into a per-frame duration.
    duration = datetime.timedelta(seconds=1) / fps

    # Read the Pikov file.
    pikov = Pikov.open(pikov_path)

    # Chop the sprite sheet into frames.
    sheet = PIL.Image.open(spritesheet_path)
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
        x = col * frame_width
        y = row * frame_height
        frame = sheet.crop(box=(x, y, x + frame_width, y + frame_height,))

        if flip_x:
            frame = PIL.ImageOps.mirror(frame)
        image_key, image_added = pikov.add_image(frame)
        if image_added:
            added += 1
        else:
            duplicates += 1
        images[spritesheet_frame] = (
            image_key,
            {
                'path': relative_spritesheet_path,
                'x': x,
                'y': y,
                'width': frame_width,
                'height': frame_height,
                'flipX': flip_x,
            })

    # Create clip
    clip = pikov.add_clip(clip_id)
    for spritesheet_frame in frames:
        image_key, original_image = images[spritesheet_frame]
        frame = clip.append_frame(image_key, duration)
        frame.set_property('originalImage', original_image)

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
        'clip_id', help='Unique identifier for the new clip.')
    import_clip_parser.add_argument(
        'spritesheet_path', help='Path to sprite sheet.')
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
            args.pikov_path, args.clip_id, args.spritesheet_path,
            frame_width, frame_height, args.fps, frames, flip_x=args.flip_x)
    elif args.action is not None:
        raise NotImplementedError(
            'Got unknown action: {}'.format(args.action))


if __name__ == '__main__':
    main()
