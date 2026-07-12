<template>
  <div class="language-switcher" ref="switcherRef">
    <button class="switcher-trigger" @click="toggleDropdown">
      {{ currentLabel }}
      <span class="caret">{{ open ? '▲' : '▼' }}</span>
    </button>
    <ul v-if="open" class="switcher-dropdown">
      <li
        v-for="loc in availableLocales"
        :key="loc.key"
        class="switcher-option"
        :class="{ active: loc.key === locale }"
        @click="switchLocale(loc.key)"
      >
        {{ loc.label }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { availableLocales } from '@/i18n/index.js'

const { locale } = useI18n()
const open = ref(false)
const switcherRef = ref(null)

const currentLabel = computed(() => {
  const found = availableLocales.find(l => l.key === locale.value)
  return found ? found.label : locale.value
})

const toggleDropdown = () => {
  open.value = !open.value
}

const switchLocale = (key) => {
  locale.value = key
  localStorage.setItem('locale', key)
  document.documentElement.lang = key
  open.value = false
}

const onClickOutside = (e) => {
  if (switcherRef.value && !switcherRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
  document.documentElement.lang = locale.value
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<style scoped>
.language-switcher {
  position: relative;
  display: inline-block;
  font-family: var(--sb-font-mono);
}

/* Glass pill trigger (for dark glass header backgrounds) */
.switcher-trigger {
  background: var(--sb-glass);
  color: var(--sb-text-secondary);
  border: 1px solid var(--sb-glass-border);
  border-radius: 999px;
  backdrop-filter: blur(var(--sb-glass-blur));
  -webkit-backdrop-filter: blur(var(--sb-glass-blur));
  padding: 4px 12px;
  font-family: var(--sb-font-mono);
  font-size: 0.8rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: border-color 0.2s, background 0.2s, color 0.2s, opacity 0.2s;
}

.switcher-trigger:hover {
  border-color: var(--sb-glass-border-strong);
  background: var(--sb-glass-strong);
  color: var(--sb-text);
}

.caret {
  font-size: 0.6rem;
  color: var(--sb-text-muted);
}

.switcher-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 6px;
  background: rgba(18, 18, 34, 0.85);
  border: 1px solid var(--sb-glass-border);
  border-radius: var(--sb-radius-sm);
  backdrop-filter: blur(var(--sb-glass-blur));
  -webkit-backdrop-filter: blur(var(--sb-glass-blur));
  list-style: none;
  padding: 4px 0;
  min-width: 100%;
  z-index: 1000;
  box-shadow: var(--sb-shadow);
  overflow: hidden;
}

.switcher-option {
  padding: 6px 12px;
  font-size: 0.8rem;
  color: var(--sb-text-secondary);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}

.switcher-option:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--sb-text);
}

.switcher-option.active {
  color: var(--sb-violet);
  font-weight: 600;
}


</style>
