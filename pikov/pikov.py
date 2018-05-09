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
import hashlib
import io
import sqlite3

from PIL import Image


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
            'id INTEGER PRIMARY KEY, '
            'clip_id INTEGER, '
            'image_key TEXT, '
            'clip_order INTEGER, '
            'duration_microseconds INTEGER, '
            'FOREIGN KEY(clip_id) REFERENCES clip(id),'
            'FOREIGN KEY(image_key) REFERENCES image(key))')
        cursor.execute(
            'CREATE TABLE clip ('
            'id INTEGER PRIMARY KEY)')
        pikov._connection.commit()

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

    def add_frame(self, clip_id, image_key, clip_order, duration_microseconds):
        """Add a frame to the Pikov file.

        Args:
            clip_id (int):
                Clip this frame is a part of.
            image_key (str):
                An image to use as a frame in a clip.
            clip_order (int):
                Integer describing the order that frames appear in a clip.
            duration_microseconds (int):
                Number of microseconds to display clip.

        Returns:
            int: ID of the frame added.
        """
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'INSERT INTO frame '
                '(clip_id, image_key, clip_order, duration_microseconds) '
                'VALUES (?, ?, ?, ?)',
                (clip_id, image_key, clip_order, duration_microseconds))
            return cursor.lastrowid

    def add_clip(self):
        """Add an animation clip to the Pikov file.

        Returns:
            int: ID of the clip added.
        """
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute('INSERT INTO clip DEFAULT VALUES')
            return cursor.lastrowid


def is_blank(image):
    """Determine if an image is blank.

    Args:
        frame (PIL.Image.Image):
            A frame image to add to the Pikov file.

    Returns:
        bool:
            True if the image contains only a single solid color.
    """
    solid_color = image.getpixel((0, 0))
    for x in range(image.size[0]):
        for y in range(image.size[1]):
            if solid_color != image.getpixel((x, y)):
                return False
    return True


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
    duration_microseconds = int(1000000 / fps)

    # Read the Pikov file.
    pikov = Pikov.open(pikov_path)

    # Chop the sprite sheet into frames.
    sheet = Image.open(sprite_sheet_path)
    sheet_width, sheet_height = sheet.size
    rows = sheet_height // frame_height
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
        pikov.add_frame(
            clip_id, image_key, clip_order, duration_microseconds)

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
