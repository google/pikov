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


@pytest.fixture
def clip_id(pkv):
    clip = pkv.add_clip()
    return clip.id


@pytest.fixture
def clip_with_frames(pkv, image_key):
    clip = pkv.add_clip()
    clip.append_frame(image_key)
    two_tenths_second = datetime.timedelta(microseconds=200000)
    clip.append_frame(image_key, duration=two_tenths_second)
    return clip


@pytest.fixture
def frame(pkv, clip_id, image_key):
    clip = pkv.get_clip(clip_id)
    return clip.append_frame(image_key)


def test_get_clip_notfound(pkv):
    with pytest.raises(pikov.NotFound):
        pkv.get_clip(999)


def test_get_clip_no_frames(pkv, clip_id):
    clip = pkv.get_clip(clip_id)
    assert clip.id == clip_id
    assert len(clip.frames) == 0


def test_get_clip_with_frames(pkv, clip_id, image_key):
    clip = pkv.get_clip(clip_id)
    clip.append_frame(image_key)
    two_tenths_second = datetime.timedelta(microseconds=200000)
    clip.append_frame(image_key, duration=two_tenths_second)

    assert clip.id == clip_id
    assert len(clip.frames) == 2
    assert all([frame.id[0] == clip_id for frame in clip.frames])
    assert all([frame.image.key == image_key for frame in clip.frames])
    assert all([frame.image.contents is not None for frame in clip.frames])
    assert clip.frames[0].id[1] == 0
    assert clip.frames[1].id[1] == 1
    assert clip.frames[1].duration == two_tenths_second


def test_add_frames(pkv, frame):
    multi_clip = frame + frame
    assert len(multi_clip.frames) == 2


def test_add_clip_with_frame(pkv, clip_with_frames, frame):
    multi_clip = clip_with_frames + frame
    assert len(multi_clip.frames) == len(clip_with_frames.frames) + 1

    multi_clip = frame + clip_with_frames
    assert len(multi_clip.frames) == len(clip_with_frames.frames) + 1

    multi_clip_added = multi_clip + frame
    assert len(multi_clip_added.frames) == len(multi_clip.frames) + 1

    multi_clip_added = frame + multi_clip
    assert len(multi_clip_added.frames) == len(multi_clip.frames) + 1


def test_add_clips(pkv, clip_with_frames):
    multi_clip = clip_with_frames + clip_with_frames
    assert len(multi_clip.frames) == 2 * len(clip_with_frames.frames)

    multi_added = multi_clip + clip_with_frames
    expected_multi_added_len = (
        len(multi_clip.frames) + len(clip_with_frames.frames)
    )
    assert len(multi_added.frames) == expected_multi_added_len

    multi_added = clip_with_frames + multi_clip
    assert len(multi_added.frames) == expected_multi_added_len

    double_multi = multi_clip + multi_clip
    assert len(double_multi.frames) == 2 * len(multi_clip.frames)


def test_get_image_notfound(pkv):
    with pytest.raises(pikov.NotFound):
        pkv.get_image('md5-1234567890')


def test_get_image_found(pkv, pil_image):
    key, is_added = pkv.add_image(pil_image)
    img = pkv.get_image(key)
    assert img.key == key
    assert img.contents is not None
    assert len(img.contents) > 0
