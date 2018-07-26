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
import io

import pytest

from pikov import pikov


def load_image(x=0, y=0):
    import PIL.Image

    spritesheet_path = os.path.join(
        os.path.dirname(__file__), '..', 'examples', 'gamekitty',
        'gamekitty.png')
    sheet = PIL.Image.open(spritesheet_path)

    # Grab an 8x8 image of the spritesheet.
    return sheet.crop(box=(x, y, x + 8, y + 8,))


def create_clip(pkv, pil_images):
    previous_frame = None
    frames = []

    for index, image in enumerate(pil_images):
        key, _ = pkv.add_image(image)
        current_frame = pkv.add_frame(
            key,
            duration=datetime.timedelta(microseconds=(index * 10000) + 10000))

        if previous_frame is not None:
            previous_frame.transition_to(current_frame)

        frames.append(current_frame)
        previous_frame = current_frame

    return pikov.Clip(frames)


@pytest.fixture
def pkv():
    """Create an emptyp Pikov file."""
    return pikov.Pikov.create(':memory:')


@pytest.fixture
def pil_image():
    return load_image(0, 0)


@pytest.fixture
def image_key(pkv, pil_image):
    key, _ = pkv.add_image(pil_image)
    return key


@pytest.fixture
def clip_with_frames(pkv):
    return create_clip(
        pkv,
        (
            load_image(0, 0),
            load_image(8, 0),
            load_image(16, 0),
            load_image(24, 0),
            load_image(32, 0),
        ))


@pytest.fixture
def clip_2(pkv):
    return create_clip(
        pkv,
        (
            load_image(40, 0),
            load_image(48, 0),
            load_image(56, 0),
            load_image(64, 0),
            load_image(72, 0),
        ))


@pytest.fixture
def frame(pkv, image_key):
    return pkv.add_frame(image_key)


@pytest.fixture
def transition(clip_with_frames, clip_2):
    source_frame = clip_with_frames.frames[-1]
    target_frame = clip_2.frames[0]
    return source_frame.transition_to(target_frame)


def test_find_absorbing_frames(pkv, clip_with_frames, clip_2):
    # Two independent clips.
    frame1 = clip_with_frames.frames[-1]
    frame2 = clip_2.frames[-1]
    found = pkv.find_absorbing_frames()
    expected = tuple(sorted((frame1, frame2), key=lambda frame: frame.id))
    assert found == expected

    # Connecting one to the other drops an absorbing frame.
    frame1.transition_to(frame2)
    found = pkv.find_absorbing_frames()
    assert found == (frame2,)


def test_find_absorbing_frames_empty(pkv):
    assert pkv.find_absorbing_frames() == ()


def test_add_frame_with_duration(pkv, image_key):
    two_tenths_second = datetime.timedelta(microseconds=200000)
    frame = pkv.add_frame(image_key, duration=two_tenths_second)
    assert frame.id is not None
    assert frame.duration == two_tenths_second


def test_add_frame_sets_start_frame(pkv, image_key):
    assert pkv.start_frame is None
    first = pkv.add_frame(image_key)
    assert pkv.start_frame == first
    second = pkv.add_frame(image_key)
    assert pkv.start_frame == first
    assert pkv.start_frame != second


def test_set_start_frame_sets_frame(pkv, image_key):
    assert pkv.start_frame is None
    first = pkv.add_frame(image_key)
    second = pkv.add_frame(image_key)
    assert pkv.start_frame == first
    assert pkv.start_frame != second
    pkv.start_frame = second
    assert pkv.start_frame == second


def test_set_start_frame_none_unsets_frame(pkv, image_key):
    assert pkv.start_frame is None
    first = pkv.add_frame(image_key)
    assert first is not None
    assert pkv.start_frame == first
    pkv.start_frame = None
    assert pkv.start_frame is None


def test_get_frame_notfound(pkv):
    with pytest.raises(pikov.NotFound):
        pkv.get_frame(999)


def test_get_frame(pkv, frame):
    got = pkv.get_frame(frame.id)
    assert got.id == frame.id
    assert got.image.key is not None
    assert got.image.contents is not None


# Clip
def test_add_frames(pkv, frame):
    clip = frame + frame
    assert len(clip.frames) == 2


def test_add_clip_with_frame(pkv, clip_with_frames, frame):
    clip = clip_with_frames + frame
    assert len(clip.frames) == len(clip_with_frames.frames) + 1

    clip = frame + clip_with_frames
    assert len(clip.frames) == len(clip_with_frames.frames) + 1

    clip_added = clip + frame
    assert len(clip_added.frames) == len(clip.frames) + 1

    clip_added = frame + clip
    assert len(clip_added.frames) == len(clip.frames) + 1


def test_add_clips(pkv, clip_with_frames):
    clip = clip_with_frames + clip_with_frames
    assert len(clip.frames) == 2 * len(clip_with_frames.frames)

    multi_added = clip + clip_with_frames
    expected_multi_added_len = (
        len(clip.frames) + len(clip_with_frames.frames)
    )
    assert len(multi_added.frames) == expected_multi_added_len

    multi_added = clip_with_frames + clip
    assert len(multi_added.frames) == expected_multi_added_len

    double_multi = clip + clip
    assert len(double_multi.frames) == 2 * len(clip.frames)


# Pikov
def test_get_image_notfound(pkv):
    with pytest.raises(pikov.NotFound):
        pkv.get_image('md5-1234567890')


def test_get_image_found(pkv, pil_image):
    key, is_added = pkv.add_image(pil_image)
    img = pkv.get_image(key)
    assert img.key == key
    assert img.contents is not None
    assert len(img.contents) > 0


def test_frame_transitions_empty(pkv, clip_with_frames):
    last_frame = clip_with_frames.frames[-1]
    assert last_frame is not None
    assert last_frame.transitions == ()


def test_frame_transition_to(pkv, clip_with_frames, clip_2):
    source_frame = clip_with_frames.frames[-1]
    assert source_frame is not None
    target_frame = clip_2.frames[0]
    assert target_frame is not None

    transition = source_frame.transition_to(target_frame)

    assert transition.source == source_frame
    assert transition.target == target_frame


def test_frame_transitions(pkv, clip_with_frames, clip_2):
    source_frame = clip_with_frames.frames[-1]
    target1 = clip_2.frames[0]
    target2 = clip_2.frames[1]
    source_frame.transition_to(target2)
    source_frame.transition_to(target1)

    transitions = source_frame.transitions

    assert len(transitions) == 2
    assert all(
        (transition.source == source_frame for transition in transitions))
    # Transitions should be sorted by target clip_order.
    assert transitions[0].target == target1
    assert transitions[1].target == target2


def test_clip_transitions_to(pkv, clip_with_frames, clip_2):
    transition = clip_with_frames.transition_to(clip_2)

    source_frame = clip_with_frames.frames[-1]
    assert transition.source == source_frame
    target_frame = clip_2.frames[0]
    assert transition.target == target_frame


def test_transition_delete_does_delete(transition):
    transition_id = transition.id
    source = transition.source
    before_len = len(source.transitions)
    assert before_len > 0

    transition.delete()

    assert transition.id == transition_id
    assert len(source.transitions) == before_len - 1


def test_transition_operations_raise_on_deleted(transition):
    transition.delete()

    with pytest.raises(ValueError):
        transition.target

    with pytest.raises(ValueError):
        transition.source

    with pytest.raises(ValueError):
        transition.delete()


def test_pikov_save_gif_missing_start_frame(pkv):
    fp = io.BytesIO()
    with pytest.raises(ValueError):
        pkv.save_gif(fp)


def test__preview_clip_respects_duration(pkv, clip_with_frames):
    # Transition clip to self so that loops are possible.
    clip_with_frames.transition_to(clip_with_frames)
    min_duration = datetime.timedelta(seconds=2)
    max_duration = datetime.timedelta(seconds=3)
    preview = pkv._preview_clip(
        start_frame=clip_with_frames.frames[0],
        min_duration=min_duration,
        max_duration=max_duration)

    # Any frames at all?
    assert len(preview.frames) > 0

    total_duration = datetime.timedelta(seconds=0)
    for frame in preview.frames:
        total_duration = total_duration + frame.duration

    assert min_duration <= total_duration
    assert total_duration <= max_duration
