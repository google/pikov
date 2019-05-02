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

"""Property classes for building wrapper classes for Pikov nodes.

We want to wrap our semantic graph with Python classes. This allows us to
interact with Python objects to modify the guid_map.

These classes encode the core types used in the semantic graph. When classes
use these properties, the guid_map is updated with the correct serialization
of the property.
"""

from .core import Int64Node, StringNode


class AbstractSemanticGraphProperty(object):
    def __init__(self, label):
        self._label = label

    def from_node(self, obj, value):
        raise NotImplementedError()

    def to_node(self, value):
        raise NotImplementedError()

    def __get__(self, obj, type=None):
        return self.from_node(obj, obj[self._label])

    def __set__(self, obj, value):
        obj[self._label] = self.to_node(value)


class UnspecifiedProperty(AbstractSemanticGraphProperty):
    def from_node(self, obj, value):
        obj._graph.get_value(obj, self._label)

    def to_node(self, value):
        # Value should already by a Node.
        return value


class GuidProperty(AbstractSemanticGraphProperty):
    def __init__(self, label, cls):
        super().__init__(label)
        self._cls = cls

    def from_node(self, obj, value):
        if value is None:
            return None
        return self._cls(obj._graph, guid=value.guid)

    def to_node(self, value):
        # Value should already by a GuidNode.
        return value


def make_guid_property(wrapped):
    def __init__(self, label):
        GuidProperty.__init__(self, label, wrapped)

    return type(
        wrapped.__name__ + "Property",
        (GuidProperty,),
        {
            "__init__": __init__,
        }
    )


class ScalarProperty(AbstractSemanticGraphProperty):
    def from_node(self, obj, value):
        if value is None:
            return None
        return value.value


class Int64Property(ScalarProperty):
    def to_node(self, value):
        if value is None:
            return None
        return Int64Node(value)


class StringProperty(ScalarProperty):
    def to_node(self, value):
        if value is None:
            return None
        return StringNode(value)
