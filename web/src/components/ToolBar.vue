<template>
  <div class="toolbar">
    <!-- Symbol & Interval Info -->
    <div class="toolbar-group info-group">
      <span class="symbol-info">{{ symbolDisplay }}</span>
    </div>

    <!-- Price Data -->
    <div class="toolbar-group price-group">
      <span class="price-item">开 {{ formatPrice(safePriceData.open) }}</span>
      <span class="price-item">高 {{ formatPrice(safePriceData.high) }}</span>
      <span class="price-item">低 {{ formatPrice(safePriceData.low) }}</span>
      <span class="price-item">收 {{ formatPrice(safePriceData.close) }}</span>
      <span class="price-change" :class="{ up: safePriceData.changePercent >= 0, down: safePriceData.changePercent < 0 }">
        {{ safePriceData.change >= 0 ? '+' : '' }}{{ safePriceData.change.toFixed(2) }}
        ({{ safePriceData.changePercent >= 0 ? '+' : '' }}{{ safePriceData.changePercent.toFixed(2) }}%)
      </span>
    </div>

    <!-- Layer controls - 手绘风格按钮 -->
    <div class="toolbar-group legend-group">
      <select v-model="localSymbol" @change="onSymbolChange" class="symbol-select">
        <option value="BTCUSDT">BTC/USDT</option>
        <option value="ETHUSDT">ETH/USDT</option>
      </select>
    </div>

    <!-- Interval selection - dropdown -->
    <div class="toolbar-group">
      <select v-model="localInterval" @change="onIntervalChange" class="interval-select">
        <option v-for="int in intervals" :key="int.value" :value="int.value">
          {{ int.label }}
        </option>
      </select>
    </div>

    <!-- Layer controls - 手绘风格按钮 -->
    <div class="toolbar-group legend-group">
      <HandDrawnLegendBtn
        v-for="layer in layers"
        :key="layer.key"
        :label="layer.label"
        :color="layer.color"
        :active="layer.show"
        @click="onToggleLayer(layer.key)"
      />
    </div>

    <!-- AI Analysis buttons - 手绘风格 -->
    <div class="toolbar-group ai-group">
      <HandDrawnButton
        variant="structured"
        :disabled="analyzing"
        @click="onAnalyzeStructured"
      >
        {{ analyzing ? '分析中...' : '结构化输出' }}
      </HandDrawnButton>
      <HandDrawnButton
        variant="table"
        :disabled="analyzing"
        @click="onAnalyzeTable"
      >
        {{ analyzing ? '分析中...' : '表格输出' }}
      </HandDrawnButton>
    </div>

    <!-- Show Result button - 涂鸦风格 -->
    <div class="toolbar-group result-group">
      <ShowResultButton
        :has-result="hasResult"
        :has-new-result="hasNewResult"
        @click="onShowResult"
      />
    </div>

    <!-- Refresh button -->
    <div class="toolbar-group">
      <button class="refresh-btn" @click="onRefresh" :disabled="loading" title="刷新 K 线数据">
        <svg :class="{ spinning: loading }" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <circle cx="12" cy="12" r="10" stroke-width="2"></circle>
          <path d="M 12 6v6l4 2" stroke-width="2" stroke-linecap="round"></path>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import HandDrawnButton from './HandDrawnButton.vue';
import HandDrawnLegendBtn from './HandDrawnLegendBtn.vue';
import ShowResultButton from './ShowResultButton.vue';

const props = defineProps<{
  symbol: string;
  interval: string;
  loading?: boolean;
  analyzing?: boolean;
  hasResult?: boolean;
  priceData?: {
    open: number;
    high: number;
    low: number;
    close: number;
    change: number;
    changePercent: number;
  };
}>();

const emit = defineEmits<{
  (e: 'update:symbol', value: string): void;
  (e: 'update:interval', value: string): void;
  (e: 'refresh'): void;
  (e: 'analyze', mode: string): void;
  (e: 'toggle-layer', key: string): void;
  (e: 'show-result'): void;
}>();

const localSymbol = ref(props.symbol);
const localInterval = ref(props.interval);
const hasNewResult = ref(false);

// Symbol display (e.g., "BTC/USDT 1h")
const symbolDisplay = `${props.symbol.slice(0, 3)}/${props.symbol.slice(3)} ${props.interval}`;

// Default price data to avoid undefined errors
const defaultPriceData = {
  open: 0,
  high: 0,
  low: 0,
  close: 0,
  change: 0,
  changePercent: 0
};

// Safe price data with defaults
const safePriceData = computed(() => props.priceData || defaultPriceData);

// Format price with commas
function formatPrice(price: number): string {
  if (price === 0) return '-';
  return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// 监听 hasResult 变化，标记新结果
watch(() => props.hasResult, (newVal, oldVal) => {
  if (newVal && !oldVal) {
    hasNewResult.value = true;
  }
});

// Interval options
const intervals = [
  { value: '15m', label: '15分' },
  { value: '1h', label: '1小时' },
  { value: '4h', label: '4小时' },
  { value: '1d', label: '1天' }
];

// Layer options
const layers = ref([
  { key: 'bi', label: '笔', color: '#2962FF', show: true },
  { key: 'xd', label: '线段', color: '#9C27B0', show: true },
  { key: 'zs', label: '中枢', color: '#787B86', show: true },
  { key: 'fx', label: '分型', color: '#388E3C', show: true },
  { key: 'mmd', label: '买卖点', color: '#089981', show: true }
]);

function onSymbolChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  emit('update:symbol', target.value);
}

function onIntervalChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  localInterval.value = target.value;
  emit('update:interval', target.value);
}

function onRefresh() {
  emit('refresh');
}

function onAnalyzeStructured() {
  emit('analyze', 'structured');
}

function onAnalyzeTable() {
  emit('analyze', 'table');
}

function onToggleLayer(key: string) {
  const layer = layers.value.find(l => l.key === key);
  if (layer) {
    layer.show = !layer.show;
  }
}

function onShowResult() {
  hasNewResult.value = false;
  emit('show-result');
}

defineExpose({
  layers
});
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: #FFFFFF;
  border-bottom: 1px solid #E0E3EB;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  flex-wrap: wrap;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-right: 10px;
  border-right: 1px solid #E0E3EB;
}

.toolbar-group:last-child {
  border-right: none;
}

/* 下拉选择框样式 */
.symbol-select,
.interval-select {
  padding: 6px 10px;
  font-size: 13px;
  font-weight: 600;
  color: #131722;
  background: #F8F9FD;
  border: 1px solid #E0E3EB;
  border-radius: 4px;
  cursor: pointer;
  outline: none;
}

.interval-select {
  min-width: 70px;
}

.symbol-select:hover,
.interval-select:hover {
  background: #F2F3F6;
}

/* 图例按钮组 */
.legend-group {
  gap: 4px;
}

/* Info group - Symbol display */
.info-group {
  padding-right: 10px;
}

.symbol-info {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
}

/* Price group - Price data display */
.price-group {
  gap: 16px;
  padding-right: 10px;
}

.price-item {
  font-size: 12px;
  color: #666;
  white-space: nowrap;
}

.price-change {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;

  &.up { color: #089981; }
  &.down { color: #F23645; }
}

/* AI 按钮组 */
.ai-group {
  gap: 8px;
}

/* 结果按钮组 */
.result-group {
  gap: 0;
  padding-right: 10px;
}

/* 刷新按钮 */
.refresh-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #F8F9FD;
  border: 1px solid #E0E3EB;
  color: #787B86;
  cursor: pointer;
  transition: all 0.15s;
  border-radius: 50%;
}

.refresh-btn:hover:not(:disabled) {
  background: #F2F3F6;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

svg {
  width: 16px;
  height: 16px;
}

svg.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
