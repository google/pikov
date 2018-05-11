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

import datetime
import os.path

import pytest

from pikov import pikov


@pytest.fixture
def pkv():
    """Create an emptyp Pikov file."""
    return pikov.Pikov.create(':memory:')


@pytest.fixture
def pil_image():
    import PIL.Image

    spritesheet_path = os.path.join(
        os.path.dirname(__file__), '..', 'examples', 'gamekitty',
        'gamekitty.png')
    sheet = PIL.Image.open(spritesheet_path)

    # Grab just the first image of the spritesheet.
    return sheet.crop(box=(0, 0, 8, 8,))


@pytest.fixture
def image_key(pkv, pil_image):
    key, _ = pkv.add_image(pil_image)
    return key


def test_get_clip_notfound(pkv):
    with pytest.raises(pikov.NotFound):
        pkv.get_clip(999)


def test_get_clip_no_frames(pkv):
    clip_id = pkv.add_clip()
    clip = pkv.get_clip(clip_id)
    assert clip.id == clip_id
    assert len(clip.frames) == 0


def test_get_clip_with_frames(pkv, image_key):
    two_tenths_second = datetime.timedelta(microseconds=200000)
    clip_id = pkv.add_clip()
    pkv.add_frame(clip_id, 0, image_key)
    pkv.add_frame(
        clip_id, 1, image_key, duration=two_tenths_second)
    clip = pkv.get_clip(clip_id)
    assert clip.id == clip_id
    assert len(clip.frames) == 2
    assert all([frame.clip_id == clip_id for frame in clip.frames])
    assert all([frame.image.key == image_key for frame in clip.frames])
    assert all([frame.image.contents is not None for frame in clip.frames])
    assert clip.frames[0].clip_order == 0
    assert clip.frames[1].clip_order == 1
    assert clip.frames[1].duration == two_tenths_second


def test_get_image_notfound(pkv):
    with pytest.raises(pikov.NotFound):
        pkv.get_image('md5-1234567890')


def test_get_image_found(pkv, pil_image):
    key, is_added = pkv.add_image(pil_image)
    img = pkv.get_image(key)
    assert img.key == key
    assert img.contents is not None


def test_get_image_found_nocontents(pkv, pil_image):
    key, is_added = pkv.add_image(pil_image)
    img = pkv.get_image(key, include_contents=False)
    assert img.key == key
    assert img.contents is None
