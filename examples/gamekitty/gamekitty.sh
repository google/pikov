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
clips=(
    0
    1,2,3,4
    34,35
    36,37,38,39,41,42,43,44
    41,42,43,44
    26,4
    57,58,59,60,61
    10,11,12,13,14,15,16
    18,19,20,21,22,23,24,25
    46,47,48,49
    50,51,45,45,52,48,49
    52,48,49
    53,54,55
    84,85,87,88,89,90,91,92,93,95,96,97
    62,63,64,65,66
    40
    69,70,71,72,73,74,75,76,77
)
rm examples/gamekitty/gamekitty.pikov ; pikov create examples/gamekitty/gamekitty.pikov

for clip in $clips; do
    pikov import-clip \
        examples/gamekitty/gamekitty.pikov \
        examples/gamekitty/gamekitty.png 8x8 $clip
done

# Mirror images
for clip in $clips; do
    pikov import-clip --flip_x=True \
        examples/gamekitty/gamekitty.pikov \
        examples/gamekitty/gamekitty.png 8x8 $clip
done
