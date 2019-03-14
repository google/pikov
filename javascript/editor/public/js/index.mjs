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

import { JSONGraph } from '/js/pikov.mjs';
import { el, list, mount } from 'https://redom.js.org/redom.es.js';


const NAME_GUID = "169a81aefca74e92b45e3fa03c7021df"


function friendlyName(node) {
    var textContent = node.guid
    var name = node.get_value(NAME_GUID)
    if (!!name) {
      textContent = name.value + ' (' + node.guid.substring(0, 7) + ')'
    }
    return textContent
}

class LabelCodeComponent {
  constructor() {
    this.el = el('li')
    this.subcontext
  }

  update(data) {
    this.el.textContent = friendlyName(data.label)
    // TODO: add + button to expand if label points to a GuidNode.
  }
}


class GuidNodeCodeComponent {
  constructor() {
    // TODO: add a link to find all references to a node.
    this.guidDom = el('span')
    this.labelsDom = el('ul')
    this.el = el('li', [this.guidDom, this.labelsDom])
    this.subcontext = list(this.labelsDom, LabelCodeComponent)
  }

  update(data) {
    this.guidDom.textContent = friendlyName(data.node)
    this.subcontext.update(data.subcontext)
    // TODO: add + button to expand if label points to a GuidNode.
  }
}

var editor = {
  context: []
}

var editorDom = list('ul', GuidNodeCodeComponent)
mount(document.body, editorDom)


function expandNode(node) {
  var nodeLabels = node.get_labels()
  var subcontext = []
  for (const label of nodeLabels) {
    subcontext.push({
      view: "label",
      subcontext: [],
      node: node,
      label: label,
    })
  }
  return subcontext
}

function rerender() {
  editorDom.update(editor.context)
}

function handleFileSelect(evt) {
  var file = evt.target.files[0];

  var reader = new FileReader()
  reader.onload = function(evt) {
    var graphJson = JSON.parse(reader.result)
    editor.graph = new JSONGraph(graphJson)
    if (editor.graph.root) {
      editor.context = [{
        view: "code",
        subcontext: expandNode(editor.graph.root),
        node: editor.graph.root
      }]
    } else {
      editor.context = []
    }
    rerender()
  }

  reader.readAsText(file)
}

document.getElementById('graph-file').addEventListener('change', handleFileSelect, false);

