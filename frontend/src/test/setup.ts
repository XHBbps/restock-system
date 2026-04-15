import { config, enableAutoUnmount } from '@vue/test-utils'
import { afterEach } from 'vitest'

enableAutoUnmount(afterEach)

config.global.directives = {
  ...config.global.directives,
  loading: {},
}
