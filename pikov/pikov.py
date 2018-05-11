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
import datetime
import hashlib
import io
import sqlite3

import PIL.Image


class PikovError(Exception):
    pass


class NotFound(PikovError):
    pass


class Image(object):
    """An image.

    Args:
        key (str): The image identifier.
        contents (bytes, optional): Image contents (assumed to be PNG).
    """
    def __init__(self, key, contents=None):
        self.key = key
        self.contents = contents


class Frame(object):
    """An animation frame.

    Args:
        clip_id (int): The identifier of the clip the frame belongs to.
        clip_order (int): Where this frame appears within the clip.
        image (Image): Image content on the frame.
        duration (datetime.timedelta):
            Time duration to display the animation frame.
    """
    def __init__(self, clip_id, clip_order, image, duration):
        self.clip_id = clip_id
        self.clip_order = clip_order
        self.image = image
        self.duration = duration


class Clip(object):
    """An animation clip.

    Args:
        id (int): The clip identifier.
        frames (List[Frame]): Frames which the clip contains.
    """
    def __init__(self, id, frames):
        self.id = id
        self.frames = frames


class Pikov(object):
    def __init__(self, connection):
        self._connection = connection

    @classmethod
    def open(cls, path):
        connection = sqlite3.connect(path)
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys = ON;')
        return cls(connection)

    @classmethod
    def create(cls, path):
        pikov = cls.open(path)
        cursor = pikov._connection.cursor()
        cursor.execute(
            'CREATE TABLE image (key TEXT PRIMARY KEY, contents BLOB)')
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
        image_io = io.BytesIO()
        image.save(image_io, format='PNG')
        image_hash = hash_image(image)

        try:
            with self._connection:
                cursor = self._connection.cursor()
                cursor.execute(
                    'INSERT INTO image (key, contents) '
                    'VALUES (?, ?)', (image_hash, image_io.read()))
        except sqlite3.IntegrityError:
            return image_hash, False  # Frame already exists
        return image_hash, True

    def get_image(self, key, include_contents=True):
        """Add an image to the Pikov file.

        Args:
            key (str): Content-based key for image file.
            include_contents (bool, optional):
                Include content bytes in the fetched image.

        Returns:
            Image: The image loaded from the Pikov file.

        Raises:
            NotFound: If image with ``key`` is not found.
        """
        if include_contents:
            sql = 'SELECT key, contents FROM image WHERE key = ?'
        else:
            sql = 'SELECT key FROM image WHERE key = ?'

        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(sql, (key,))
            image_row = cursor.fetchone()

            if not image_row:
                raise NotFound(
                    'Could not find image with key "{}"'.format(key))

        return Image(*image_row)

    def add_frame(self, clip_id, clip_order, image_key, duration=None):
        """Add a frame to the Pikov file.

        Args:
            clip_id (int): Clip this frame is a part of.
            clip_order (int):
                Integer describing the order that frames appear in a clip.
            image_key (str):
                An image to use as a frame in a clip.
            duration (datetime.timedelta, optional):
                Duration to display the frame within a clip. Defaults to
                100,000 microseconds (10 frames per second).

        Returns:
            Frame: The frame added (does not include image contents).
        """
        if duration is None:
            duration = datetime.timedelta(microseconds=100000)
        duration_microseconds = int(duration.total_seconds() * 1000000)

        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'INSERT INTO frame '
                '(clip_id, clip_order, image_key, duration_microseconds) '
                'VALUES (?, ?, ?, ?)',
                (clip_id, clip_order, image_key, duration_microseconds))

        return Frame(clip_id, clip_order, Image(image_key), duration)

    def list_frames(self, clip_id):
        """Return frames associated with ``clip_id`` in order.

        Args:
            clip_id (int): Clip the frames are a part of.

        Returns:
            List[Frame]: A list of frames associated with the clip, in order.
        """
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'SELECT clip_order, image_key, duration_microseconds '
                'FROM frame '
                'WHERE clip_id = ? '
                'ORDER BY clip_order ASC;',
                (clip_id,))
            frame_rows = cursor.fetchall()

        frames = []
        for row in frame_rows:
            clip_order, image_key, duration_microseconds = row
            duration = datetime.timedelta(microseconds=duration_microseconds)
            image = self.get_image(image_key)
            frames.append(Frame(clip_id, clip_order, image, duration))
        return frames

    def add_clip(self):
        """Add an animation clip to the Pikov file.

        Returns:
            int: ID of the clip added.
        """
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute('INSERT INTO clip DEFAULT VALUES')
            return cursor.lastrowid

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

        return Clip(clip_id, self.list_frames(clip_id))


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
        pikov_path, sprite_sheet_path, frame_width, frame_height, fps, frames):
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

        image_key, image_added = pikov.add_image(frame)
        if image_added:
            added += 1
        else:
            duplicates += 1
        images[spritesheet_frame] = image_key

    # Create clip
    clip_id = pikov.add_clip()
    for clip_order, spritesheet_frame in enumerate(frames):
        image_key = images[spritesheet_frame]
        pikov.add_frame(clip_id, clip_order, image_key, duration)

    print('Added {} of {} images ({} duplicates)'.format(
        added, len(frames_set), duplicates))
    print('Created clip {} with {} frames.'.format(clip_id, len(frames)))


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
            frame_height, args.fps, frames)
    elif args.action is not None:
        raise NotImplementedError(
            'Got unknown action: {}'.format(args.action))


if __name__ == '__main__':
    main()
