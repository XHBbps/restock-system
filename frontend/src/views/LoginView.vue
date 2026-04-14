<template>
  <div class="login-page">
    <div class="grid-bg" />
    <div class="grid-hover">
      <div v-for="n in GRID_CELL_COUNT" :key="n" class="cell" />
    </div>

    <div class="login-card">
      <div class="card-header">
        <div class="brand-mark">R</div>
        <h1 class="card-title">登录 Restock</h1>
      </div>

      <form class="card-form" @submit.prevent="handleLogin">
        <div class="form-field">
          <label class="field-label" for="username">用户名</label>
          <el-input
            id="username"
            v-model="username"
            placeholder="请输入用户名"
            size="large"
            :disabled="loading"
            @keyup.enter="handleLogin"
          />
        </div>

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
          登录
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
import { useAuthStore, _mapUserInfo } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

// 80 列 × 35 行 = 2800 格，覆盖 2560px 宽度以下的桌面分辨率
// 单元格是 32×32，使用 CSS Grid auto-fill 按视口宽度自动换行
const GRID_CELL_COUNT = 2800

const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')
let lockedCountdownTimer: number | null = null

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

function clearLockedCountdown(): void {
  if (lockedCountdownTimer !== null) {
    window.clearInterval(lockedCountdownTimer)
    lockedCountdownTimer = null
  }
}

function startLockedCountdown(lockedUntilIso: string): void {
  clearLockedCountdown()
  const lockedUntilMs = new Date(lockedUntilIso).getTime()
  if (Number.isNaN(lockedUntilMs)) {
    errorMsg.value = '账号已锁定，请稍后再试'
    return
  }
  const update = (): void => {
    const remainingMs = lockedUntilMs - Date.now()
    if (remainingMs <= 0) {
      clearLockedCountdown()
      errorMsg.value = ''
      return
    }
    const totalSec = Math.ceil(remainingMs / 1000)
    const min = Math.floor(totalSec / 60)
    const sec = totalSec % 60
    const remaining = min > 0 ? `${min} 分 ${sec} 秒` : `${sec} 秒`
    errorMsg.value = `账号已锁定，剩余 ${remaining}`
  }
  update()
  lockedCountdownTimer = window.setInterval(update, 1000)
}

onUnmounted(() => {
  clearLockedCountdown()
})

async function handleLogin(): Promise<void> {
  if (!username.value || !password.value) {
    errorMsg.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  clearLockedCountdown()
  try {
    const resp = await login(username.value, password.value)
    auth.setAuth(resp.access_token, _mapUserInfo(resp.user))
    ElMessage.success('登录成功')
    const raw = (route.query.redirect as string) || '/'
    const redirect = raw.startsWith('/') && !raw.startsWith('//') ? raw : '/'
    router.replace(redirect)
  } catch (err: unknown) {
    const e = err as {
      response?: {
        status?: number
        data?: { message?: string; detail?: { locked_until?: string } }
      }
    }
    if (e.response?.status === 423) {
      const lockedUntil = e.response?.data?.detail?.locked_until
      if (lockedUntil) {
        startLockedCountdown(lockedUntil)
      } else {
        errorMsg.value = '账号已锁定，请稍后再试'
      }
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

// 交互层：透明 DOM 格子，hover 时填充浅灰
// 叠加在 .grid-bg 之上，不干扰网格线本身
.grid-hover {
  position: absolute;
  inset: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, 32px);
  grid-auto-rows: 32px;
  overflow: hidden;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%);
  -webkit-mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%);

  .cell {
    // 进入 300ms / 离开 500ms（离开略慢有"余温"感）
    transition: background-color 500ms ease;

    &:hover {
      background-color: $color-border-default;
      transition-duration: 300ms;
    }
  }
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
