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
import sqlite3

from PIL import Image


def add_frames(pikov_path, sprite_sheet_path):
    # Read the frame size from the Pikov file.
    conn = sqlite3.connect(pikov_path)
    cursor = conn.cursor()
    cursor.execute('SELECT frame_width, frame_height FROM pikov')
    frame_width, frame_height = cursor.fetchone()
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
            frame.show()
            return


def create(pikov_path, frame_width, frame_height):
    conn = sqlite3.connect(pikov_path)
    cursor = conn.cursor()
    cursor.execute(
        'CREATE TABLE frames (key TEXT PRIMARY KEY, contents BLOB)')
    cursor.execute(
        'CREATE TABLE pikov '
        '(id INTEGER PRIMARY KEY, frame_width INTEGER, frame_height INTEGER)')
    cursor.execute(
        'INSERT INTO pikov (frame_width, frame_height) VALUES (?, ?)',
        (frame_width, frame_height))
    conn.commit()


def main():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(title='Actions', dest='action')
    create_parser = subparsers.add_parser(
        'create', help='Create a new .pikov file.')
    create_parser.add_argument('pikov_path', help='Path to .pikov file.')
    create_parser.add_argument(
        'frame_size', help='Size of frame. WIDTHxHEIGHT. Example: 8x8')

    add_frames_parser = subparsers.add_parser(
        'add-frames',
        help='Add frames from a sprite sheet to an existing .pikov file.')
    add_frames_parser.add_argument('pikov_path', help='Path to .pikov file.')
    add_frames_parser.add_argument(
        'sprite_sheet_path', help='Path to sprite sheet.')

    args = parser.parse_args()
    if args.action == 'create':
        frame_width, frame_height = map(int, args.frame_size.split('x'))
        create(args.pikov_path, frame_width, frame_height)
    elif args.action == 'add-frames':
        add_frames(args.pikov_path, args.sprite_sheet_path)
    elif args.action is not None:
        raise NotImplementedError(
            'Got unknown action: {}'.format(args.action))


if __name__ == '__main__':
    main()
