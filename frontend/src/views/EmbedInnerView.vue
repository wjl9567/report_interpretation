<template>
  <div class="embed-container">
    <div class="embed-header">
      <span class="embed-title">报告AI解读</span>
    </div>

    <!-- 患者号输入（两种模式都需要） -->
    <div class="embed-search">
      <el-input
        v-model="patientId"
        placeholder="输入住院号/门诊号"
        size="small"
        clearable
        @keyup.enter="onPatientSubmit"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <div class="select-row">
        <el-select v-model="reportType" size="small" style="flex:1">
          <el-option label="检验报告" value="lab" />
          <el-option label="B超" value="ultrasound" />
          <el-option label="心电图" value="ecg" />
          <el-option label="脑电图" value="eeg" />
          <el-option label="肺功能" value="pulmonary" />
          <el-option label="CT" value="ct" />
          <el-option label="放射/X光" value="xray" />
          <el-option label="核磁共振" value="mri" />
        </el-select>
        <el-select v-model="deptCode" size="small" style="flex:1">
          <el-option label="通用" value="general" />
          <el-option label="血液科" value="hematology" />
          <el-option label="内科" value="internal" />
          <el-option label="呼吸科" value="respiratory" />
        </el-select>
      </div>
      <!-- list_select：查报告列表；latest_auto：查询并解读 -->
      <el-button
        type="primary"
        size="small"
        style="width:100%; margin-top:8px"
        :loading="loading"
        @click="onPatientSubmit"
      >
        {{ isListSelectMode ? '查询报告列表' : '查询并解读' }}
      </el-button>
    </div>

    <!-- list_select 模式：报告列表 + 选中解读 -->
    <template v-if="isListSelectMode">
      <div class="embed-list" v-if="reportList.length > 0">
        <div class="list-title">报告列表（选中即解读）</div>
        <div
          v-for="r in reportList"
          :key="r.report_no"
          class="report-row"
          :class="{ active: selectedReportNo === r.report_no }"
          @click="selectReport(r)"
        >
          <span class="report-name">{{ r.report_title }}</span>
          <span class="report-date">{{ formatDate(r.report_date) }}</span>
        </div>
      </div>
      <div v-else-if="searched && reportList.length === 0" class="embed-empty">
        该患者暂无报告
      </div>
      <!-- 选中后的 PDF（若有）与解读结果 -->
      <div class="embed-result" v-if="selectedReportNo">
        <div v-if="selectedPdfUrl" class="embed-pdf-wrap">
          <iframe :src="selectedPdfUrl" class="embed-pdf-iframe" title="报告PDF" />
        </div>
        <div v-if="loading" class="state-box">
          <el-icon class="spin" :size="24"><Loading /></el-icon>
          <span>AI解读中...</span>
        </div>
        <div v-else-if="result" class="result-content" v-html="formatResult(result)"></div>
        <div v-else-if="error" class="embed-error">
          <el-alert :title="error" type="error" show-icon :closable="false" />
        </div>
      </div>
    </template>

    <!-- latest_auto 模式：直接展示解读结果 -->
    <template v-else>
      <div class="embed-upload">
        <el-upload :auto-upload="false" :show-file-list="false" :on-change="handleUpload" accept=".jpg,.jpeg,.png,.bmp">
          <el-button size="small" style="width:100%">
            <el-icon><UploadFilled /></el-icon> 上传报告图片解读
          </el-button>
        </el-upload>
      </div>
      <div class="embed-result">
        <div v-if="loading" class="state-box">
          <el-icon class="spin" :size="24"><Loading /></el-icon>
          <span>AI解读中...</span>
        </div>
        <div v-else-if="result" class="result-content" v-html="formatResult(result)"></div>
        <div v-else-if="error" style="padding:8px 0">
          <el-alert :title="error" type="error" show-icon :closable="false" />
        </div>
        <div v-else class="state-box" style="color:#bbb">
          输入住院号/门诊号查询<br/>或上传报告图片
        </div>
      </div>
    </template>

    <div class="embed-actions">
      <el-button text size="small" @click="openFull">
        <el-icon><FullScreen /></el-icon> 打开完整版
      </el-button>
    </div>
    <div class="embed-footer">⚠ 仅供临床参考，不替代医生诊断</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getConfig, getReportList, interpretReport, uploadAndInterpret } from '@/api'

const route = useRoute()
const patientId = ref('')
const reportType = ref('lab')
const deptCode = ref('general')
const loading = ref(false)
const result = ref('')
const error = ref('')
const embedReportMode = ref('list_select')
const reportList = ref([])
const selectedReportNo = ref('')
const selectedPdfUrl = ref('')
const searched = ref(false)

const isListSelectMode = computed(() => embedReportMode.value === 'list_select')

onMounted(async () => {
  try {
    const res = await getConfig()
    embedReportMode.value = res.data.embed_report_mode || 'list_select'
  } catch {
    embedReportMode.value = 'list_select'
  }
  if (route.meta?.embedReportMode) {
    embedReportMode.value = route.meta.embedReportMode
  }
  const pid = route.params.patientId || route.query.pid
  if (pid) {
    patientId.value = pid
    if (isListSelectMode.value) {
      await fetchReportList()
    } else {
      doInterpretLatest()
    }
  }
})

async function onPatientSubmit() {
  if (!patientId.value.trim()) return
  if (isListSelectMode.value) {
    await fetchReportList()
  } else {
    doInterpretLatest()
  }
}

async function fetchReportList() {
  if (!patientId.value.trim()) return
  loading.value = true
  error.value = ''
  result.value = ''
  reportList.value = []
  selectedReportNo.value = ''
  selectedPdfUrl.value = ''
  searched.value = true
  try {
    const res = await getReportList(patientId.value.trim())
    reportList.value = res.data.reports || []
  } catch (err) {
    error.value = err.response?.data?.detail || '获取报告列表失败'
  } finally {
    loading.value = false
  }
}

function selectReport(report) {
  selectedReportNo.value = report.report_no
  selectedPdfUrl.value = report.pdf_url || ''
  result.value = ''
  error.value = ''
  doInterpretReport(report.report_no)
}

async function doInterpretReport(reportNo) {
  if (!patientId.value.trim() || !reportNo) return
  loading.value = true
  error.value = ''
  try {
    const res = await interpretReport({
      patient_id: patientId.value.trim(),
      report_no: reportNo,
      department_code: deptCode.value,
      report_type: reportType.value,
    })
    const d = res.data
    result.value = [
      d.abnormal_summary ? `【异常发现】\n${d.abnormal_summary}` : '',
      d.clinical_significance ? `【临床意义】\n${d.clinical_significance}` : '',
      d.clinical_suggestion ? `【临床建议】\n${d.clinical_suggestion}` : '',
    ].filter(Boolean).join('\n\n') || '解读完成'
  } catch (err) {
    error.value = err.response?.data?.detail || '解读失败'
  } finally {
    loading.value = false
  }
}

async function doInterpretLatest() {
  if (!patientId.value.trim()) return
  loading.value = true
  error.value = ''
  result.value = ''
  try {
    const res = await interpretReport({
      patient_id: patientId.value.trim(),
      department_code: deptCode.value,
      report_type: reportType.value,
    })
    const d = res.data
    result.value = [
      d.abnormal_summary ? `【异常发现】\n${d.abnormal_summary}` : '',
      d.clinical_significance ? `【临床意义】\n${d.clinical_significance}` : '',
      d.clinical_suggestion ? `【临床建议】\n${d.clinical_suggestion}` : '',
    ].filter(Boolean).join('\n\n') || '解读完成'
  } catch (err) {
    error.value = err.response?.data?.detail || '解读失败'
  } finally {
    loading.value = false
  }
}

async function handleUpload(uploadFile) {
  loading.value = true
  error.value = ''
  result.value = ''
  const formData = new FormData()
  formData.append('file', uploadFile.raw)
  formData.append('department_code', deptCode.value)
  formData.append('report_type', reportType.value)
  try {
    const res = await uploadAndInterpret(formData)
    result.value = res.data.interpretation
  } catch (err) {
    error.value = err.response?.data?.detail || '解读失败'
  } finally {
    loading.value = false
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function openFull() {
  const url = patientId.value ? `/interpret/${patientId.value}` : '/'
  window.open(url, '_blank')
}

function formatResult(text) {
  return text
    .replace(/\n/g, '<br/>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/【(.*?)】/g, '<h4 style="margin:12px 0 6px;color:#1677ff;font-size:13px">$1</h4>')
    .replace(/- /g, '• ')
}
</script>

<style scoped>
.embed-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: #fff;
}
.embed-header {
  padding: 10px 16px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}
.embed-title {
  font-size: 15px;
  font-weight: 600;
  color: #1677ff;
}
.embed-search {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}
.select-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.embed-upload {
  padding: 8px 16px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}
.embed-list {
  flex-shrink: 0;
  padding: 8px 16px;
  border-bottom: 1px solid #f0f0f0;
  max-height: 200px;
  overflow-y: auto;
}
.list-title {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}
.report-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  margin-bottom: 4px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  background: #fafafa;
}
.report-row:hover,
.report-row.active {
  background: #e6f4ff;
  color: #1677ff;
}
.report-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.report-date { font-size: 11px; color: #999; margin-left: 8px; }
.embed-empty {
  padding: 12px 16px;
  font-size: 13px;
  color: #999;
  flex-shrink: 0;
}
.embed-pdf-wrap {
  height: 220px;
  margin-bottom: 12px;
  border: 1px solid #eee;
  border-radius: 4px;
  overflow: hidden;
}
.embed-pdf-iframe {
  width: 100%;
  height: 100%;
  border: none;
}
.embed-result {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.embed-error { padding: 8px 0; }
.state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 180px;
  gap: 12px;
  color: #1677ff;
  text-align: center;
  font-size: 13px;
  line-height: 1.8;
}
.spin { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.result-content {
  font-size: 13px;
  line-height: 1.8;
  color: #333;
}
.embed-actions {
  padding: 4px 16px;
  border-top: 1px solid #f0f0f0;
  text-align: center;
  flex-shrink: 0;
}
.embed-footer {
  padding: 6px 16px;
  text-align: center;
  font-size: 11px;
  color: #ff4d4f;
  background: #fff2f0;
  flex-shrink: 0;
}
</style>
