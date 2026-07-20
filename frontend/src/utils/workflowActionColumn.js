function textWidth(value) {
  return [...String(value || '')].reduce((total, character) => (
    total + (character.codePointAt(0) > 255 ? 14 : 8)
  ), 0)
}

function rowWidth(actions, extraWidth) {
  const primary = (actions || []).filter((item) => item.list_display === 'primary')
  const more = (actions || []).some((item) => item.list_display !== 'primary')
  const buttonsWidth = primary.reduce((total, item) => total + Math.max(48, textWidth(item.action_name) + 24), 0)
  const gaps = Math.max(0, primary.length - 1) * 4 + (primary.length && more ? 8 : 0)
  return extraWidth + buttonsWidth + gaps + (more ? 52 : 0)
}

export function workflowActionColumnWidth(actionRows = [], options = {}) {
  const minWidth = Number(options.minWidth) || 180
  const extraWidth = Number(options.extraWidth) || 0
  return Math.ceil(Math.max(minWidth, ...actionRows.map((actions) => rowWidth(actions, extraWidth))))
}
