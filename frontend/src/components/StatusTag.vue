<template>
  <el-tag :type="meta.tagType" :size="size">
    {{ meta.label }}
  </el-tag>
</template>

<script setup lang="ts">
import type { TagType } from '@/utils/element'

defineProps<{
  meta: {
    label: string
    tagType: TagType
  }
  size?: 'large' | 'default' | 'small'
}>()
</script>
