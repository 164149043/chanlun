<template>
  <button
    :class="['doodle-btn', variant]"
    :disabled="disabled"
    @click="$emit('click')"
  >
    <span class="doodle-content">
      <span class="doodle-icon">{{ icon }}</span>
      <span class="doodle-text"><slot /></span>
    </span>
  </button>
</template>

<script setup lang="ts">
const props = defineProps<{
  variant?: 'structured' | 'table';
  disabled?: boolean;
}>();

defineEmits<{
  click: [];
}>();

const variantConfig = {
  structured: {
    icon: '📊',
    borderClass: 'doodle-green'
  },
  table: {
    icon: '📋',
    borderClass: 'doodle-blue'
  }
};

const config = variantConfig[props.variant || 'structured'];
const icon = config.icon;
</script>

<style scoped>
/* 涂鸦风格按钮 - 马克笔牛皮纸效果 */
.doodle-btn {
  font-family: 'Patrick Hand', 'Caveat', cursive;
  font-size: 16px;
  font-weight: 400;
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 18px;
  background: #F9F3E3;
  border: 3px solid #2C2C2C;
  /* 不规则边框 - 手绘效果 */
  border-radius: 255px 15px 225px 15px / 15px 225px 15px 255px;
  /* 铅笔/马克笔阴影效果 */
  box-shadow:
    2px 2px 0 #2C2C2C,
    4px 4px 0 rgba(44, 44, 44, 0.3),
    0 1px 2px rgba(0, 0, 0, 0.1) inset;
  cursor: pointer;
  transform: rotate(-0.5deg);
  transition: all 0.15s ease-out;
  color: #2C2C2C;
  letter-spacing: 0.5px;
}

/* 纸张纹理效果 */
.doodle-btn::before {
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

.doodle-content {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 6px;
}

.doodle-icon {
  font-size: 18px;
  filter: drop-shadow(1px 1px 0 rgba(44, 44, 44, 0.2));
}

.doodle-text {
  text-shadow: 1px 1px 0 rgba(255, 255, 255, 0.5);
}

/* 结构化按钮 - 绿色马克笔风格 */
.doodle-btn.structured {
  border-color: #2E7D32;
  box-shadow:
    2px 2px 0 #2E7D32,
    4px 4px 0 rgba(46, 125, 50, 0.25);
  color: #1B5E20;
}

.doodle-btn.structured::after {
  content: '';
  position: absolute;
  top: -2px;
  left: -2px;
  right: -2px;
  bottom: -2px;
  border: 2px dashed rgba(46, 125, 50, 0.3);
  border-radius: 260px 20px 235px 20px / 20px 235px 20px 260px;
  pointer-events: none;
}

/* 表格按钮 - 蓝色马克笔风格 */
.doodle-btn.table {
  border-color: #1565C0;
  box-shadow:
    2px 2px 0 #1565C0,
    4px 4px 0 rgba(21, 101, 192, 0.25);
  color: #0D47A1;
}

.doodle-btn.table::after {
  content: '';
  position: absolute;
  top: -2px;
  left: -2px;
  right: -2px;
  bottom: -2px;
  border: 2px dashed rgba(21, 101, 192, 0.3);
  border-radius: 255px 18px 230px 18px / 18px 230px 18px 255px;
  pointer-events: none;
}

/* 悬停效果 - 涂鸦风格的轻微位移 */
.doodle-btn:hover:not(:disabled) {
  transform: rotate(-1deg) translateY(-3px);
  box-shadow:
    3px 3px 0 #2C2C2C,
    7px 7px 0 rgba(44, 44, 44, 0.2),
    0 2px 4px rgba(0, 0, 0, 0.15) inset;
}

.doodle-btn.structured:hover:not(:disabled) {
  box-shadow:
    3px 3px 0 #2E7D32,
    7px 7px 0 rgba(46, 125, 50, 0.2);
}

.doodle-btn.table:hover:not(:disabled) {
  box-shadow:
    3px 3px 0 #1565C0,
    7px 7px 0 rgba(21, 101, 192, 0.2);
}

/* 点击效果 */
.doodle-btn:active:not(:disabled) {
  transform: rotate(0deg) translateY(-1px);
  box-shadow:
    1px 1px 0 #2C2C2C,
    2px 2px 0 rgba(44, 44, 44, 0.3);
}

.doodle-btn.structured:active:not(:disabled) {
  box-shadow:
    1px 1px 0 #2E7D32,
    2px 2px 0 rgba(46, 125, 50, 0.3);
}

.doodle-btn.table:active:not(:disabled) {
  box-shadow:
    1px 1px 0 #1565C0,
    2px 2px 0 rgba(21, 101, 192, 0.3);
}

/* 禁用状态 */
.doodle-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: rotate(-0.3deg);
  filter: grayscale(30%);
}

/* 每个按钮略微不同的旋转角度 - 更自然的手绘感 */
.doodle-btn:nth-child(3n+1) {
  transform: rotate(-0.8deg);
}

.doodle-btn:nth-child(3n+2) {
  transform: rotate(0.3deg);
}

.doodle-btn:nth-child(3n+3) {
  transform: rotate(-0.2deg);
}
</style>
