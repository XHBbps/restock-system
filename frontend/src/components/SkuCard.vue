<template>
  <div class="sku-card">
    <img
      v-if="showImage"
      :src="imageSrc"
      :alt="name || sku"
      class="sku-image"
      @error="handleImageError"
    />
    <div v-else class="sku-image-placeholder">无图</div>
    <div class="sku-meta">
      <div class="sku-name">{{ name || sku }}</div>
      <div class="sku-code">{{ sku }}</div>
    </div>
    <el-tag v-if="blocker" type="info" size="small">无法推送</el-tag>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  sku: string
  name?: string | null
  image?: string | null
  blocker?: string | null
}>()

const imageLoadFailed = ref(false)
const imageSrc = computed(() => props.image?.trim() || '')
const showImage = computed(() => Boolean(imageSrc.value) && !imageLoadFailed.value)

watch(
  () => props.image,
  () => {
    imageLoadFailed.value = false
  }
)

function handleImageError(): void {
  imageLoadFailed.value = true
}
</script>

<style lang="scss" scoped>
.sku-card {
  display: flex;
  align-items: center;
  gap: $space-3;
}
.sku-image,
.sku-image-placeholder {
  width: 48px;
  height: 48px;
  border-radius: $radius-md;
  object-fit: cover;
  background: $color-bg-subtle;
  display: flex;
  align-items: center;
  justify-content: center;
  color: $color-text-secondary;
  font-size: $font-size-sm;
  flex-shrink: 0;
}
.sku-meta {
  flex: 1;
  min-width: 0;
}
.sku-name {
  font-weight: $font-weight-medium;
  color: $color-text-primary;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sku-code {
  color: $color-text-secondary;
  font-size: $font-size-xs;
}
</style>
