// Copyright 2019 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

export class StringNode {
  constructor(value) {
    this.value = value
  }
}


export class Int64Node {
  constructor(value) {
    // TODO: convert to non-Number
    this.value = value
  }
}


export class GuidNode {
  constructor(graph, guid) {
    this._graph = graph
    this.guid = guid
  }

  get_labels() {
    return this._graph.get_labels(this.guid)
  }

  get_value(label) {
    var labelGuid = label.guid || label
    return this._graph.get_value(this.guid, labelGuid)
  }
}


export class JSONGraph {
  constructor(properties) {
    this._properties = properties
    if (!('guidMap' in this._properties)) {
      this._properties.guidMap = {}
    }
    this.root = properties.root
    if (this.root) {
      this.root = new GuidNode(this, this.root)
    }
  }

  _from_json(value) {
    if ("guid" in value) {
      return new GuidNode(this, value["guid"])
    }
    if ("string" in value) {
      return new StringNode(value["string"])
    }
    if ("int64" in value) {
      return new Int64Node(int(value["int64"]))
    }
  }

  get_value(sourceGuid, labelGuid) {
    var guidMap = this._properties.guidMap
    if (!(sourceGuid in guidMap)) {
      return null
    }

    var nodeJson = guidMap[sourceGuid]
    if (!(labelGuid in nodeJson)) {
      return null
    }

    return this._from_json(nodeJson[labelGuid])
  }

  get_labels(nodeGuid) {
    var guidMap = this._properties.guidMap
    if (!(nodeGuid in guidMap)) {
      return []
    }

    var labels = []
    var guids = Object.keys(guidMap[nodeGuid])
    for (const label of guids) {
      labels.push(new GuidNode(this, label))
    }
    return labels
  }
}
