<template>
  <header class="topbar">
    <div class="left">
      <span class="logo">多模态医疗辅助问诊系统</span>
      <el-menu mode="horizontal" :ellipsis="false" router class="menu">
        <el-menu-item index="/">问诊</el-menu-item>
        <el-menu-item v-if="auth.permissions.includes('rag:read')" index="/admin">
          知识库 / 监控
        </el-menu-item>
      </el-menu>
    </div>
    <div class="right">
      <span class="user">{{ auth.displayName }}</span>
      <el-button link type="primary" @click="doLogout">退出登录</el-button>
    </div>
  </header>
</template>

<script setup>
import { useRouter } from 'vue-router'
import request from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function doLogout() {
  try {
    await request.post('/auth/logout')
  } catch {
    /* token 可能已失效 */
  }
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<style scoped>
.topbar {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}
.left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.logo {
  font-weight: 600;
  font-size: 16px;
  color: #303133;
}
.menu {
  border-bottom: none;
}
.right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user {
  color: #606266;
  font-size: 14px;
}
</style>
