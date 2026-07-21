import ELK from 'elkjs/lib/elk.bundled.js'

const elk = new ELK()

self.onmessage = async ({ data }) => {
  const { requestId, graph } = data || {}
  try {
    const result = await elk.layout(graph)
    self.postMessage({ requestId, result })
  } catch (error) {
    self.postMessage({
      requestId,
      error: error instanceof Error ? error.message : String(error)
    })
  }
}

