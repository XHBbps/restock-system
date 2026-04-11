<template>
  <section class="dashboard-page-header">
    <div class="dashboard-page-header__main">
      <div v-if="eyebrow" class="dashboard-page-header__eyebrow">{{ eyebrow }}</div>
      <h1 class="dashboard-page-header__title">{{ title }}</h1>
      <p v-if="description" class="dashboard-page-header__description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions || $slots.meta" class="dashboard-page-header__aside">
      <div v-if="$slots.meta" class="dashboard-page-header__meta">
        <slot name="meta" />
      </div>
      <div v-if="$slots.actions" class="dashboard-page-header__actions">
        <slot name="actions" />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
  eyebrow?: string
}>()
</script>

<style lang="scss" scoped>
.dashboard-page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: $space-4;
  padding: $space-6;
  border: 1px solid $color-border-default;
  border-radius: $radius-xl;
  background: $color-bg-card;
  box-shadow: $shadow-card;
}

.dashboard-page-header__main {
  min-width: 0;
}

.dashboard-page-header__eyebrow {
  color: $color-text-secondary;
  font-size: $font-size-xs;
  font-weight: $font-weight-semibold;
  letter-spacing: $tracking-wider;
  text-transform: uppercase;
}

.dashboard-page-header__title {
  margin: $space-2 0 0;
  font-size: $font-size-4xl;
  line-height: $line-height-tight;
  letter-spacing: $tracking-tight;
}

.dashboard-page-header__description {
  margin: $space-2 0 0;
  max-width: 780px;
  color: $color-text-secondary;
  line-height: $line-height-relaxed;
}

.dashboard-page-header__aside {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: $space-3;
}

.dashboard-page-header__meta,
.dashboard-page-header__actions {
  display: flex;
  gap: $space-3;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .dashboard-page-header {
    flex-direction: column;
  }

  .dashboard-page-header__aside {
    align-items: flex-start;
  }

  .dashboard-page-header__meta,
  .dashboard-page-header__actions {
    justify-content: flex-start;
  }
}
</style>
