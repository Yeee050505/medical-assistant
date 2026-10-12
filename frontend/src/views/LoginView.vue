<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2 class="title">多模态医疗辅助问诊系统</h2>
      <p class="sub">RAG 药品知识库 · 仅供科普参考，不能替代医师诊断</p>
      <el-form @submit.prevent="doLogin">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            show-password
            placeholder="密码"
            size="large"
            @keyup.enter="doLogin"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          style="width: 100%"
          :loading="loading"
          @click="doLogin"
        >
          登 录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '../api'
import { useAuthStore } from '../stores/auth'

const username = ref('admin')
const password = ref('')
const loading = ref(false)
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

async function doLogin() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await request.post('/auth/login', {
      username: username.value,
      password: password.value,
    })
    auth.setToken(res.data.token)
    const info = await request.get('/auth/info')
    auth.setUser(info.data)
    router.push(typeof route.query.redirect === 'string' ? route.query.redirect : '/')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f3ff 0%, #f5f7fa 100%);
}
.login-card {
  width: 380px;
  padding: 12px 8px;
}
.title {
  text-align: center;
  margin: 8px 0 4px;
  font-size: 20px;
}
.sub {
  text-align: center;
  color: #909399;
  font-size: 13px;
  margin: 0 0 20px;
}
</style>
