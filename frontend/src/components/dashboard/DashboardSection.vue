<template>
  <section class="dashboard-section">
    <div v-if="title || description || $slots.actions" class="dashboard-section__header">
      <div>
        <div v-if="title" class="dashboard-section__title">{{ title }}</div>
        <div v-if="description" class="dashboard-section__description">{{ description }}</div>
      </div>
      <div v-if="$slots.actions" class="dashboard-section__actions">
        <slot name="actions" />
      </div>
    </div>
    <slot />
  </section>
</template>

<script setup lang="ts">
defineProps<{
  title?: string
  description?: string
}>()
</script>

<style lang="scss" scoped>
.dashboard-section {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.dashboard-section__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
}

.dashboard-section__title {
  font-size: $font-size-2xl;
  font-weight: $font-weight-semibold;
  letter-spacing: $tracking-tight;
}

.dashboard-section__description {
  margin-top: 4px;
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.dashboard-section__actions {
  display: flex;
  gap: $space-3;
  align-items: center;
  flex-wrap: wrap;
}

@media (max-width: 900px) {
  .dashboard-section__header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
