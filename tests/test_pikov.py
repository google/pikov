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
import uuid

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
    clip = pkv.add_clip(str(uuid.uuid4()))
    for index, image in enumerate(pil_images):
        key, _ = pkv.add_image(image)
        clip.append_frame(
            key,
            duration=datetime.timedelta(microseconds=(index * 10000) + 10000))
    return clip


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
def clip_id(pkv):
    clip_id = str(uuid.uuid4())
    clip = pkv.add_clip(clip_id)
    return clip.id


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
def frame(pkv, clip_id, image_key):
    clip = pkv.get_clip(clip_id)
    return clip.append_frame(image_key)


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
    # Check clip_order
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


def test_frame_next_found(pkv, clip_with_frames):
    frames = clip_with_frames.frames
    assert len(frames) > 1
    frame = frames[0]
    assert frame.next is not None
    assert frame.next.id[0] == frame.id[0]
    assert frame.next.id[1] == frame.id[1] + 1


def test_frame_next_not_found(pkv, clip_with_frames):
    frames = clip_with_frames.frames
    assert len(frames) > 0
    last_frame = frames[-1]
    assert last_frame.next is None


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


def test_clip_transitions(pkv, clip_with_frames, clip_2):
    source1 = clip_with_frames.frames[0]
    source2 = clip_with_frames.frames[-1]
    target1 = clip_2.frames[0]
    target2 = clip_2.frames[1]
    source2.transition_to(target2)
    source2.transition_to(target1)
    source1.transition_to(target2)
    source1.transition_to(target1)

    transitions = clip_with_frames.transitions

    assert len(transitions) == 4
    # Transitions should be sorted by source clip_order,
    # then by target clip_order.
    assert transitions[0].source == source1
    assert transitions[0].target == target1
    assert transitions[1].source == source1
    assert transitions[1].target == target2
    assert transitions[2].source == source2
    assert transitions[2].target == target1
    assert transitions[3].source == source2
    assert transitions[3].target == target2


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
