<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="login-title">赛狐补货计算工具</h1>
      <p class="login-subtitle">登录以继续</p>

      <el-form @submit.prevent="handleLogin">
        <el-input
          v-model="password"
          type="password"
          placeholder="登录密码"
          size="large"
          :disabled="loading"
          @keyup.enter="handleLogin"
        />
        <el-button
          type="primary"
          size="large"
          class="login-btn"
          :loading="loading"
          @click="handleLogin"
        >
          登录
        </el-button>
      </el-form>

      <p v-if="errorMsg" class="login-error">{{ errorMsg }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { login } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

async function handleLogin(): Promise<void> {
  if (!password.value) {
    errorMsg.value = '请输入密码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const resp = await login(password.value)
    auth.setToken(resp.access_token)
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/'
    router.replace(redirect)
  } catch (err: unknown) {
    const e = err as { response?: { status?: number; data?: { message?: string } } }
    if (e.response?.status === 423) {
      errorMsg.value = '账号已锁定，请稍后再试'
    } else {
      errorMsg.value = e.response?.data?.message || '登录失败'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: $color-bg-base;
}

.login-card {
  background: $color-bg-card;
  border-radius: $radius-xl;
  box-shadow: $shadow-card;
  padding: $space-12 $space-10;
  width: 380px;
}

.login-title {
  margin: 0 0 $space-2 0;
  font-size: $font-size-2xl;
  color: $color-text-primary;
  font-weight: $font-weight-semibold;
}

.login-subtitle {
  margin: 0 0 $space-8 0;
  color: $color-text-secondary;
  font-size: $font-size-md;
}

.login-btn {
  width: 100%;
  margin-top: $space-5;
}

.login-error {
  margin-top: $space-4;
  color: $color-danger;
  font-size: $font-size-sm;
  text-align: center;
}
</style>
