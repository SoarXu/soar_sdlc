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
import {
  clipboardHtmlFromDataTransfer,
  getClipboardImageFiles,
  imageDataUrlToHtml,
  sanitizeHtml
} from '../utils/clipboardHtml'

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
  const imageFiles = getClipboardImageFiles(event.clipboardData)
  const html = clipboardHtmlFromDataTransfer(event.clipboardData)
  if (!imageFiles.length && !html) return

  event.preventDefault()
  if (html) {
    insertHtmlAtCursor(html)
  }
  for (const file of imageFiles) {
    const dataUrl = await readFileAsDataUrl(file)
    insertHtmlAtCursor(imageDataUrlToHtml(dataUrl))
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
  const editor = editorRef.value
  const selection = window.getSelection()
  if (!editor || !selection || !selection.rangeCount || !editor.contains(selection.anchorNode)) {
    editor?.insertAdjacentHTML('beforeend', html)
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
</script>
