export function getKey(name) {
  return localStorage.getItem(`apikey_${name}`) || ''
}

export function setKey(name, value) {
  localStorage.setItem(`apikey_${name}`, value)
}
