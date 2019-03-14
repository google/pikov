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

import uuid


class ScalarNode:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        if not hasattr(other, "value"):
            return NotImplemented
        return self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)


class StringNode(ScalarNode):
    pass


class Int64Node(ScalarNode):
    pass


class GuidNode:
    def __init__(self, graph, guid=None):
        if guid is None:
            guid = uuid.uuid4().hex
        self.guid = guid
        self._graph = graph

    def __iter__(self):
        return self._graph.get_labels(self)

    def __getitem__(self, key):
        return self._graph.get_value(self, key)

    def __setitem__(self, key, value):
        self._graph.set_value(self, key, value)

    def __delitem__(self, key):
        self._graph.set_value(self, key, None)

    def __eq__(self, other):
        if not hasattr(other, "guid"):
            return NotImplemented
        return self.guid == other.guid

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return '{}(guid="{}")'.format(
            self.__class__.__name__,
            self.guid)

    def __hash__(self):
        return self.guid.__hash__()


class AbstractGraph:
    def get_value(self, source, label):
        raise NotImplementedError()

    def __iter__(self):
        """Generate a sequence of all GuidNodes in the graph."""
        raise NotImplementedError()

    def get_labels(self, node):
        raise NotImplementedError()

    def set_value(self, source, label, target):
        """Create/update/remove an edge.

        Set the ``target`` value to ``None`` to remove an edge.
        """
        raise NotImplementedError()

    # TODO: Require simple queries?
    # def query(self, filter_):
    #     """Find nodes matching a query.

    #     Note: In JSON implementation, this scans the whole table,
    #     as there are no indexes in the underlying storage layer.
    #     """
    #     for node in self:
    #         for label in node:
    #             if (type(filter_.label) is AnyLabel or filter_.label == label) and filter_.eq == node[label]:
    #                 yield node
