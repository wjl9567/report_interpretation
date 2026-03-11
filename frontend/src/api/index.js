import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

/** 搜索患者 */
export function searchPatient(keyword) {
  return api.get('/report/patient/search', { params: { keyword } })
}

/** 获取患者报告列表 */
export function getReportList(patientId) {
  return api.get(`/report/list/${patientId}`)
}

/** AI解读报告 */
export function interpretReport(data) {
  return api.post('/report/interpret', data)
}

/** 直接传入数据解读 */
export function interpretDirect(data) {
  return api.post('/report/interpret/direct', data)
}

/** 上传图片并解读 */
export function uploadAndInterpret(formData) {
  return api.post('/ocr/interpret', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}

/** 仅OCR识别 */
export function uploadAndRecognize(formData) {
  return api.post('/ocr/recognize', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/** 系统健康检查 */
export function healthCheck() {
  return api.get('/system/health')
}

/** 获取前端配置 */
export function getConfig() {
  return api.get('/system/config')
}

export default api
