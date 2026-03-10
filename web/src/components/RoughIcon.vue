<template>
  <canvas ref="canvasEl" :width="size" :height="size"></canvas>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import rough from 'roughjs/bin/rough.js';

const props = withDefaults(
  defineProps<{
    type: 'bi' | 'zs' | 'fenxing-ding' | 'fenxing-di' | 'ai' | '15m' | '1h' | '4h' | '1d';
    color?: string;
    size?: number;
  }>(),
  {
    color: '',
    size: 40
  }
);

const canvasEl = ref<HTMLCanvasElement | null>(null);

// 默认颜色
const defaultColors: Record<string, string> = {
  'bi': '#2962FF',           // 蓝色 - 笔
  'zs': '#787B86',           // 灰色 - 中枢
  'fenxing-ding': '#D32F2F',  // 红色 - 顶分型
  'fenxing-di': '#388E3C',    // 绿色 - 底分型
  'ai': '#2962FF',           // 蓝色 - AI
  '15m': '#787B86',
  '1h': '#787B86',
  '4h': '#787B86',
  '1d': '#787B86'
};

function drawIcon() {
  const canvas = canvasEl.value;
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const color = props.color || defaultColors[props.type] || '#787B86';
  const s = props.size;

  // 清空画布
  ctx.clearRect(0, 0, s, s);

  switch (props.type) {
    case 'bi': {
      // 笔 - 折线
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.moveTo(s * 0.15, s * 0.85);
      ctx.lineTo(s * 0.5, s * 0.35);
      ctx.lineTo(s * 0.85, s * 0.6);
      ctx.stroke();
      break;
    }
    case 'zs': {
      // 中枢 - 手绘矩形框
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      const x = s * 0.15, y = s * 0.25;
      const w = s * 0.7, h = s * 0.5;
      ctx.strokeRect(x, y, w, h);
      break;
    }
    case 'fenxing-ding': {
      // 顶分型 - 下三角
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.moveTo(s * 0.5, s * 0.1);
      ctx.lineTo(s * 0.15, s * 0.85);
      ctx.lineTo(s * 0.85, s * 0.85);
      ctx.fill();
      break;
    }
    case 'fenxing-di': {
      // 底分型 - 上三角
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.moveTo(s * 0.5, s * 0.85);
      ctx.lineTo(s * 0.15, s * 0.15);
      ctx.lineTo(s * 0.85, s * 0.15);
      ctx.fill();
      break;
    }
    case 'ai': {
      // AI 分析 - 大脑形状
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.beginPath();
      // 大脑轮廓
      const cx = s * 0.5, cy = s * 0.35;
      const r = s * 0.35;
      ctx.arc(cx, cy, r, Math.PI, Math.PI * 1.7);
      // 闪电符号
      ctx.beginPath();
      ctx.moveTo(s * 0.55, s * 0.25);
      ctx.lineTo(s * 0.45, s * 0.45);
      ctx.lineTo(s * 0.5, s * 0.55);
      ctx.lineTo(s * 0.45, s * 0.7);
      ctx.stroke();
      break;
    }
    case '15m':
    case '1h':
    case '4h':
    case '1d': {
      // 周期标签 - 简化文字
      const text = props.type.toUpperCase();
      ctx.font = `${s * 0.35}px monospace`;
      ctx.fillStyle = color;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(text, s / 2, s / 2);
      break;
    }
  }
}

onMounted(() => {
  drawIcon();
});

// 当 type 或 color 变化时重绘
watch(() => [props.type, props.color], () => {
  drawIcon();
});
</script>

<style scoped>
canvas {
  display: inline-block;
  vertical-align: middle;
}
</style>
