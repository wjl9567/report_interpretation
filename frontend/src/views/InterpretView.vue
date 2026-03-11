<template>
  <div class="interpret-container">
    <!-- 顶部导航 -->
    <div class="top-bar">
      <div class="top-left">
        <el-button text @click="goHome">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <span class="app-title">报告AI解读</span>
      </div>
      <div class="top-right">
        <el-select v-model="reportType" placeholder="报告类型" size="small" style="width: 120px">
          <el-option label="检验报告" value="lab" />
          <el-option label="B超" value="ultrasound" />
          <el-option label="心电图" value="ecg" />
          <el-option label="脑电图" value="eeg" />
          <el-option label="肺功能" value="pulmonary" />
          <el-option label="CT" value="ct" />
          <el-option label="放射/X光" value="xray" />
          <el-option label="核磁共振" value="mri" />
        </el-select>
        <el-select v-model="departmentCode" placeholder="选择科室" size="small" style="width: 120px">
          <el-option label="通用" value="general" />
          <el-option label="血液科" value="hematology" />
          <el-option label="内科" value="internal" />
          <el-option label="呼吸科" value="respiratory" />
        </el-select>
        <span class="disclaimer-text">⚠ 仅供临床参考，不替代医生诊断</span>
      </div>
    </div>

    <!-- 患者信息条 -->
    <div class="patient-bar" v-if="patientInfo">
      <el-descriptions :column="5" size="small" border>
        <el-descriptions-item label="住院号">{{ patientInfo.patient_id }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ patientInfo.name }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ patientInfo.gender }}</el-descriptions-item>
        <el-descriptions-item label="年龄">{{ patientInfo.age }}岁</el-descriptions-item>
        <el-descriptions-item label="科室">{{ patientInfo.department }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 主内容区域：左右分栏 -->
    <div class="main-content">
      <!-- 左侧：报告列表 + 报告详情 -->
      <div class="left-panel">
        <div class="panel-header">
          <h3>报告</h3>
        </div>

        <!-- 报告列表 -->
        <div class="report-list" v-if="reportList.length > 0">
          <div
            v-for="report in reportList"
            :key="report.report_no"
            class="report-list-item"
            :class="{ active: selectedReportNo === report.report_no }"
            @click="selectReport(report)"
          >
            <div class="report-item-title">
              {{ report.report_title }}
              <el-tag v-if="report.has_critical" type="danger" size="small">危急值</el-tag>
              <el-tag v-else-if="report.has_abnormal" type="warning" size="small">异常</el-tag>
            </div>
            <div class="report-item-date">{{ formatDate(report.report_date) }}</div>
          </div>
        </div>

        <!-- 报告 PDF 展示（LIS 返回 FILEURL 时） -->
        <div class="report-pdf-wrap" v-if="selectedReport?.pdf_url">
          <iframe
            :src="pdfIframeSrc"
            class="report-pdf-iframe"
            title="报告PDF"
          />
        </div>

        <!-- 报告详情表格（无 PDF 时展示结构化项） -->
        <div class="report-detail" v-else-if="interpretResult">
          <el-table
            :data="interpretResult.abnormal_items"
            stripe
            size="small"
            :row-class-name="getRowClassName"
          >
            <el-table-column prop="name" label="检验项目" min-width="160" />
            <el-table-column label="结果" min-width="100">
              <template #default="{ row }">
                <span :style="{ color: row.color, fontWeight: row.abnormal_level !== 'normal' ? '600' : '400' }">
                  {{ row.value }} {{ row.unit }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="reference_range" label="参考范围" min-width="120" />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag
                  :type="getLevelTagType(row.abnormal_level)"
                  size="small"
                  v-if="row.abnormal_level !== 'normal'"
                >
                  {{ row.level_label }}
                </el-tag>
                <span v-else style="color: #52c41a">正常</span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 空状态 -->
        <div class="empty-state" v-if="!loading && reportList.length === 0 && searched">
          <el-empty description="未找到该患者的报告" />
        </div>
      </div>

      <!-- 右侧：AI解读结果 -->
      <div class="right-panel">
        <div class="panel-header">
          <h3>AI解读结果</h3>
          <div class="interpret-meta" v-if="interpretResult">
            <el-tag type="info" size="small">{{ interpretResult.model_name }}</el-tag>
            <el-tag type="info" size="small">{{ interpretResult.latency_ms }}ms</el-tag>
            <el-tag :type="confidenceType" size="small">可信度: {{ confidenceLabel }}</el-tag>
          </div>
        </div>

        <!-- 加载状态 -->
        <div class="loading-state" v-if="interpreting">
          <el-icon class="loading-icon" :size="32"><Loading /></el-icon>
          <p>AI正在解读报告，请稍候...</p>
        </div>

        <!-- 解读结果 -->
        <div class="interpret-result" v-else-if="interpretResult">
          <div class="result-section">
            <div class="section-title">
              <el-icon color="#ff4d4f"><WarningFilled /></el-icon>
              <span>异常总结</span>
            </div>
            <div class="section-content" v-html="formatContent(interpretResult.abnormal_summary)"></div>
          </div>

          <div class="result-section">
            <div class="section-title">
              <el-icon color="#1677ff"><InfoFilled /></el-icon>
              <span>临床意义</span>
            </div>
            <div class="section-content" v-html="formatContent(interpretResult.clinical_significance)"></div>
          </div>

          <div class="result-section">
            <div class="section-title">
              <el-icon color="#52c41a"><CircleCheckFilled /></el-icon>
              <span>临床建议</span>
            </div>
            <div class="section-content" v-html="formatContent(interpretResult.clinical_suggestion)"></div>
          </div>

          <div class="result-disclaimer">
            ⚠ {{ interpretResult.disclaimer }}
          </div>
        </div>

        <!-- 未解读状态 -->
        <div class="empty-interpret" v-else-if="!interpreting && selectedReportNo">
          <el-button type="primary" size="large" @click="doInterpret">
            <el-icon><MagicStick /></el-icon>
            开始AI解读
          </el-button>
        </div>

        <div class="empty-interpret" v-else>
          <p style="color: #999">请先选择一份报告</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getReportList, interpretReport } from '@/api'

const route = useRoute()
const router = useRouter()

const patientInfo = ref(null)
const reportList = ref([])
const selectedReportNo = ref('')
const interpretResult = ref(null)
const reportType = ref('lab')
const departmentCode = ref('general')
const loading = ref(false)
const interpreting = ref(false)
const searched = ref(false)

const confidenceLabel = computed(() => {
  const map = { high: '高', medium: '中', low: '低' }
  return map[interpretResult.value?.confidence] || ''
})

const confidenceType = computed(() => {
  const map = { high: 'success', medium: 'warning', low: 'danger' }
  return map[interpretResult.value?.confidence] || 'info'
})

const selectedReport = computed(() =>
  reportList.value.find((r) => r.report_no === selectedReportNo.value)
)

const pdfIframeSrc = computed(() => {
  const url = selectedReport.value?.pdf_url
  if (!url) return ''
  if (url.startsWith('http')) return url
  return url
})

onMounted(async () => {
  const pid = route.params.patientId
  if (pid) {
    await fetchReportList(pid)
  }
})

async function fetchReportList(patientId) {
  loading.value = true
  searched.value = true
  try {
    const res = await getReportList(patientId)
    patientInfo.value = res.data.patient
    reportList.value = res.data.reports

    if (reportList.value.length > 0) {
      await selectReport(reportList.value[0])
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '查询失败')
  } finally {
    loading.value = false
  }
}

async function selectReport(report) {
  selectedReportNo.value = report.report_no
  interpretResult.value = null
  await doInterpret()
}

async function doInterpret() {
  if (!selectedReportNo.value || !patientInfo.value) return

  interpreting.value = true
  try {
    const res = await interpretReport({
      patient_id: patientInfo.value.patient_id,
      report_no: selectedReportNo.value,
      department_code: departmentCode.value,
      report_type: reportType.value,
    })
    interpretResult.value = res.data
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || 'AI解读失败，请重试')
  } finally {
    interpreting.value = false
  }
}

function goHome() {
  router.push('/')
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function formatContent(text) {
  if (!text) return ''
  return text
    .replace(/\n/g, '<br/>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/- /g, '• ')
}

function getLevelTagType(level) {
  const map = { critical: 'danger', severe: 'danger', moderate: 'warning', mild: '' }
  return map[level] || 'info'
}

function getRowClassName({ row }) {
  if (row.abnormal_level === 'critical') return 'row-critical'
  if (row.abnormal_level === 'severe') return 'row-severe'
  return ''
}
</script>

<style scoped>
.interpret-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
}

.top-bar {
  height: 52px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.top-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-title {
  font-size: 16px;
  font-weight: 600;
  color: #1677ff;
}

.top-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.disclaimer-text {
  font-size: 12px;
  color: #ff4d4f;
  background: #fff2f0;
  padding: 4px 12px;
  border-radius: 4px;
}

.patient-bar {
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.main-content {
  flex: 1;
  display: flex;
  gap: 1px;
  background: #e8e8e8;
  overflow: hidden;
}

.left-panel, .right-panel {
  background: #fff;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.left-panel {
  width: 50%;
  min-width: 400px;
}

.right-panel {
  width: 50%;
  min-width: 400px;
}

.panel-header {
  padding: 12px 20px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.panel-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: #333;
}

.interpret-meta {
  display: flex;
  gap: 6px;
}

.report-list {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.report-list-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.report-list-item:hover {
  background: #f5f7fa;
}

.report-list-item.active {
  background: #e6f4ff;
  border: 1px solid #91caff;
}

.report-item-title {
  font-size: 14px;
  color: #333;
  display: flex;
  align-items: center;
  gap: 8px;
}

.report-item-date {
  font-size: 12px;
  color: #999;
}

.report-pdf-wrap {
  flex: 1;
  min-height: 400px;
  padding: 12px;
  overflow: hidden;
}

.report-pdf-iframe {
  width: 100%;
  height: 100%;
  min-height: 500px;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
}

.report-detail {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
}

.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #1677ff;
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.interpret-result {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.result-section {
  margin-bottom: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #f0f0f0;
}

.section-content {
  font-size: 14px;
  line-height: 1.8;
  color: #555;
  padding-left: 8px;
}

.result-disclaimer {
  margin-top: 24px;
  padding: 12px 16px;
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 8px;
  font-size: 13px;
  color: #ad6800;
  text-align: center;
}

.empty-interpret {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

:deep(.row-critical) {
  background-color: #fff1f0 !important;
}

:deep(.row-severe) {
  background-color: #fff7e6 !important;
}
</style>
