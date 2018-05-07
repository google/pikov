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
            'image_key TEXT, '
            'duration_microseconds INTEGER, '
            'FOREIGN KEY(image_key) REFERENCES image(key))')
        cursor.execute(
            'CREATE TABLE clip ('
            'id INTEGER PRIMARY KEY, '
            'sequence TEXT)')
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

    def add_frame(self, image_key, duration_microseconds):
        """Add a frame to the Pikov file.

        Args:
            image_key (str):
                An image to use as a frame in a clip.
            duration_microseconds (int):
                Number of microseconds to display clip.

        Returns:
            int: ID of the frame added.
        """
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'INSERT INTO frame (image_key, duration_microseconds) '
                'VALUES (?, ?)', (image_key, duration_microseconds))
            return cursor.lastrowid

    def add_clip(self, clip):
        """Add an animation clip to the Pikov file.

        Args:
            clip (List[int]): A list of frame IDs.

        Returns:
            int: ID of the clip added.
        """
        with self._connection:
            cursor = self._connection.cursor()
            cursor.execute(
                'INSERT INTO clip (sequence) VALUES (?)',
                (','.join(map(str, clip)),))
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


def import_clip(pikov_path, sprite_sheet_path, frame_width, frame_height, fps):
    clip = []
    duplicates = 0
    blanks = 0
    duration_microseconds = int(1000000 / fps)

    # Read the Pikov file.
    pikov = Pikov.open(pikov_path)

    # Chop the sprite sheet into frames.
    sheet = Image.open(sprite_sheet_path)
    sheet_width, sheet_height = sheet.size
    rows = sheet_height // frame_height
    cols = sheet_width // frame_width
    for row in range(rows):
        for col in range(cols):
            frame = sheet.crop(box=(
                col * frame_width, row * frame_height,
                (col + 1) * frame_width, (row + 1) * frame_height,))

            if is_blank(frame):
                blanks += 1
                continue

            key, added = pikov.add_image(frame)
            frame_id = pikov.add_frame(key, duration_microseconds)
            if not added:
                duplicates += 1
            clip.append(frame_id)

    clip_id = pikov.add_clip(clip)

    print('Added {} of {} frames ({} duplicates, {} blank) to clip {}'.format(
        len(clip), rows * cols, duplicates, blanks, clip_id))


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

    args = parser.parse_args()
    if args.action == 'create':
        create(args.pikov_path)
    elif args.action == 'import-clip':
        frame_width, frame_height = map(int, args.frame_size.split('x'))
        import_clip(
            args.pikov_path, args.sprite_sheet_path, frame_width,
            frame_height, args.fps)
    elif args.action is not None:
        raise NotImplementedError(
            'Got unknown action: {}'.format(args.action))


if __name__ == '__main__':
    main()
