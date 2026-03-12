/**
 * 全站中文时区：统一使用中国时区与中文日期格式，避免乱码与时区混乱。
 * 报告日期等均按 Asia/Shanghai 展示。
 */

const TIMEZONE = 'Asia/Shanghai'
const LOCALE = 'zh-CN'

/** 日期时间格式：YYYY-MM-DD HH:mm，中国时区 */
const formatter = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIMEZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/**
 * 将 API 返回的日期字符串格式化为中文展示（中国时区）
 * @param {string|null|undefined} dateStr - ISO 日期字符串或 null
 * @returns {string}
 */
export function formatDate(dateStr) {
  if (dateStr == null || dateStr === '') return ''
  const d = new Date(dateStr)
  if (Number.isNaN(d.getTime())) return ''
  return formatter.format(d).replace(/\//g, '-')
}

/**
 * 仅日期：YYYY-MM-DD，中国时区
 */
const dateOnlyFormatter = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIMEZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour12: false,
})

export function formatDateOnly(dateStr) {
  if (dateStr == null || dateStr === '') return ''
  const d = new Date(dateStr)
  if (Number.isNaN(d.getTime())) return ''
  return dateOnlyFormatter.format(d).replace(/\//g, '-')
}

export { TIMEZONE, LOCALE }
