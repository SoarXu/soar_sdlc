<template>
  <div class="commit-diff-viewer">
    <template v-if="fileDiffs.length">
      <section v-for="file in fileDiffs" :key="file.key" class="diff-file">
        <header class="diff-file-head">
          <strong>{{ file.newPath || file.oldPath || 'unknown file' }}</strong>
          <span v-if="file.oldPath && file.newPath && file.oldPath !== file.newPath">{{ file.oldPath }} -> {{ file.newPath }}</span>
        </header>
        <div class="diff-table">
          <div class="diff-table-head diff-old">变更前</div>
          <div class="diff-table-head diff-new">变更后</div>
          <template v-for="(row, index) in file.rows" :key="`${file.key}-${index}`">
            <pre class="diff-cell" :class="row.oldClass">{{ row.oldText }}</pre>
            <pre class="diff-cell" :class="row.newClass">{{ row.newText }}</pre>
          </template>
        </div>
      </section>
    </template>
    <pre v-else class="diff-viewer">{{ fallbackText || '暂无 diff 内容' }}</pre>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  diffText: { type: String, default: '' },
  diffJson: { type: [Array, Object, String], default: null }
})

const fallbackText = computed(() => props.diffText || formatDiffJson(props.diffJson))
const fileDiffs = computed(() => parseUnifiedDiff(fallbackText.value))

function formatDiffJson(value) {
  return value ? JSON.stringify(value, null, 2) : ''
}

function parseUnifiedDiff(value) {
  const lines = (value || '').split(/\r?\n/)
  const files = []
  let current = null

  for (const line of lines) {
    if (line.startsWith('diff --git ')) {
      current = { key: line, oldPath: '', newPath: '', rows: [] }
      files.push(current)
      const match = line.match(/^diff --git a\/(.+?) b\/(.+)$/)
      if (match) {
        current.oldPath = match[1]
        current.newPath = match[2]
      }
      continue
    }
    if (!current) continue
    if (line.startsWith('--- ')) {
      current.oldPath = normalizePath(line.slice(4))
      continue
    }
    if (line.startsWith('+++ ')) {
      current.newPath = normalizePath(line.slice(4))
      continue
    }
    if (line.startsWith('@@')) {
      current.rows.push({
        oldText: line,
        newText: line,
        oldClass: 'diff-hunk',
        newClass: 'diff-hunk'
      })
      continue
    }
    if (line.startsWith('-')) {
      current.rows.push({
        oldText: line.slice(1),
        newText: '',
        oldClass: 'diff-removed',
        newClass: 'diff-empty'
      })
      continue
    }
    if (line.startsWith('+')) {
      current.rows.push({
        oldText: '',
        newText: line.slice(1),
        oldClass: 'diff-empty',
        newClass: 'diff-added'
      })
      continue
    }
    if (line) {
      const text = line.startsWith(' ') ? line.slice(1) : line
      current.rows.push({
        oldText: text,
        newText: text,
        oldClass: 'diff-context',
        newClass: 'diff-context'
      })
    }
  }

  return files.filter((file) => file.rows.length)
}

function normalizePath(value) {
  return value.replace(/^a\//, '').replace(/^b\//, '').replace('/dev/null', '')
}
</script>
