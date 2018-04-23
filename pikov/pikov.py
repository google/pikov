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


def add_frame():
    raise NotImplementedError('add-frame command not implemented yet')


def create(pixov_path):
    conn = sqlite3.connect(pixov_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE frames (key TEXT PRIMARY KEY, contents BLOB)')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pikov_path', help='Path to .pikov file.')

    subparsers = parser.add_subparsers(title='Actions', dest='action')
    subparsers.add_parser(
        'create', help='Create a new .pikov file.')
    subparsers.add_parser(
        'add-frame', help='Add a frame to an existing .pikov file.')

    args = parser.parse_args()
    if args.action == 'create':
        create(args.pikov_path)
    elif args.action == 'add-frame':
        add_frame()
    elif args.action is not None:
        raise NotImplementedError('Got unknown action: {}')


if __name__ == '__main__':
    main()
