<template>
  <div class="not-authorized">
    <el-empty description="暂无权限访问此页面">
      <el-button type="primary" @click="router.replace('/')">返回首页</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<style scoped>
.not-authorized {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 50vh;
}
</style>
