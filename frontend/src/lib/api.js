function headers(keys = {}) {
  const h = { 'Content-Type': 'application/json' }
  if (keys.gemini) h['X-Gemini-Key'] = keys.gemini
  if (keys.fal) h['X-Fal-Key'] = keys.fal
  if (keys.elevenlabs) h['X-Elevenlabs-Key'] = keys.elevenlabs
  return h
}

async function json(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function analyzeProduct({ url, description, language, actorGender, numScripts = 3 }, keys) {
  return json(await fetch('/api/ugc/analyze', {
    method: 'POST',
    headers: headers(keys),
    body: JSON.stringify({ url, description, language, actor_gender: actorGender, num_scripts: numScripts }),
  }))
}

export async function getActorOptions({ actorDescription, numOptions = 3 }, keys) {
  return json(await fetch('/api/ugc/actor-options', {
    method: 'POST',
    headers: headers(keys),
    body: JSON.stringify({ actor_description: actorDescription, num_options: numOptions }),
  }))
}

export async function uploadActor(file) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch('/api/ugc/actor-upload', { method: 'POST', body: fd })
  return json(res)
}

export async function generateVideo(payload, keys) {
  return json(await fetch('/api/ugc/generate', {
    method: 'POST',
    headers: headers(keys),
    body: JSON.stringify(payload),
  }))
}

export async function getJobStatus(jobId) {
  return json(await fetch(`/api/ugc/status/${jobId}`))
}

export async function getGallery() {
  return json(await fetch('/api/gallery'))
}

export async function socialPost(payload, keys) {
  return json(await fetch('/api/ugc/social/post', {
    method: 'POST',
    headers: headers(keys),
    body: JSON.stringify(payload),
  }))
}
