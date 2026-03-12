import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Accept-Language': 'zh-CN',
    'Accept': 'application/json; charset=utf-8',
  },
})

/** 搜索患者 */
export function searchPatient(keyword) {
  return api.get('/report/patient/search', { params: { keyword } })
}

/**
 * 获取患者报告列表
 * 返回 reports[]：report_no, report_title, report_date, pdf_url, report_source(lab=检验/8092, exam=检查/8091) 等，与后端 ReportListItem 一致
 */
export function getReportList(patientId) {
  return api.get(`/report/list/${patientId}`)
}

/** 获取报告详情（含项目列表，解读前展示） */
export function getReportDetail(patientId, reportNo) {
  return api.get('/report/detail', { params: { patient_id: patientId, report_no: reportNo } })
}

/** AI解读报告 */
export function interpretReport(data) {
  return api.post('/report/interpret', data)
}

/** 多份同类报告对比解读（在「多份对比解读」页左侧选中同类≥2 后调用） */
export function interpretMulti(patientId, reportNos) {
  return api.post('/report/interpret-multi', { patient_id: patientId, report_nos: reportNos })
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
