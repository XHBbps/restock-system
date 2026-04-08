<template>
  <el-card shadow="never">
    <h2>{{ title }}</h2>
    <p style="color: #8b94a3">该页面将在后续 Phase 实现。</p>
  </el-card>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
const title = (route.meta.title as string) || '未命名页面'
</script>
