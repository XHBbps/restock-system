import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const width = ref(typeof window === 'undefined' ? 1024 : window.innerWidth)
let listenerCount = 0

function updateWidth(): void {
  width.value = window.innerWidth
}

export function useResponsive() {
  onMounted(() => {
    listenerCount += 1
    if (listenerCount === 1) {
      window.addEventListener('resize', updateWidth, { passive: true })
    }
    updateWidth()
  })

  onBeforeUnmount(() => {
    listenerCount = Math.max(0, listenerCount - 1)
    if (listenerCount === 0) {
      window.removeEventListener('resize', updateWidth)
    }
  })

  const isMobile = computed(() => width.value < 768)
  const isTablet = computed(() => width.value >= 768 && width.value < 1024)

  return {
    width,
    isMobile,
    isTablet,
  }
}
