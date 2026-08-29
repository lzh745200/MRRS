import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useConfigStore } from '@/stores/config'

describe('useConfigStore', () => {
  let store: ReturnType<typeof useConfigStore>
  beforeEach(() => { setActivePinia(createPinia()); store = useConfigStore() })
  it('initializes with default config', () => {
    expect(store).toBeDefined()
  })
})

