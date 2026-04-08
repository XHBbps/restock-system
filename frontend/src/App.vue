<template>
  <RouterView />
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<style lang="scss">
html,
body,
#app {
  margin: 0;
  padding: 0;
  height: 100%;
  background: $color-bg-base;
  color: $color-text-primary;
  font-family: $font-family-sans;
  font-size: $font-size-md;
}
</style>
