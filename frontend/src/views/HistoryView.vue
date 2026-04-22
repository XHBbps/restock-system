<template>
  <PageSectionCard title="历史记录">
    <SuggestionTabBar base-path="/restock/history" />
    <router-view />
  </PageSectionCard>
</template>

<script setup lang="ts">
import PageSectionCard from '@/components/PageSectionCard.vue'
import SuggestionTabBar from '@/components/SuggestionTabBar.vue'
</script>
