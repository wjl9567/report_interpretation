<template>
  <div class="embed-container">
    <div class="embed-header">
      <span class="embed-title">报告AI解读</span>
    </div>

    <!-- 患者信息条（有患者时展示） -->
    <div class="embed-patient-bar" v-if="patientInfo">
      <el-descriptions :column="4" size="small" border>
        <el-descriptions-item :label="patientIdLabel">{{ patientInfo.patient_id }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ patientInfo.name }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ patientInfo.gender }}</el-descriptions-item>
        <el-descriptions-item label="年龄">{{ patientInfo.age }}岁</el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 患者号输入（两种模式都需要） -->
    <div class="embed-search">
      <el-input
        v-model="patientId"
        :placeholder="searchPlaceholder"
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
        <el-tabs v-model="reportListSourceTab" class="embed-report-tabs">
          <el-tab-pane label="全部" name="all" />
          <el-tab-pane name="lab">
            <template #label>
              <span>检验</span>
              <el-badge v-if="labReportCount > 0" :value="labReportCount" class="embed-tab-badge" />
            </template>
          </el-tab-pane>
          <el-tab-pane name="exam">
            <template #label>
              <span>检查</span>
              <el-badge v-if="examReportCount > 0" :value="examReportCount" class="embed-tab-badge" />
            </template>
          </el-tab-pane>
        </el-tabs>
        <div
          v-for="r in filteredReportList"
          :key="r.report_no"
          class="report-row"
          :class="{ active: selectedReportNo === r.report_no }"
          @click="selectReport(r)"
        >
          <span class="report-name">{{ r.report_title }}</span>
          <span v-if="r.report_source === 'lab'" class="report-source report-source-lab">检验</span>
          <span v-else-if="r.report_source === 'exam'" class="report-source report-source-exam">检查</span>
          <span class="report-date">{{ formatDate(r.report_date) }}</span>
        </div>
      </div>
      <div v-else-if="searched && reportList.length === 0" class="embed-empty">
        <p>该患者暂无报告</p>
        <p class="empty-hint">请核对住院号/门诊号或病历号是否与系统一致。</p>
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
        <template v-else-if="interpretResult">
          <div class="result-section">
            <div class="section-title">异常总结</div>
            <div class="section-content" v-html="formatResult(interpretResult.abnormal_summary)"></div>
          </div>
          <div class="result-section">
            <div class="section-title">临床意义</div>
            <div class="section-content" v-html="formatResult(interpretResult.clinical_significance)"></div>
          </div>
          <div class="result-section">
            <div class="section-title">临床建议</div>
            <div class="section-content" v-html="formatResult(interpretResult.clinical_suggestion)"></div>
          </div>
        </template>
        <div v-else-if="error" class="embed-error">
          <el-alert :title="error" type="error" show-icon :closable="false" />
          <el-button type="primary" size="small" style="margin-top:8px" @click="retryInterpret">重试解读</el-button>
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
        <template v-else-if="interpretResult">
          <template v-if="interpretResult.abnormal_summary != null">
            <div class="result-section">
              <div class="section-title">异常总结</div>
              <div class="section-content" v-html="formatResult(interpretResult.abnormal_summary)"></div>
            </div>
            <div class="result-section">
              <div class="section-title">临床意义</div>
              <div class="section-content" v-html="formatResult(interpretResult.clinical_significance)"></div>
            </div>
            <div class="result-section">
              <div class="section-title">临床建议</div>
              <div class="section-content" v-html="formatResult(interpretResult.clinical_suggestion)"></div>
            </div>
          </template>
          <div v-else-if="interpretResult.interpretation" class="result-content" v-html="formatResult(interpretResult.interpretation)"></div>
        </template>
        <div v-else-if="error" style="padding:8px 0">
          <el-alert :title="error" type="error" show-icon :closable="false" />
          <el-button type="primary" size="small" style="margin-top:8px" @click="retryLatest">重试解读</el-button>
        </div>
        <div v-else class="state-box" style="color:#bbb; white-space: pre-line">
          {{ searchEmptyText }}
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
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getConfig, getReportList, interpretReport, uploadAndInterpret } from '@/api'
import { formatDate } from '@/utils/datetime'

const route = useRoute()
const patientId = ref('')
const patientInfo = ref(null)
const reportType = ref('lab')
const deptCode = ref('general')
const loading = ref(false)
const interpretResult = ref(null)
const error = ref('')
const embedReportMode = ref('list_select')
const reportList = ref([])
const reportListSourceTab = ref('all')
const selectedReportNo = ref('')
const selectedPdfUrl = ref('')
const searched = ref(false)
const mssqlHidResolver = ref(false)

const isListSelectMode = computed(() => embedReportMode.value === 'list_select')
const labReportCount = computed(() => reportList.value.filter((r) => r.report_source === 'lab').length)
const examReportCount = computed(() => reportList.value.filter((r) => r.report_source === 'exam').length)
const filteredReportList = computed(() => {
  if (reportListSourceTab.value === 'lab') return reportList.value.filter((r) => r.report_source === 'lab')
  if (reportListSourceTab.value === 'exam') return reportList.value.filter((r) => r.report_source === 'exam')
  return reportList.value
})
const patientIdLabel = computed(() => (mssqlHidResolver.value ? '患者标识' : '住院号'))
const searchPlaceholder = computed(() =>
  mssqlHidResolver.value ? '输入住院号/门诊号或病历号/门诊卡号' : '输入住院号/门诊号'
)
const searchEmptyText = computed(() =>
  mssqlHidResolver.value ? '输入住院号/门诊号或病历号查询\n或上传报告图片' : '输入住院号/门诊号查询\n或上传报告图片'
)

watch([reportListSourceTab, filteredReportList], () => {
  const list = filteredReportList.value
  if (list.length === 0) return
  const stillInList = list.some((r) => r.report_no === selectedReportNo.value)
  if (!stillInList) selectReport(list[0])
}, { immediate: false })

onMounted(async () => {
  try {
    const res = await getConfig()
    embedReportMode.value = res.data.embed_report_mode || 'list_select'
    mssqlHidResolver.value = !!res.data.mssql_hid_resolver
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
  interpretResult.value = null
  reportList.value = []
  selectedReportNo.value = ''
  selectedPdfUrl.value = ''
  searched.value = true
  try {
    const res = await getReportList(patientId.value.trim())
    patientInfo.value = res.data.patient ?? null
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
  interpretResult.value = null
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
    interpretResult.value = res.data
  } catch (err) {
    error.value = err.response?.data?.detail || '解读失败'
  } finally {
    loading.value = false
  }
}

function retryInterpret() {
  if (selectedReportNo.value) doInterpretReport(selectedReportNo.value)
}

async function doInterpretLatest() {
  if (!patientId.value.trim()) return
  loading.value = true
  error.value = ''
  interpretResult.value = null
  try {
    const res = await interpretReport({
      patient_id: patientId.value.trim(),
      department_code: deptCode.value,
      report_type: reportType.value,
    })
    interpretResult.value = res.data
  } catch (err) {
    error.value = err.response?.data?.detail || '解读失败'
  } finally {
    loading.value = false
  }
}

function retryLatest() {
  doInterpretLatest()
}

async function handleUpload(uploadFile) {
  loading.value = true
  error.value = ''
  interpretResult.value = null
  const formData = new FormData()
  formData.append('file', uploadFile.raw)
  formData.append('department_code', deptCode.value)
  formData.append('report_type', reportType.value)
  try {
    const res = await uploadAndInterpret(formData)
    interpretResult.value = { interpretation: res.data.interpretation }
  } catch (err) {
    error.value = err.response?.data?.detail || '解读失败'
  } finally {
    loading.value = false
  }
}

function openFull() {
  const url = patientId.value ? `/interpret/${patientId.value}` : '/'
  window.open(url, '_blank')
}

function formatResult(text) {
  if (text == null || text === '') return ''
  return String(text)
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
.embed-patient-bar {
  padding: 8px 16px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
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
  margin-bottom: 4px;
}
.embed-report-tabs {
  margin-bottom: 8px;
}
.embed-report-tabs :deep(.el-tabs__header) { margin-bottom: 0; }
.embed-report-tabs :deep(.el-tabs__item) { font-size: 12px; padding: 0 12px; }
.embed-report-tabs :deep(.el-tabs__nav-wrap::after) { display: none; }
.embed-tab-badge { margin-left: 2px; }
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
.report-source { font-size: 10px; color: #909399; margin-left: 6px; flex-shrink: 0; }
.report-date { font-size: 11px; color: #999; margin-left: 8px; flex-shrink: 0; }
.embed-empty {
  padding: 12px 16px;
  font-size: 13px;
  color: #999;
  flex-shrink: 0;
}
.embed-empty .empty-hint {
  font-size: 12px;
  color: #bbb;
  margin-top: 4px;
}
.result-section {
  margin-bottom: 14px;
}
.result-section .section-title {
  font-size: 13px;
  font-weight: 600;
  color: #1677ff;
  margin-bottom: 6px;
}
.result-section .section-content {
  font-size: 13px;
  color: #333;
  line-height: 1.6;
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
