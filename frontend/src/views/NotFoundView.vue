<template>
  <div class="not-found">
    <el-empty description="页面不存在">
      <el-button type="primary" @click="router.replace('/')">返回首页</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style scoped>
.not-found {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 50vh;
}
</style>
