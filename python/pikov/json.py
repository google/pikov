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
import pathlib

from . import core


class JSONGraph(core.AbstractGraph):
    def __init__(self, filepath):
        self._properties = {'guidMap': {}}
        self.filepath = pathlib.Path(filepath)

    @property
    def _guid_map(self):
        return self._properties['guidMap']

    @classmethod
    def load(cls, filepath):
        graph = cls(filepath)
        with open(filepath) as fp:
            graph._properties = json.load(fp)
        return graph

    def save(self):
        with open(self.filepath, "w") as fp:
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
        source_guid = _get_guid(source)
        label_guid = _get_guid(label)

        if source_guid not in self._guid_map:
            return None

        node_json = self._guid_map[source_guid]
        if label_guid not in node_json:
            return None

        return self._from_json(node_json[label_guid])

    def __iter__(self):
        for guid in self._guid_map:
            yield core.GuidNode(self, guid=guid)

    def delete_node(self, node):
        node_guid = _get_guid(node)
        del self._guid_map[node_guid]

    def get_labels(self, node):
        node_guid = _get_guid(node)

        node_json = self._guid_map.get(node_guid, {})
        for guid in node_json:
            yield core.GuidNode(self, guid=guid)

    def _unset_value(self, source, label):
        source_guid = _get_guid(source)
        label_guid = _get_guid(label)

        if source_guid not in self._guid_map:
            return

        node_json = self._guid_map[source_guid]
        if label_guid not in node_json:
            return

        del node_json[label_guid]

    def set_value(self, source, label, target):
        """Create/update/remove an edge.

        Set the ``target`` value to ``None`` to remove an edge.
        """
        source_guid = _get_guid(source)
        label_guid = _get_guid(label)

        if target is None:
            self._unset_value(source, label)
            return

        if source_guid not in self._guid_map:
            self._guid_map[source_guid] = {}

        node_json = self._guid_map[source_guid]
        node_json[label_guid] = self._to_json(target)


def _get_guid(node_or_guid):
    if isinstance(node_or_guid, str):
        return node_or_guid
    return node_or_guid.guid
