<template>
  <div class="login-page">
    <div class="grid-bg" />

    <div class="login-card">
      <div class="card-header">
        <div class="brand-mark">R</div>
        <h1 class="card-title">Sign in to Restock</h1>
      </div>

      <form class="card-form" @submit.prevent="handleLogin">
        <div class="form-field">
          <label class="field-label" for="password">密码</label>
          <el-input
            id="password"
            v-model="password"
            type="password"
            placeholder="••••••••"
            size="large"
            :disabled="loading"
            @keyup.enter="handleLogin"
          />
        </div>

        <el-button
          type="primary"
          size="large"
          class="submit-btn"
          :loading="loading"
          @click="handleLogin"
        >
          Sign in
        </el-button>

        <div v-if="errorMsg" class="error-banner">
          <div class="error-dot" />
          <span>{{ errorMsg }}</span>
        </div>
      </form>

      <div class="card-footer">
        <span class="footer-text">Restock System</span>
        <span class="footer-dot">·</span>
        <span class="footer-version">v0.1.0</span>
      </div>
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
    const raw = (route.query.redirect as string) || '/'
    const redirect = raw.startsWith('/') && !raw.startsWith('//') ? raw : '/'
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
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: $color-bg-base;
  overflow: hidden;
}

// shadcn 标志性网格纹理背景
.grid-bg {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, $color-border-subtle 1px, transparent 1px),
    linear-gradient(to bottom, $color-border-subtle 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%);
  -webkit-mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%);
  pointer-events: none;
}

.login-card {
  position: relative;
  z-index: 1;
  width: 400px;
  background: $color-bg-card;
  border: 1px solid $color-border-default;
  border-radius: $radius-xl;
  box-shadow: $shadow-card;
  padding: 0;
  overflow: hidden;
}

.card-header {
  padding: $space-6 $space-6 $space-4;
  text-align: center;
  border-bottom: 1px solid $color-border-subtle;

  .brand-mark {
    width: 44px;
    height: 44px;
    border-radius: $radius-md;
    background: $color-brand-primary;
    color: $color-brand-primary-fg;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-family: $font-family-mono;
    font-weight: $font-weight-bold;
    font-size: $font-size-xl;
    letter-spacing: -0.05em;
    margin-bottom: $space-4;
  }

  .card-title {
    margin: 0;
    font-size: $font-size-2xl;
    font-weight: $font-weight-semibold;
    color: $color-text-primary;
    letter-spacing: $tracking-tight;
    line-height: 1.2;
  }
}

.card-form {
  padding: $space-6;
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: $space-2;
}

// 覆盖浏览器 autofill 的蓝色背景（Chrome/Edge/Safari）
// 用 inset box-shadow 遮盖 #E8F0FE 默认底色；transition 9999s 防止闪烁
.card-form :deep(input:-webkit-autofill),
.card-form :deep(input:-webkit-autofill:hover),
.card-form :deep(input:-webkit-autofill:focus),
.card-form :deep(input:-webkit-autofill:active) {
  -webkit-box-shadow: 0 0 0 1000px $color-bg-card inset !important;
  -webkit-text-fill-color: $color-text-primary !important;
  transition: background-color 9999s ease-in-out 0s;
  caret-color: $color-text-primary;
}

.field-label {
  font-size: $font-size-sm;
  font-weight: $font-weight-medium;
  color: $color-text-primary;
}

.submit-btn {
  width: 100%;
  margin-top: $space-1;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: $space-2;
  padding: $space-3 $space-4;
  background: $color-danger-soft;
  border: 1px solid $color-danger-border;
  border-radius: $radius-md;
  color: $color-danger;
  font-size: $font-size-xs;
  font-weight: $font-weight-medium;

  .error-dot {
    width: 6px;
    height: 6px;
    border-radius: $radius-pill;
    background: $color-danger;
    flex-shrink: 0;
    animation: pulse 2s infinite;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.card-footer {
  padding: $space-4 $space-6;
  border-top: 1px solid $color-border-subtle;
  background: $color-bg-subtle;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: $space-2;
  font-size: $font-size-xs;
  color: $color-text-secondary;

  .footer-text {
    font-weight: $font-weight-medium;
  }
  .footer-dot {
    color: $color-text-disabled;
  }
  .footer-version {
    font-family: $font-family-mono;
    color: $color-text-disabled;
  }
}
</style>
