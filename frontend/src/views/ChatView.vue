<template>
  <div class="chat-layout">
    <TopBar />
    <div class="body">
      <aside class="session-side">
        <el-button type="primary" class="new-btn" @click="newSession">+ 新建问诊</el-button>
        <div class="session-list">
          <div
            v-for="s in sessions"
            :key="s.sessionId"
            class="session-item"
            :class="{ active: s.sessionId === currentId }"
            @click="openSession(s.sessionId)"
          >
            <div class="summary">{{ s.summary || '未命名会话' }}</div>
            <div class="time">{{ (s.updatedAt || '').replace('T', ' ').slice(0, 16) }}</div>
          </div>
          <el-empty v-if="!sessions.length" description="暂无会话" :image-size="60" />
        </div>
      </aside>

      <main class="chat-main">
        <div ref="msgBox" class="messages">
          <div
            v-for="(m, i) in messages"
            :key="i"
            class="msg"
            :class="m.role === 'user' ? 'mine' : 'theirs'"
          >
            <div class="bubble">
              <div class="content" style="white-space: pre-wrap">{{ m.content }}</div>
              <el-collapse v-if="m.referenceDocs?.length" class="refs">
                <el-collapse-item title="参考药品说明书片段">
                  <div v-for="(d, j) in m.referenceDocs" :key="j" class="ref-item">
                    <div class="ref-title">
                      《{{ d.drugName }}》
                      <el-tag v-if="d.score != null" size="small" type="info">
                        相关度 {{ d.score }}
                      </el-tag>
                    </div>
                    <div class="ref-text">{{ d.chunkContent }}</div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>
          </div>
          <div v-if="!messages.length" class="empty-hint">
            描述你的症状或用药问题，可附图片（检验报告等），系统将检索药品说明书作科普解答。
          </div>
        </div>

        <div class="disclaimer">
          本内容仅为药品科普参考，不能替代执业医师诊断，不能作为处方依据。
        </div>

        <div class="input-area">
          <div class="img-chips">
            <div v-for="(f, i) in imageList" :key="f.fileId" class="chip">
              <img :src="f.url" alt="" />
              <span class="del" @click="imageList.splice(i, 1)">×</span>
            </div>
          </div>
          <textarea
            v-model="input"
            class="input-box"
            rows="3"
            placeholder="请输入症状描述 / 用药疑问，Enter 发送，Shift+Enter 换行"
            @keydown.enter.exact.prevent="send"
          />
          <div class="actions">
            <el-upload
              :show-file-list="false"
              :auto-upload="false"
              accept="image/jpeg,image/png,image/webp"
              :on-change="onPickImage"
            >
              <el-button :icon="Picture" :disabled="sending">图片</el-button>
            </el-upload>
            <el-button
              type="primary"
              :loading="sending"
              :disabled="!input.trim() && !imageList.length"
              @click="send"
            >
              发 送
            </el-button>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { Picture } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { nextTick, onMounted, ref } from 'vue'
import request from '../api'
import { streamChat } from '../api/sse'
import TopBar from '../components/TopBar.vue'

const sessions = ref([])
const currentId = ref('')
const messages = ref([])
const input = ref('')
const imageList = ref([])
const sending = ref(false)
const msgBox = ref(null)

async function loadSessions() {
  try {
    const res = await request.get('/chat/session/list', { params: { size: 50 } })
    sessions.value = res.data.list
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function scrollBottom() {
  await nextTick()
  if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight
}

async function openSession(id) {
  currentId.value = id
  try {
    const res = await request.get(`/chat/session/${id}`)
    messages.value = res.data.messages
    scrollBottom()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function newSession() {
  currentId.value = ''
  messages.value = []
  imageList.value = []
  input.value = ''
}

async function onPickImage(file) {
  const raw = file.raw
  if (!raw) return
  if (raw.size > 10 * 1024 * 1024) {
    ElMessage.warning('图片上限 10MB')
    return
  }
  const form = new FormData()
  form.append('file', raw)
  try {
    const res = await request.post('/file/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    imageList.value.push({ fileId: res.data.fileId, url: res.data.url })
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function send() {
  const text = input.value.trim()
  if ((!text && !imageList.value.length) || sending.value) return
  sending.value = true
  const body = { userDesc: text, imageList: imageList.value.map((f) => f.fileId) }
  messages.value.push({ role: 'user', content: text || '[图片]', referenceDocs: [] })
  input.value = ''
  imageList.value = []
  scrollBottom()

  try {
    if (!currentId.value) {
      const res = await request.post('/chat/session/create', body)
      currentId.value = res.data.sessionId
      messages.value.push({
        role: 'assistant',
        content: res.data.answer,
        referenceDocs: res.data.referenceDocs || [],
      })
      await loadSessions()
    } else {
      const bubble = { role: 'assistant', content: '', referenceDocs: [], streaming: true }
      messages.value.push(bubble)
      let acc = ''
      await streamChat(currentId.value, body, {
        delta: (d) => {
          acc += d.content
          bubble.content = acc
          scrollBottom()
        },
        done: (d) => {
          bubble.streaming = false
          bubble.referenceDocs = d.referenceDocs || []
        },
        error: (d) => {
          bubble.streaming = false
          if (!bubble.content) bubble.content = `⚠️ ${d.msg}`
          ElMessage.error(d.msg)
        },
      })
      if (!bubble.content) messages.value.pop()
      const idx = sessions.value.findIndex((s) => s.sessionId === currentId.value)
      if (idx >= 0) {
        const [item] = sessions.value.splice(idx, 1)
        sessions.value.unshift(item)
      }
    }
    scrollBottom()
  } catch (e) {
    ElMessage.error(e.message)
    messages.value.pop()
  } finally {
    sending.value = false
  }
}

onMounted(loadSessions)
</script>

<style scoped>
.chat-layout {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.session-side {
  width: 260px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  padding: 12px;
}
.new-btn {
  width: 100%;
  margin-bottom: 10px;
}
.session-list {
  flex: 1;
  overflow-y: auto;
}
.session-item {
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 6px;
}
.session-item:hover {
  background: #f5f7fa;
}
.session-item.active {
  background: #ecf5ff;
}
.summary {
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.time {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.msg {
  display: flex;
  margin-bottom: 14px;
}
.msg.mine {
  justify-content: flex-end;
}
.bubble {
  max-width: 72%;
  padding: 10px 14px;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.mine .bubble {
  background: #409eff;
  color: #fff;
}
.refs {
  margin-top: 8px;
  border: none;
}
.ref-item {
  padding: 6px 0;
  border-bottom: 1px dashed #ebeef5;
}
.ref-item:last-child {
  border-bottom: none;
}
.ref-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  display: flex;
  gap: 6px;
  align-items: center;
}
.ref-text {
  font-size: 12px;
  color: #606266;
  margin-top: 4px;
}
.empty-hint {
  text-align: center;
  color: #909399;
  margin-top: 80px;
  font-size: 14px;
}
.disclaimer {
  text-align: center;
  font-size: 12px;
  color: #e6a23c;
  background: #fdf6ec;
  padding: 6px;
}
.input-area {
  background: #fff;
  border-top: 1px solid #e4e7ed;
  padding: 10px 16px;
}
.img-chips {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
}
.img-chips:empty {
  display: none;
}
.chip {
  position: relative;
}
.chip img {
  height: 44px;
  width: 44px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
}
.chip .del {
  position: absolute;
  top: -6px;
  right: -6px;
  background: #909399;
  color: #fff;
  border-radius: 50%;
  width: 16px;
  height: 16px;
  font-size: 12px;
  line-height: 16px;
  text-align: center;
  cursor: pointer;
}
.input-box {
  width: 100%;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  padding: 8px;
  resize: none;
  font-size: 14px;
  font-family: inherit;
  outline: none;
}
.input-box:focus {
  border-color: #409eff;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}
</style>
