<template>
  <button
    :class="['doodle-legend-btn', { active }]"
    :title="label"
    :style="active ? { '--doodle-color': color } : {}"
    @click="$emit('click')"
  >
    <span class="doodle-legend-label">{{ label }}</span>
  </button>
</template>

<script setup lang="ts">
const props = defineProps<{
  label: string;
  color: string;
  active?: boolean;
}>();

defineEmits<{
  click: [];
}>();
</script>

<style scoped>
/* 涂鸦风格图例按钮 */
.doodle-legend-btn {
  font-family: 'Patrick Hand', 'Caveat', cursive;
  font-size: 14px;
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 14px;
  background: #F9F3E3;
  border: 2px solid #787B86;
  /* 不规则边框 */
  border-radius: 12px 3px 8px 5px / 5px 12px 3px 8px;
  box-shadow:
    1px 1px 0 #787B86,
    2px 2px 0 rgba(120, 123, 134, 0.2);
  cursor: pointer;
  transform: rotate(0.3deg);
  transition: all 0.15s ease-out;
  color: #555;
}

/* 纸张纹理 */
.doodle-legend-btn::before {
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
      rgba(0, 0, 0, 0.015) 1px,
      rgba(0, 0, 0, 0.015) 2px
    );
  pointer-events: none;
  border-radius: inherit;
}

.doodle-legend-label {
  position: relative;
  z-index: 1;
  text-shadow: 1px 1px 0 rgba(255, 255, 255, 0.5);
}

/* 悬停效果 */
.doodle-legend-btn:hover {
  transform: rotate(-0.5deg) translateY(-2px);
  box-shadow:
    2px 2px 0 #787B86,
    4px 4px 0 rgba(120, 123, 134, 0.15);
}

/* 激活状态 - 使用图层颜色 */
.doodle-legend-btn.active {
  font-weight: 700;
  transform: rotate(-0.3deg);
  background: #FFF8E1;
  border-color: var(--doodle-color, #424242);
  box-shadow:
    2px 2px 0 var(--doodle-color, #424242),
    3px 3px 0 color-mix(in srgb, var(--doodle-color, #424242) 25%, transparent);
  color: var(--doodle-color, #212121);
}

/* 激活状态装饰 - 涂鸦风格的对勾 */
.doodle-legend-btn.active::after {
  content: '✓';
  position: absolute;
  top: -8px;
  right: -6px;
  font-size: 14px;
  color: currentColor;
  background: #FFF;
  border-radius: 50%;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid currentColor;
  box-shadow: 1px 1px 0 rgba(0, 0, 0, 0.1);
}

/* 点击效果 */
.doodle-legend-btn:active {
  transform: translateY(0);
  box-shadow:
    1px 1px 0 currentColor,
    1px 1px 0 rgba(0, 0, 0, 0.2);
}

/* 每个按钮略有不同的旋转 - 更自然 */
.doodle-legend-btn:nth-child(5n+1) {
  transform: rotate(0.5deg);
}

.doodle-legend-btn:nth-child(5n+2) {
  transform: rotate(-0.7deg);
}

.doodle-legend-btn:nth-child(5n+3) {
  transform: rotate(0.2deg);
}

.doodle-legend-btn:nth-child(5n+4) {
  transform: rotate(-0.3deg);
}

.doodle-legend-btn:nth-child(5n+5) {
  transform: rotate(0.6deg);
}

.doodle-legend-btn:nth-child(5n+1).active {
  transform: rotate(-0.2deg);
}

.doodle-legend-btn:nth-child(5n+2).active {
  transform: rotate(0.4deg);
}

.doodle-legend-btn:nth-child(5n+3).active {
  transform: rotate(-0.5deg);
}

.doodle-legend-btn:nth-child(5n+4).active {
  transform: rotate(0.3deg);
}

.doodle-legend-btn:nth-child(5n+5).active {
  transform: rotate(-0.4deg);
}
</style>
