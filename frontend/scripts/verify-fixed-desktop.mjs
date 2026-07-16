import { spawn } from 'node:child_process'
import { writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const debugPort = 9223
const viewport = {
  width: Number(process.env.SOAR_VIEWPORT_WIDTH || 1440),
  height: Number(process.env.SOAR_VIEWPORT_HEIGHT || 900),
  deviceScaleFactor: 1,
  mobile: false
}
const approvedDesktopSizes = new Set(['1366x768', '1440x900', '1920x1080'])
const viewportKey = `${viewport.width}x${viewport.height}`
if (!approvedDesktopSizes.has(viewportKey)) {
  throw new Error(`Unsupported desktop viewport: ${viewportKey}`)
}

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

async function waitForDebugger() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${debugPort}/json/version`)
      if (response.ok) return
    } catch {}
    await delay(250)
  }
  throw new Error('Edge debugging endpoint did not start')
}

async function connect(target) {
  const socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true })
    socket.addEventListener('error', reject, { once: true })
  })
  let id = 0
  const pending = new Map()
  const listeners = new Map()
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (!message.id) {
      for (const listener of listeners.get(message.method) || []) listener(message.params)
      return
    }
    if (!pending.has(message.id)) return
    const { resolve, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(message.error.message))
    else resolve(message.result)
  })
  return {
    send(method, params = {}) {
      id += 1
      socket.send(JSON.stringify({ id, method, params }))
      return new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
    },
    on(method, listener) {
      const methodListeners = listeners.get(method) || new Set()
      methodListeners.add(listener)
      listeners.set(method, methodListeners)
      return () => methodListeners.delete(listener)
    },
    close() {
      socket.close()
    }
  }
}

async function loginToken() {
  if (process.env.SOAR_ACCESS_TOKEN) return process.env.SOAR_ACCESS_TOKEN
  const response = await fetch('http://127.0.0.1:8000/api/v1/auth/login', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'admin123' })
  })
  if (!response.ok) throw new Error(`Login failed: ${response.status}`)
  return (await response.json()).access_token
}

async function evaluateValue(client, expression) {
  const evaluated = await client.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (evaluated.exceptionDetails) {
    throw new Error(evaluated.exceptionDetails.exception?.description || evaluated.exceptionDetails.text)
  }
  return evaluated.result.value
}

async function verifyWorkflowDrawer(client) {
  await client.send('Page.navigate', { url: 'http://127.0.0.1:5173/workflow' })
  await delay(1800)
  const openedDetail = await evaluateValue(client, `(() => {
    const button = document.querySelector('.table-link-button')
    if (!button) return false
    button.click()
    return true
  })()`)
  if (!openedDetail) throw new Error('Workflow drawer verification could not find a workflow scheme')

  await delay(1800)
  const selectedTransition = await evaluateValue(client, `(async () => {
    const edges = [...document.querySelectorAll('.workflow-edge')]
    for (const edge of edges) {
      edge.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await new Promise((resolve) => setTimeout(resolve, 50))
      const button = document.querySelector('.workflow-advanced-entry .el-button')
      if (button && !button.disabled) return true
    }
    return false
  })()`)
  if (!selectedTransition) throw new Error('Workflow drawer verification could not find a transition')

  await delay(300)
  const canvasBefore = await evaluateValue(client, `(() => ({
    transform: document.querySelector('.workflow-svg > g')?.getAttribute('transform') || '',
    nodes: [...document.querySelectorAll('.workflow-node')].map((node) => node.getAttribute('transform'))
  }))()`)
  const openState = await evaluateValue(client, `(async () => {
    const button = document.querySelector('.workflow-advanced-entry .el-button:not([disabled])')
    if (!button) return { found: false }
    button.click()
    await new Promise((resolve) => setTimeout(resolve, 100))
    const overlay = document.querySelector('.workflow-advanced-drawer-modal')
    return {
      found: true,
      overlayDisplay: overlay ? getComputedStyle(overlay).display : 'missing'
    }
  })()`)
  if (!openState.found || openState.overlayDisplay === 'none') {
    throw new Error(`Workflow drawer verification could not open advanced configuration: ${JSON.stringify(openState)}`)
  }

  await delay(500)
  const result = await evaluateValue(client, `(() => {
    const candidates = [...document.querySelectorAll('.workflow-advanced-drawer, .el-drawer, .el-overlay')]
    const drawer = candidates.find((item) => item.matches('.el-drawer') && item.getBoundingClientRect().width >= 500)
    if (!drawer) {
      return {
        missing: true,
        candidates: candidates.map((item) => ({
          className: item.className,
          rect: [item.getBoundingClientRect().width, item.getBoundingClientRect().height],
          display: getComputedStyle(item).display,
          visibility: getComputedStyle(item).visibility,
          transform: getComputedStyle(item).transform
        }))
      }
    }
    const rect = drawer.getBoundingClientRect()
    const canvas = {
      transform: document.querySelector('.workflow-svg > g')?.getAttribute('transform') || '',
      nodes: [...document.querySelectorAll('.workflow-node')].map((node) => node.getAttribute('transform'))
    }
    return {
      width: Math.round(rect.width),
      sectionLabels: [...drawer.querySelectorAll('.section-nav-item')].map((item) => item.textContent.trim()),
      horizontalOverflow: drawer.scrollWidth > drawer.clientWidth,
      canvas,
      viewport: [window.innerWidth, window.innerHeight]
    }
  })()`)
  if (!result || result.missing) throw new Error(`Workflow advanced drawer did not render: ${JSON.stringify(result)}`)

  const expectedSections = ['流转规则', '处理人与权限', '动作表单', '按钮展示', '通知']
  const canvasStable = JSON.stringify(result.canvas) === JSON.stringify(canvasBefore)
  if (
    result.width < 520 ||
    result.width > 640 ||
    result.horizontalOverflow ||
    !canvasStable ||
    JSON.stringify(result.sectionLabels) !== JSON.stringify(expectedSections)
  ) {
    throw new Error(`Workflow drawer verification failed: ${JSON.stringify({ ...result, canvasStable })}`)
  }

  const screenshot = await client.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  const screenshotPath = join(tmpdir(), `soar-sdlc-workflow-drawer-${viewportKey}.png`)
  await writeFile(screenshotPath, Buffer.from(screenshot.data, 'base64'))
  return { ...result, canvasStable, screenshotPath }
}

async function dismissDiscardPrompt(client) {
  const result = await evaluateValue(client, `(async () => {
    const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))
    for (let attempt = 0; attempt < 20; attempt += 1) {
      const box = document.querySelector('.el-message-box')
      if (box) {
        const cancel = [...box.querySelectorAll('button')].find((button) => button.textContent.trim() === '取消')
        if (!cancel) return { promptVisible: true, dismissed: false }
        cancel.click()
        await delay(100)
        return {
          promptVisible: true,
          dismissed: true,
          drawerVisible: Boolean(document.querySelector('.workflow-advanced-drawer-modal'))
        }
      }
      await delay(50)
    }
    return { promptVisible: false, dismissed: false }
  })()`)
  if (!result.promptVisible || !result.dismissed || !result.drawerVisible) {
    throw new Error(`Workflow discard prompt verification failed: ${JSON.stringify(result)}`)
  }
  return result
}

async function verifyWorkflowDrawerInteractions(client) {
  const openedAssignment = await evaluateValue(client, `(() => {
    const drawer = document.querySelector('.workflow-advanced-drawer')
    const assignment = [...(drawer?.querySelectorAll('.section-nav-item') || [])]
      .find((button) => button.textContent.trim() === '处理人与权限')
    assignment?.click()
    return Boolean(assignment)
  })()`)
  if (!openedAssignment) throw new Error('Workflow assignment section could not be opened')
  await delay(120)
  const assignmentScreenshot = await client.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  const assignmentScreenshotPath = join(tmpdir(), `soar-sdlc-workflow-assignment-${viewportKey}.png`)
  await writeFile(assignmentScreenshotPath, Buffer.from(assignmentScreenshot.data, 'base64'))

  const editing = await evaluateValue(client, `(async () => {
    const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))
    const drawer = document.querySelector('.workflow-advanced-drawer')
    if (!drawer) return { error: 'drawer_missing' }
    const nav = (label) => [...drawer.querySelectorAll('.section-nav-item')]
      .find((button) => button.textContent.trim() === label)
    const button = (root, label) => [...root.querySelectorAll('button')]
      .find((item) => item.textContent.trim() === label)
    const setInput = (root, label, value) => {
      const item = [...root.querySelectorAll('.el-form-item')]
        .find((candidate) => candidate.querySelector('.el-form-item__label')?.textContent.trim() === label)
      const input = item?.querySelector('input, textarea')
      if (!input) return false
      const prototype = input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
      Object.getOwnPropertyDescriptor(prototype, 'value').set.call(input, value)
      input.dispatchEvent(new Event('input', { bubbles: true }))
      return true
    }
    const selectSection = async (label) => {
      nav(label)?.click()
      await delay(80)
      return drawer.querySelector('.editor-section')
    }

    window.__workflowGraphSaveCalls = 0
    const originalOpen = XMLHttpRequest.prototype.open
    XMLHttpRequest.prototype.open = function (method, url, ...args) {
      if (String(method).toUpperCase() === 'PUT' && String(url).includes('/workflow-definitions/') && String(url).endsWith('/graph')) {
        window.__workflowGraphSaveCalls += 1
      }
      return originalOpen.call(this, method, url, ...args)
    }

    let section = await selectSection('动作表单')
    button(section, '新增字段')?.click()
    await delay(80)
    const firstField = section.querySelector('.field-editor:last-of-type')
    const fieldInputs = firstField ? [...firstField.querySelectorAll('input')] : []
    if (fieldInputs.length < 2) return { error: 'form_inputs_missing' }
    for (const [input, value] of [[fieldInputs[0], 'acceptance_field'], [fieldInputs[1], '验收字段']]) {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value)
      input.dispatchEvent(new Event('input', { bubbles: true }))
    }

    section = await selectSection('流转规则')
    if (!setInput(section, '条件字段', 'acceptance_field')) return { error: 'rule_field_missing' }

    section = await selectSection('处理人与权限')
    const targetRoleItem = [...section.querySelectorAll('.el-form-item')]
      .find((item) => item.querySelector('.el-form-item__label')?.textContent.trim() === '主要目标角色')
    const targetRoleLabel = targetRoleItem?.querySelector('.el-form-item__label')?.getBoundingClientRect()
    const targetRoleSelect = targetRoleItem?.querySelector('.el-select')?.getBoundingClientRect()
    if (!targetRoleLabel || !targetRoleSelect) return { error: 'target_role_layout_missing' }
    const assignmentLayout = {
      selectWidth: Math.round(targetRoleSelect.width),
      labelAbove: targetRoleLabel.bottom <= targetRoleSelect.top + 1
    }
    section.querySelector('.el-switch')?.click()

    section = await selectSection('按钮展示')
    section.querySelector('.el-switch')?.click()

    section = await selectSection('通知')
    section.querySelector('.el-switch')?.click()
    await delay(80)
    if (!setInput(section, '通知标题', '验收通知')) return { error: 'notification_title_missing' }
    await delay(80)

    const sectionStates = Object.fromEntries([...drawer.querySelectorAll('.section-nav-item')].map((item) => [
      item.textContent.trim(),
      item.querySelector('.section-indicator')?.className || ''
    ]))
    const configuredSections = [...drawer.querySelectorAll('.section-indicator.configured')].length
    section = await selectSection('动作表单')
    button(section, '新增字段')?.click()
    await delay(80)
    const duplicateField = section.querySelector('.field-editor:last-of-type')
    const duplicateInput = duplicateField?.querySelector('input')
    if (!duplicateInput) return { error: 'duplicate_input_missing' }
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(duplicateInput, 'acceptance_field')
    duplicateInput.dispatchEvent(new Event('input', { bubbles: true }))
    button(drawer.querySelector('.drawer-footer'), '应用配置')?.click()
    await delay(120)

    const validation = {
      activeSection: drawer.querySelector('.section-nav-item.active')?.textContent.trim(),
      invalidSections: drawer.querySelectorAll('.section-indicator.invalid').length,
      errorVisible: Boolean(drawer.querySelector('.el-form-item.is-error'))
    }
    section = await selectSection('动作表单')
    const duplicateToRemove = section.querySelector('.field-editor:last-of-type')
    button(duplicateToRemove, '删除')?.click()
    await delay(80)
    button(drawer.querySelector('.drawer-footer'), '取消')?.click()
    return { configuredSections, sectionStates, assignmentLayout, validation }
  })()`)
  if (
    editing.error ||
    editing.configuredSections !== 5 ||
    editing.assignmentLayout.selectWidth < 160 ||
    !editing.assignmentLayout.labelAbove ||
    editing.validation.activeSection !== '动作表单' ||
    editing.validation.invalidSections < 1 ||
    !editing.validation.errorVisible
  ) {
    throw new Error(`Workflow drawer editing verification failed: ${JSON.stringify(editing)}`)
  }

  const cancelPrompt = await dismissDiscardPrompt(client)
  await evaluateValue(client, `document.querySelector('.workflow-advanced-drawer .el-drawer__close-btn')?.click()`)
  const closePrompt = await dismissDiscardPrompt(client)
  await client.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape' })
  await client.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape' })
  const escapePrompt = await dismissDiscardPrompt(client)

  const applied = await evaluateValue(client, `(async () => {
    const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))
    const drawer = document.querySelector('.workflow-advanced-drawer')
    const apply = [...drawer.querySelectorAll('.drawer-footer button')]
      .find((button) => button.textContent.trim() === '应用配置')
    apply?.click()
    let closed = false
    for (let attempt = 0; attempt < 20; attempt += 1) {
      const overlay = document.querySelector('.workflow-advanced-drawer-modal')
      if (!overlay || getComputedStyle(overlay).display === 'none') {
        closed = true
        break
      }
      await delay(50)
    }
    const saveCalls = window.__workflowGraphSaveCalls
    document.querySelector('.workflow-advanced-entry .el-button:not([disabled])')?.click()
    await delay(200)
    const reopened = document.querySelector('.workflow-advanced-drawer')
    const nav = (label) => [...reopened.querySelectorAll('.section-nav-item')]
      .find((button) => button.textContent.trim() === label)
    nav('动作表单')?.click()
    await delay(80)
    const fieldValue = reopened.querySelector('.field-editor input')?.value
    const configuredSections = reopened.querySelectorAll('.section-indicator.configured').length
    reopened.querySelector('.el-drawer__close-btn')?.click()
    return { saveCalls, closed, fieldValue, configuredSections }
  })()`)
  if (!applied.closed || applied.saveCalls !== 0 || applied.fieldValue !== 'acceptance_field' || applied.configuredSections !== 5) {
    throw new Error(`Workflow drawer apply verification failed: ${JSON.stringify(applied)}`)
  }

  return {
    configuredSections: editing.configuredSections,
    assignmentLayout: editing.assignmentLayout,
    assignmentScreenshotPath,
    validation: editing.validation,
    discardPrompts: {
      cancel: cancelPrompt.promptVisible,
      close: closePrompt.promptVisible,
      escape: escapePrompt.promptVisible
    },
    applyWithoutSave: applied.saveCalls === 0,
    appliedField: applied.fieldValue
  }
}

async function verifyBugDictionaryRouting(client, token) {
  const templatesResponse = await fetch(
    'http://127.0.0.1:8000/api/v1/workflow-definitions?object_type=bug&scope_type=system',
    { headers: { Authorization: `Bearer ${token}` } }
  )
  if (!templatesResponse.ok) throw new Error(`Bug template lookup failed: ${templatesResponse.status}`)
  const templates = await templatesResponse.json()
  const defaultTemplate = templates.find((item) => item.is_default_template)
  if (!defaultTemplate) throw new Error('Bug default workflow template was not found')

  let resolveInterception
  const intercepted = new Promise((resolve) => { resolveInterception = resolve })
  const removeListener = client.on('Fetch.requestPaused', async ({ requestId, request }) => {
    const url = new URL(request.url)
    if (
      url.pathname.endsWith('/workflow-definitions') &&
      url.searchParams.get('object_type') === 'bug' &&
      url.searchParams.get('scope_type') === 'assignee_rule_config'
    ) {
      await client.send('Fetch.fulfillRequest', {
        requestId,
        responseCode: 200,
        responseHeaders: [{ name: 'content-type', value: 'application/json' }],
        body: Buffer.from(JSON.stringify([defaultTemplate])).toString('base64')
      })
      resolveInterception(true)
      return
    }
    await client.send('Fetch.continueRequest', { requestId })
  })
  await client.send('Fetch.enable', {
    patterns: [{ urlPattern: '*workflow-definitions*', requestStage: 'Request' }]
  })

  const selected = await evaluateValue(client, `(async () => {
    const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))
    for (let attempt = 0; attempt < 20; attempt += 1) {
      const overlay = document.querySelector('.workflow-advanced-drawer-modal')
      if (!overlay || getComputedStyle(overlay).display === 'none') break
      await delay(50)
    }
    const select = document.querySelector('.workflow-object-select .el-select__wrapper')
    if (!select) return false
    select.click()
    return true
  })()`)
  if (!selected) throw new Error('Bug dictionary verification could not open the object type selector')
  await delay(200)
  const choseBug = await evaluateValue(client, `(() => {
    const option = [...document.querySelectorAll('.el-select-dropdown__item')]
      .find((item) => item.textContent.trim() === '缺陷' && getComputedStyle(item).display !== 'none')
    if (!option) return false
    option.click()
    return true
  })()`)
  if (!choseBug) throw new Error('Bug dictionary verification could not select the Bug workflow')
  const didIntercept = await Promise.race([intercepted, delay(3000).then(() => false)])
  if (!didIntercept) throw new Error('Bug dictionary verification did not intercept the workflow list')
  await delay(1800)
  removeListener()
  await client.send('Fetch.disable')

  const result = await evaluateValue(client, `(async () => {
    const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))
    const edges = [...document.querySelectorAll('.workflow-edge')]
    for (const edge of edges) {
      edge.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await delay(80)
      const entry = document.querySelector('.workflow-advanced-entry .el-button:not([disabled])')
      if (!entry) continue
      entry.click()
      await delay(350)
      const drawer = document.querySelector('.workflow-advanced-drawer')
      const dictionaryAlert = [...(drawer?.querySelectorAll('.el-alert__title') || [])]
        .some((item) => item.textContent.trim() === 'Bug 类型字典自动路由')
      if (dictionaryAlert) {
        return {
          found: true,
          dictionaryAlert,
          staticRoutesEditable: drawer.textContent.includes('静态路由')
        }
      }
      drawer?.querySelector('.el-drawer__close-btn')?.click()
      await delay(400)
    }
    return { found: false }
  })()`)
  if (!result.found || !result.dictionaryAlert || result.staticRoutesEditable) {
    throw new Error(`Bug dictionary routing verification failed: ${JSON.stringify(result)}`)
  }
  return result
}

async function main() {
  const profile = join(tmpdir(), `soar-sdlc-edge-${process.pid}`)
  const edge = spawn(edgePath, [
    '--headless=new',
    '--disable-gpu',
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${profile}`,
    '--no-first-run',
    'about:blank'
  ], { stdio: 'ignore' })

  try {
    await waitForDebugger()
    const token = await loginToken()
    const username = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString()).sub
    const targetResponse = await fetch(`http://127.0.0.1:${debugPort}/json/new?http://127.0.0.1:5173`, { method: 'PUT' })
    const client = await connect(await targetResponse.json())
    await client.send('Page.enable')
    await client.send('Runtime.enable')
    await client.send('Emulation.setDeviceMetricsOverride', viewport)
    await delay(1000)
    await client.send('Runtime.evaluate', {
      expression: `localStorage.setItem('access_token', ${JSON.stringify(token)}); localStorage.setItem('current_username', ${JSON.stringify(username)}); localStorage.setItem('current_full_name', ${JSON.stringify(username)}); localStorage.setItem('current_full_name_username', ${JSON.stringify(username)}); localStorage.setItem('must_change_password', 'false')`
    })

    const routes = ['/', '/requirements', '/tasks', '/bugs', '/iterations', '/exception-rules', '/workflow']
    const results = []
    for (const route of routes) {
      await client.send('Page.navigate', { url: `http://127.0.0.1:5173${route}` })
      await delay(1800)
      const evaluated = await client.send('Runtime.evaluate', {
        returnByValue: true,
        expression: `(() => ({
          route: location.pathname,
          title: document.title,
          textLength: (document.body.innerText || '').trim().length,
          viewport: [window.innerWidth, window.innerHeight],
          horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
          loginVisible: Boolean(document.querySelector('.login-card')),
          authError: (document.body.innerText || '').includes('Not authenticated') || (document.body.innerText || '').includes('未登录')
        }))()`
      })
      const result = evaluated.result.value
      if (result.route !== route || result.loginVisible || result.authError || result.textLength < 20 || result.horizontalOverflow) {
        throw new Error(`Desktop verification failed: ${JSON.stringify(result)}`)
      }
      results.push(result)
    }

    const workflowDrawer = await verifyWorkflowDrawer(client)
    const interactionAcceptance = viewportKey === '1440x900'
      ? await verifyWorkflowDrawerInteractions(client)
      : null
    const bugDictionaryRouting = viewportKey === '1440x900'
      ? await verifyBugDictionaryRouting(client, token)
      : null

    await client.send('Page.navigate', { url: 'http://127.0.0.1:5173/' })
    await delay(1200)
    const screenshot = await client.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
    const screenshotPath = join(tmpdir(), 'soar-sdlc-fixed-desktop.png')
    await writeFile(screenshotPath, Buffer.from(screenshot.data, 'base64'))
    client.close()
    console.log(JSON.stringify({
      viewport: [viewport.width, viewport.height],
      routes: results,
      workflowDrawer,
      interactionAcceptance,
      bugDictionaryRouting,
      screenshotPath
    }, null, 2))
  } finally {
    edge.kill()
  }
}

await main()
