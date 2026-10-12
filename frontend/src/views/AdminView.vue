<template>
  <div class="admin-layout">
    <TopBar />
    <div class="content">
      <el-tabs v-model="tab">
        <el-tab-pane label="药品知识库" name="rag">
          <el-card shadow="never">
            <div class="upload-row">
              <el-input v-model="form.drugName" placeholder="药品名称" style="width: 180px" />
              <el-input v-model="form.version" placeholder="说明书版本（可选）" style="width: 180px" />
              <input
                ref="fileInput"
                type="file"
                accept=".pdf,.txt,.md"
                @change="onPickFile"
              />
              <el-button type="primary" :loading="uploading" @click="uploadDoc">
                上传入库
              </el-button>
              <span v-if="pickedName" class="picked">{{ pickedName }}</span>
            </div>
          </el-card>

          <el-card shadow="never" style="margin-top: 12px">
            <div class="list-row">
              <el-input
                v-model="keyword"
                placeholder="按药品名搜索"
                clearable
                style="width: 220px"
                @keyup.enter="loadDocs"
                @clear="loadDocs"
              />
              <el-button @click="loadDocs">查询</el-button>
            </div>
            <el-table :data="docs" v-loading="loading" style="margin-top: 10px">
              <el-table-column prop="drugName" label="药品名称" min-width="140" />
              <el-table-column prop="version" label="版本" width="100" />
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'">
                    {{ row.status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="参与检索" width="100">
                <template #default="{ row }">
                  <el-switch
                    :model-value="row.enabled"
                    :disabled="row.status !== 'success'"
                    @change="(v) => toggleStatus(row, v)"
                  />
                </template>
              </el-table-column>
              <el-table-column prop="createdAt" label="上传时间" width="170">
                <template #default="{ row }">
                  {{ (row.createdAt || '').replace('T', ' ').slice(0, 19) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button link type="primary" @click="openSearch(row)">检索调试</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-pagination
              style="margin-top: 10px; justify-content: flex-end"
              layout="total, prev, pager, next"
              :total="total"
              :page-size="size"
              :current-page="page"
              @current-change="(p) => { page = p; loadDocs() }"
            />
          </el-card>

          <el-dialog v-model="searchVisible" :title="`检索调试 - ${searchDrug}`" width="720px">
            <div class="list-row">
              <el-input
                v-model="searchQuery"
                placeholder="输入检索 query，如：阿莫西林的禁忌"
                style="flex: 1"
                @keyup.enter="doSearch"
              />
              <el-input-number v-model="searchTopK" :min="1" :max="20" />
              <el-button type="primary" @click="doSearch">检索</el-button>
            </div>
            <el-table :data="searchResults" style="margin-top: 12px" max-height="380">
              <el-table-column prop="drugName" label="药品" width="110" />
              <el-table-column prop="score" label="分数" width="80" />
              <el-table-column prop="chunkContent" label="召回片段" min-width="360" />
            </el-table>
          </el-dialog>
        </el-tab-pane>

        <el-tab-pane label="监控与审计" name="monitor">
          <el-card shadow="never">
            <div class="list-row">
              <el-date-picker
                v-model="dateRange"
                type="daterange"
                value-format="YYYY-MM-DD"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                style="width: 300px"
              />
              <el-button type="primary" @click="loadCost">查询用量</el-button>
            </div>
            <el-row :gutter="12" style="margin-top: 14px">
              <el-col :span="6">
                <el-card shadow="hover"><div class="stat">调用总次数</div><div class="num">{{ cost.totalCalls }}</div></el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="hover"><div class="stat">输入 Tokens</div><div class="num">{{ cost.totalPromptTokens }}</div></el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="hover"><div class="stat">输出 Tokens</div><div class="num">{{ cost.totalCompletionTokens }}</div></el-card>
              </el-col>
              <el-col :span="6">
                <el-card shadow="hover"><div class="stat">预估费用（元）</div><div class="num">{{ cost.totalCost }}</div></el-card>
              </el-col>
            </el-row>
            <el-table :data="cost.byApiType || []" style="margin-top: 14px" size="small">
              <el-table-column prop="apiType" label="类型" width="100" />
              <el-table-column prop="calls" label="调用次数" width="120" />
              <el-table-column prop="promptTokens" label="输入 tokens" width="140" />
              <el-table-column prop="completionTokens" label="输出 tokens" />
            </el-table>
          </el-card>

          <el-card shadow="never" style="margin-top: 12px">
            <div class="list-row">
              <el-input
                v-model="traceId"
                placeholder="按 traceId 精确查询（留空查全部）"
                clearable
                style="width: 360px"
                @keyup.enter="loadLogs"
                @clear="loadLogs"
              />
              <el-button @click="loadLogs">查询日志</el-button>
            </div>
            <el-table :data="logs" style="margin-top: 10px" size="small">
              <el-table-column prop="traceId" label="traceId" width="200" />
              <el-table-column prop="method" label="方法" width="70" />
              <el-table-column prop="path" label="路径" min-width="220" />
              <el-table-column prop="code" label="状态码" width="80" />
              <el-table-column prop="userId" label="用户" width="70" />
              <el-table-column prop="ip" label="IP" width="120" />
              <el-table-column prop="costMs" label="耗时ms" width="80" />
              <el-table-column label="时间" width="160">
                <template #default="{ row }">
                  {{ (row.createdAt || '').replace('T', ' ').slice(0, 19) }}
                </template>
              </el-table-column>
            </el-table>
            <el-pagination
              style="margin-top: 10px; justify-content: flex-end"
              layout="total, prev, pager, next"
              :total="logTotal"
              :page-size="20"
              :current-page="logPage"
              @current-change="(p) => { logPage = p; loadLogs() }"
            />
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import request from '../api'
import TopBar from '../components/TopBar.vue'

const tab = ref('rag')

const form = reactive({ drugName: '', version: '' })
const fileInput = ref(null)
const pickedFile = ref(null)
const pickedName = ref('')
const uploading = ref(false)
const docs = ref([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const size = ref(10)
const total = ref(0)

function onPickFile(e) {
  pickedFile.value = e.target.files?.[0] || null
  pickedName.value = pickedFile.value?.name || ''
}

async function uploadDoc() {
  if (!form.drugName.trim()) {
    ElMessage.warning('请填写药品名称')
    return
  }
  if (!pickedFile.value) {
    ElMessage.warning('请选择文档（pdf/txt/md）')
    return
  }
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', pickedFile.value)
    fd.append('drugName', form.drugName.trim())
    fd.append('version', form.version.trim())
    const res = await request.post('/rag/doc/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    const d = res.data
    if (d.status === 'success') ElMessage.success('入库成功')
    else ElMessage.error(`入库失败：${d.status}`)
    form.drugName = ''
    form.version = ''
    pickedFile.value = null
    pickedName.value = ''
    if (fileInput.value) fileInput.value.value = ''
    await loadDocs()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    uploading.value = false
  }
}

async function loadDocs() {
  loading.value = true
  try {
    const res = await request.get('/rag/doc/list', {
      params: { page: page.value, size: size.value, drugName: keyword.value },
    })
    docs.value = res.data.list
    total.value = res.data.total
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function toggleStatus(row, value) {
  try {
    await request.put('/rag/doc/status', {
      docId: row.docId,
      status: value ? 'enable' : 'disable',
    })
    row.enabled = value
    ElMessage.success(value ? '已启用' : '已下线')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

const searchVisible = ref(false)
const searchDrug = ref('')
const searchQuery = ref('')
const searchTopK = ref(5)
const searchResults = ref([])

function openSearch(row) {
  searchDrug.value = row.drugName
  searchQuery.value = ''
  searchResults.value = []
  searchVisible.value = true
}

async function doSearch() {
  if (!searchQuery.value.trim()) return
  try {
    const res = await request.post('/rag/search/test', {
      query: searchQuery.value.trim(),
      topK: searchTopK.value,
    })
    searchResults.value = res.data.list
    if (!searchResults.value.length) ElMessage.info('无召回片段（可能低于相关性阈值或文档已下线）')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

const dateRange = ref([])
const cost = reactive({
  totalCalls: 0,
  totalPromptTokens: 0,
  totalCompletionTokens: 0,
  totalCost: 0,
  byApiType: [],
})

async function loadCost() {
  try {
    const params = {}
    if (dateRange.value?.length === 2) {
      params.startDate = dateRange.value[0]
      params.endDate = dateRange.value[1]
    }
    const res = await request.get('/monitor/llm/cost', { params })
    Object.assign(cost, res.data)
  } catch (e) {
    ElMessage.error(e.message)
  }
}

const traceId = ref('')
const logs = ref([])
const logTotal = ref(0)
const logPage = ref(1)

async function loadLogs() {
  try {
    const res = await request.get('/monitor/log', {
      params: { traceId: traceId.value, page: logPage.value, size: 20 },
    })
    logs.value = res.data.list
    logTotal.value = res.data.total
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(() => {
  loadDocs()
  loadCost()
  loadLogs()
})
</script>

<style scoped>
.admin-layout {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.content {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}
.upload-row,
.list-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.picked {
  color: #606266;
  font-size: 13px;
}
.stat {
  font-size: 13px;
  color: #909399;
}
.num {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
  margin-top: 4px;
}
</style>
