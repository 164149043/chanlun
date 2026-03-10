<template>
  <button
    v-if="hasResult"
    :class="['doodle-result-btn', { 'has-new': hasNewResult }]"
    @click="$emit('click')"
  >
    <span class="btn-icon">📋</span>
    <span class="btn-text">查看结果</span>
    <span v-if="hasNewResult" class="new-indicator">!</span>
  </button>
</template>

<script setup lang="ts">
defineProps<{
  hasResult: boolean;
  hasNewResult?: boolean;
}>();

defineEmits<{
  click: [];
}>();
</script>

<style scoped>
/* 涂鸦风格结果按钮 */
.doodle-result-btn {
  font-family: 'Patrick Hand', 'Caveat', cursive;
  font-size: 16px;
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 18px;
  background: #FFF8E1;
  border: 3px solid #F57C00;
  /* 不规则边框 */
  border-radius: 15px 5px 12px 8px / 8px 12px 5px 15px;
  /* 马克笔阴影 */
  box-shadow:
    2px 2px 0 #F57C00,
    4px 4px 0 rgba(245, 124, 0, 0.25);
  cursor: pointer;
  transform: rotate(0.5deg);
  transition: all 0.15s ease-out;
  color: #E65100;
}

/* 纸张纹理 */
.doodle-result-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image:
    repeating-linear-gradient(
      0deg,
      transparent,
      transparent 1px,
      rgba(0, 0, 0, 0.02) 1px,
      rgba(0, 0, 0, 0.02) 2px
    );
  pointer-events: none;
  border-radius: inherit;
}

.doodle-result-btn .btn-icon {
  font-size: 18px;
  filter: drop-shadow(1px 1px 0 rgba(255, 255, 255, 0.3));
}

.doodle-result-btn .btn-text {
  text-shadow: 1px 1px 0 rgba(255, 255, 255, 0.5);
}

/* 新结果指示器 - 涂鸦风格 */
.new-indicator {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 22px;
  height: 22px;
  background: #F44336;
  color: #FFF;
  border: 2px solid #2C2C2C;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: bold;
  box-shadow:
    1px 1px 0 #2C2C2C,
    2px 2px 0 rgba(244, 67, 54, 0.3);
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.1);
  }
}

/* 新结果时按钮脉动动画 */
.doodle-result-btn.has-new {
  animation: bounce-in 0.5s ease-out;
}

@keyframes bounce-in {
  0% {
    transform: rotate(0.5deg) scale(0.8);
    opacity: 0;
  }
  50% {
    transform: rotate(-0.3deg) scale(1.05);
  }
  100% {
    transform: rotate(0.5deg) scale(1);
    opacity: 1;
  }
}

/* 悬停效果 */
.doodle-result-btn:hover {
  transform: rotate(-0.5deg) translateY(-3px);
  box-shadow:
    3px 3px 0 #F57C00,
    6px 6px 0 rgba(245, 124, 0, 0.2);
}

/* 点击效果 */
.doodle-result-btn:active {
  transform: translateY(-1px);
  box-shadow:
    1px 1px 0 #F57C00,
    2px 2px 0 rgba(245, 124, 0, 0.3);
}
</style>
