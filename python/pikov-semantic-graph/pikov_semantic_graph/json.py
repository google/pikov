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

import json

from . import core


class JSONGraph(core.AbstractGraph):
    def __init__(self):
        self._properties = {'guidMap': {}}

    @property
    def _guid_map(self):
        return self._properties['guidMap']

    @classmethod
    def load(cls, fp):
        graph = cls()
        graph._properties = json.load(fp)
        return graph

    def save(self, fp):
        json.dump(self._properties, fp, indent=2, sort_keys=True)

    def _to_json(self, target):
        if isinstance(target, core.GuidNode):
            return {"guid": target.guid}
        if isinstance(target, core.StringNode):
            return {"string": target.value}
        if isinstance(target, core.Int64Node):
            return {"int64": str(target.value)}

    def _from_json(self, value):
        if "guid" in value:
            return core.GuidNode(self, guid=value["guid"])
        if "string" in value:
            return core.StringNode(value["string"])
        if "int64" in value:
            return core.Int64Node(int(value["int64"]))

    def get_value(self, source, label):
        if source.guid not in self._guid_map:
            return None

        node_json = self._guid_map[source.guid]
        if label.guid not in node_json:
            return None

        return self._from_json(node_json[label.guid])

    def __iter__(self):
        for guid in self._guid_map:
            yield core.GuidNode(self, guid=guid)

    def get_labels(self, node):
        node_json = self._guid_map.get(node.guid, {})
        for guid in node_json:
            yield core.GuidNode(self, guid=guid)

    def _unset_value(self, source, label):
        if source.guid not in self._guid_map:
            return

        node_json = self._guid_map[source.guid]
        if label.guid not in node_json:
            return

        del node_json[label.guid]

    def set_value(self, source, label, target):
        """Create/update/remove an edge.

        Set the ``target`` value to ``None`` to remove an edge.
        """
        if target is None:
            self._unset_value(source, label)
            return

        if source.guid not in self._guid_map:
            self._guid_map[source.guid] = {}

        node_json = self._guid_map[source.guid]
        node_json[label.guid] = self._to_json(target)