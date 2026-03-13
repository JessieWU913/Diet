const COOKING_VERBS = [
  '焯水', '腌制', '勾芡', '收汁', '翻炒', '爆炒', '快炒', '慢炖', '炖煮', '煎至', '煎', '炸', '烤',
  '蒸', '煮', '炒', '炖', '拌', '焖', '熬', '焗', '煸', '汆', '卤', '切', '洗', '泡', '浸泡', '剁', '拍',
  '压', '捣', '加', '放入', '加入', '倒入', '淋入', '撒入', '搅拌', '搅匀', '翻匀', '搅打', '打散', '打发',
  '调味', '腌', '冷藏', '静置', '小火', '中火', '大火', '转小火', '转中火', '加热', '预热', '出锅', '装盘'
]

const VERB_REG = new RegExp(`(${COOKING_VERBS.sort((a, b) => b.length - a.length).join('|')})`, 'g')

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
  return escapeHtml(line).replace(VERB_REG, '<span class="step-verb">$1</span>')
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
