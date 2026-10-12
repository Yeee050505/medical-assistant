export async function streamChat(sessionId, body, handlers) {
  const token = localStorage.getItem('token')
  const resp = await fetch(`/api/v1/chat/session/${sessionId}/message`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    let msg = `请求失败 (${resp.status})`
    try {
      const data = await resp.json()
      msg = data.msg || msg
    } catch {
      /* ignore */
    }
    throw new Error(msg)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      let event = 'message'
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7).trim()
        else if (line.startsWith('data: ')) data = line.slice(6)
      }
      if (!data) continue
      try {
        handlers[event]?.(JSON.parse(data))
      } catch {
        /* ignore malformed block */
      }
    }
  }
}
