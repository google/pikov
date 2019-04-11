# Copyright 2019 Google LLC
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

"""Experimental module defining classes used in Pikov animations."""

from .core import GuidNode
from .properties import StringProperty
from . import guids


class SemanticGraphNode(GuidNode):
    """I want all nodes to have an (optional) name property, so define the
    node class after we've defined the property classes.
    """

    def __init__(self, ctor, graph, guid=None):
        super().__init__(graph, guid=guid)

        graph.set_value(
            self,
            GuidNode(graph, guid=guids.CTOR),
            GuidNode(graph, guid=_get_guid(ctor)))

    name = StringProperty(GuidNode(None, guid=guids.NAME))


def _get_guid(node_or_guid):
    if isinstance(node_or_guid, str):
        return node_or_guid
    return node_or_guid.guid
