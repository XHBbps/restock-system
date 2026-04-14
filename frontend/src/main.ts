// 应用入口：装配 Vue + Pinia + Router + Element Plus
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import ElementPlus, { ElMessage } from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import router from './router'
import './styles/element-overrides.scss'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 全局 Vue 错误处理：防止组件错误静默失败
app.config.errorHandler = (err, _instance, info) => {
  console.error('[Vue Error]', err, info)
  ElMessage.error('操作异常，请刷新页面重试')
}

// 捕获未处理的 Promise rejection
window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled Rejection]', event.reason)
})

app.mount('#app')
