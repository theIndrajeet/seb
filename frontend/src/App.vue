<template>
  <router-view />
</template>

<script setup>
// 使用 Vue Router 来管理页面
</script>

<style>
/* 全局样式重置 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: var(--sb-font-body);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--sb-text);
  min-height: 100vh;
}

h1, h2, h3, h4, h5, h6 {
  font-family: var(--sb-font-display);
}

button {
  font-family: inherit;
}
</style>
