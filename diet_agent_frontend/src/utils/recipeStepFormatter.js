const escapeHtml = (str) => {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const normalizeStepPrefix = (line) => {
  return line.replace(/^\s*(?:第\s*\d+\s*步|步骤\s*\d+|\d+)\s*[：:.、\-]?\s*/i, '').trim()
}

const splitToSteps = (raw) => {
  if (raw === null || raw === undefined) return []

  if (Array.isArray(raw)) {
    return raw
      .map((x) => normalizeStepPrefix(String(x || '').trim()))
      .filter(Boolean)
  }

  const text = String(raw).trim()
  if (!text) return []

  try {
    const parsed = JSON.parse(text)
    if (Array.isArray(parsed)) {
      return parsed
        .map((x) => normalizeStepPrefix(String(x || '').trim()))
        .filter(Boolean)
    }
  } catch {
    // Keep processing as plain text.
  }

  const byLines = text
    .split(/\r?\n+/)
    .map((x) => normalizeStepPrefix(x.trim()))
    .filter(Boolean)

  if (byLines.length > 1) return byLines

  return text
    .split(/[。；;]+/)
    .map((x) => normalizeStepPrefix(x.trim()))
    .filter(Boolean)
}

const stylizeStepText = (line) => {
  return escapeHtml(line)
}

export const formatRecipeStepsHtml = (raw) => {
  const steps = splitToSteps(raw)
  if (steps.length === 0) return ''

  return [
    '<ol class="recipe-steps-list">',
    ...steps.map((step, idx) => {
      const num = `<span class="step-index">${idx + 1}</span>`
      const text = `<span class="step-text">${stylizeStepText(step)}</span>`
      return `<li class="recipe-step-item">${num}${text}</li>`
    }),
    '</ol>'
  ].join('')
}
