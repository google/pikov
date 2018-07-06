#!/usr/bin/env zsh

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

# Animation clips, as defined in the PICO-8 version of gamekitty.
# https://github.com/tswast/pixelsketches/blob/master/pico-8/gamekitty.p8
typeset -A buffer
clips=(
    sit 0
    sit_to_stand 1,2,3,4
    # stand_to_walk 34,35
    # strut 36,37,38,39,41,42,43,44
    stand_waggle 26,4
    stand_to_sit 57,58,59,60,61
    # turn_from_sit 10,11,12,13,14,15,16
    # turn_from_stand 18,19,20,21,22,23,24,25
    # stand_to_jump 46,47,48,49
    # jump 50,51,45,45,52,48,49
    # jump_to_stand 53,54,55
    # walk 84,85,87,88,89,90,91,92,93,95,96,97
    sit_paw 62,63,64,65,66
    sit_to_crouch 69,70,71
    crouch 72
    lie_down 73
    crouch_to_sit 75,76,77
)
rm examples/gamekitty/gamekitty.pikov ; pikov create examples/gamekitty/gamekitty.pikov

for clip_id frames in ${(kv)clips}; do
    pikov import-clip \
        examples/gamekitty/gamekitty.pikov ${clip_id} \
        examples/gamekitty/gamekitty.png 8x8 ${frames}
done

# Mirror images
# for clip_id frames in ${(kv)clips}; do
#     pikov import-clip --flip_x=True \
#         examples/gamekitty/gamekitty.pikov ${clip_id}_mirror \
#         examples/gamekitty/gamekitty.png 8x8 ${frames}
# done
