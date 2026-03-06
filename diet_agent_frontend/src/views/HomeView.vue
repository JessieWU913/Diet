<template>
  <div class="home-view">
    <ChatBox />
  </div>
</template>

<script setup>
import ChatBox from '../components/ChatBox.vue'
</script>

<style scoped>
.home-view {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
  box-sizing: border-box;
}
</style>
