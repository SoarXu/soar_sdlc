<template>
  <div class="rich-text-paste-editor">
    <div
      ref="editorRef"
      class="rich-text-paste-editor__surface"
      contenteditable="true"
      :data-placeholder="placeholder"
      @input="emitValue"
      @paste="handlePaste"
      @blur="emitValue"
    ></div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: 'Paste text or screenshots here' }
})
const emit = defineEmits(['update:modelValue'])
const editorRef = ref(null)
let syncing = false

watch(
  () => props.modelValue,
  (value) => syncEditorValue(value),
  { immediate: true }
)

onMounted(() => syncEditorValue(props.modelValue))

async function syncEditorValue(value) {
  await nextTick()
  const editor = editorRef.value
  if (!editor || syncing || editor.innerHTML === (value || '')) return
  editor.innerHTML = value || ''
}

function emitValue() {
  const editor = editorRef.value
  if (!editor) return
  syncing = true
  emit('update:modelValue', sanitizeHtml(editor.innerHTML))
  nextTick(() => { syncing = false })
}

async function handlePaste(event) {
  const items = Array.from(event.clipboardData?.items || [])
  const imageItems = items.filter((item) => item.type.startsWith('image/'))
  if (!imageItems.length) return

  event.preventDefault()
  for (const item of imageItems) {
    const file = item.getAsFile()
    if (!file) continue
    const dataUrl = await readFileAsDataUrl(file)
    insertHtmlAtCursor(`<img src="${dataUrl}" alt="pasted image" />`)
  }
  emitValue()
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

function insertHtmlAtCursor(html) {
  const selection = window.getSelection()
  if (!selection || !selection.rangeCount) {
    editorRef.value?.insertAdjacentHTML('beforeend', html)
    return
  }
  const range = selection.getRangeAt(0)
  range.deleteContents()
  const fragment = range.createContextualFragment(html)
  const lastNode = fragment.lastChild
  range.insertNode(fragment)
  if (lastNode) {
    range.setStartAfter(lastNode)
    range.collapse(true)
    selection.removeAllRanges()
    selection.addRange(range)
  }
}

function sanitizeHtml(value) {
  const template = document.createElement('template')
  template.innerHTML = value || ''
  template.content.querySelectorAll('script, style, iframe, object, embed').forEach((node) => node.remove())
  template.content.querySelectorAll('*').forEach((node) => {
    Array.from(node.attributes).forEach((attr) => {
      const name = attr.name.toLowerCase()
      const value = attr.value || ''
      if (name.startsWith('on')) node.removeAttribute(attr.name)
      if ((name === 'href' || name === 'src') && /^javascript:/i.test(value)) node.removeAttribute(attr.name)
    })
  })
  return template.innerHTML
}
</script>
