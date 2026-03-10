<template>
  <div class="app-container">
    <!-- 顶部标题栏 -->
    <header class="app-header">
      <h1>缠论 AI 分析</h1>
    </header>

    <!-- 主内容区：左右分栏 -->
    <main class="main-content">
      <!-- 左侧：TradingView 图表 -->
      <section class="chart-section">
        <TradingViewWidget :symbol="symbol" :interval="interval" />
      </section>

      <!-- 右侧：AI 分析面板 -->
      <section class="ai-section">
        <AIAnalysisPanel
          :symbol="symbol"
          :interval="interval"
          :result="aiResult"
          :analyzing="analyzing"
          :mode="analysisMode"
          :aiProvider="aiProvider"
          :aiModel="aiModel"
          :apiKey="apiKey"
          @update:symbol="symbol = $event"
          @update:interval="interval = $event"
          @analyze="analyze"
          @update:mode="analysisMode = $event"
          @update:aiProvider="onAiProviderUpdate"
          @update:aiModel="onAiModelUpdate"
          @update:apiKey="onApiKeyUpdate"
          @show-history="showHistory = true"
        />
      </section>
    </main>

    <!-- 历史记录弹窗 -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showHistory" class="modal-overlay" @click.self="showHistory = false">
          <div class="history-modal doodle-modal">
            <div class="modal-header">
              <h2>📜 AI 分析记录</h2>
              <button class="close-btn" @click="showHistory = false">✕</button>
            </div>
            <div class="modal-content">
              <div v-if="analysisHistory.length === 0" class="empty-state">
                <p>暂无历史记录</p>
              </div>
              <div v-else class="history-list">
                <div
                  v-for="(record, index) in analysisHistory"
                  :key="index"
                  class="history-item"
                  @click="loadHistoryRecord(index)"
                >
                  <div class="history-header">
                    <span class="history-symbol">{{ record.symbol }} {{ record.intervalDisplay }}</span>
                    <span class="history-time">{{ record.time }}</span>
                  </div>
                  <div class="history-summary">
                    <span v-if="record.result?.primary_scenario" class="history-direction" :class="record.result.primary_scenario.direction">
                      {{ getDirectionLabel(record.result.primary_scenario.direction) }}
                    </span>
                    <span class="history-prob">{{ formatPercentage(record.result?.primary_scenario?.probability) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import TradingViewWidget from '@/components/TradingViewWidget.vue';
import AIAnalysisPanel from '@/components/AIAnalysisPanel.vue';
import { analyzeAI } from '@/api/client';

import type { AIAnalysisResult } from '@/types/chanlun';

const symbol = ref('BTCUSDT');
const interval = ref('1h');
const analysisMode = ref<'structured' | 'table'>('structured');
const aiResult = ref<AIAnalysisResult | null>(null);
const analyzing = ref(false);
const showHistory = ref(false);

// AI 配置状态
const aiProvider = ref('deepseek');
const aiModel = ref('deepseek-reasoner');
const apiKey = ref('');

// 分析历史记录
interface HistoryRecord {
  symbol: string;
  interval: string;
  intervalDisplay: string;
  time: string;
  result: AIAnalysisResult;
}

const analysisHistory = ref<HistoryRecord[]>([]);

function intervalDisplay(int: string): string {
  const map: Record<string, string> = {
    '15m': '15分',
    '1h': '1小时',
    '4h': '4小时',
    '1d': '1天'
  };
  return map[int] || int;
}

function getDirectionLabel(dir?: string): string {
  if (dir === 'up' || dir === 'long') return '做多';
  if (dir === 'down' || dir === 'short') return '做空';
  if (dir === 'range') return '震荡';
  return dir || '-';
}

function formatPercentage(value: number | undefined): string {
  if (value === undefined || value === null) return '-';
  const displayValue = value <= 1 ? value * 100 : value;
  return `${displayValue.toFixed(1)}%`;
}

async function analyze() {
  analyzing.value = true;
  try {
    const result = await analyzeAI(
      symbol.value,
      interval.value,
      analysisMode.value,
      false,
      aiProvider.value,
      aiModel.value,
      apiKey.value
    );
    aiResult.value = result;

    // 添加到历史记录
    analysisHistory.value.unshift({
      symbol: symbol.value,
      interval: interval.value,
      intervalDisplay: intervalDisplay(interval.value),
      time: new Date().toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      }),
      result: result
    });

    // 最多保留20条记录
    if (analysisHistory.value.length > 20) {
      analysisHistory.value = analysisHistory.value.slice(0, 20);
    }
  } catch (error: any) {
    console.error('AI analysis failed:', error);
    const errorMsg = error.response?.data?.error || error.message || 'AI analysis failed';
    alert(errorMsg);
  } finally {
    analyzing.value = false;
  }
}

function loadHistoryRecord(index: number) {
  const record = analysisHistory.value[index];
  if (record) {
    symbol.value = record.symbol;
    interval.value = record.interval;
    aiResult.value = record.result;
    showHistory.value = false;
  }
}

onMounted(() => {
  // 从 localStorage 加载历史记录
  try {
    const saved = localStorage.getItem('chanlun_analysis_history');
    if (saved) {
      try {
        analysisHistory.value = JSON.parse(saved);
      } catch (e) {
        console.error('Failed to load history:', e);
      }
    }

    // 从 localStorage 加载 AI 配置
    const savedProvider = localStorage.getItem('ai_provider');
    const savedModel = localStorage.getItem('ai_model');
    const savedApiKey = localStorage.getItem('ai_api_key');

    if (savedProvider) aiProvider.value = savedProvider;
    if (savedModel) aiModel.value = savedModel;
    if (savedApiKey) apiKey.value = savedApiKey;
  } catch (e) {
    console.warn('localStorage not available:', e);
  }
});

// 安全地保存到 localStorage
function saveToLocalStorage(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch (e) {
    console.warn('localStorage not available:', e);
  }
}

// AI 配置更新处理
function onAiProviderUpdate(value: string) {
  aiProvider.value = value;
  saveToLocalStorage('ai_provider', value);
}

function onAiModelUpdate(value: string) {
  aiModel.value = value;
  saveToLocalStorage('ai_model', value);
}

function onApiKeyUpdate(value: string) {
  apiKey.value = value;
  saveToLocalStorage('ai_api_key', value);
}

// 保存历史记录到 localStorage
watch(analysisHistory, (newVal) => {
  try {
    localStorage.setItem('chanlun_analysis_history', JSON.stringify(newVal));
  } catch (e) {
    console.warn('localStorage not available:', e);
  }
}, { deep: true });
</script>

<style lang="scss">
@use "@/assets/styles/variables.scss" as *;
@use "@/assets/styles/light-theme.scss" as *;

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.app-header {
  padding: 12px 20px;
  background: #FFFFFF;
  border-bottom: 1px solid #E0E3EB;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  flex-shrink: 0;
}

.app-header h1 {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.chart-section {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.ai-section {
  width: 400px;
  min-width: 350px;
  max-width: 600px;
  border-left: 1px solid #E0E3EB;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 响应式调整 */
@media (max-width: 1024px) {
  .ai-section {
    width: 350px;
    min-width: 300px;
  }
}

@media (max-width: 768px) {
  .main-content {
    flex-direction: column;
  }

  .ai-section {
    width: 100%;
    min-width: 0;
    max-width: none;
    border-left: none;
    border-top: 1px solid #E0E3EB;
    height: 40%;
  }

  .chart-section {
    height: 60%;
  }
}

/* 历史记录弹窗样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.history-modal {
  width: 100%;
  max-width: 500px;
  max-height: 80vh;
  font-family: 'Patrick Hand', 'Caveat', cursive;
  background: #F9F3E3;
  border: 4px solid #2C2C2C;
  border-radius: 25px 8px 20px 12px / 12px 20px 8px 25px;
  box-shadow: 4px 4px 0 #2C2C2C, 8px 8px 0 rgba(44, 44, 44, 0.15);
  display: flex;
  flex-direction: column;
}

.modal-header {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: #FFF8DC;
  border-bottom: 3px solid #2C2C2C;
  border-radius: 22px 5px 0 0 / 10px 5px 0 0;
}

.modal-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #2C2C2C;
}

.close-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #FFE0B2;
  border: 2px solid #2C2C2C;
  border-radius: 8px 3px 6px 4px / 4px 6px 3px 8px;
  font-size: 20px;
  font-weight: bold;
  color: #2C2C2C;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 2px 2px 0 #2C2C2C;
}

.close-btn:hover {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 #2C2C2C;
}

.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #666;
  font-size: 16px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-item {
  padding: 12px;
  background: #FFFFFF;
  border: 2px solid #E0E3EB;
  border-radius: 10px 4px 8px 5px / 5px 8px 4px 10px;
  cursor: pointer;
  transition: all 0.15s;
}

.history-item:hover {
  border-color: #2962FF;
  box-shadow: 2px 2px 0 rgba(41, 98, 255, 0.2);
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.history-symbol {
  font-size: 15px;
  font-weight: 600;
  color: #2C2C2C;
}

.history-time {
  font-size: 12px;
  color: #999;
}

.history-summary {
  display: flex;
  gap: 10px;
  align-items: center;
}

.history-direction {
  padding: 3px 10px;
  border-radius: 5px 2px 4px 4px / 4px 4px 2px 5px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid currentColor;
}

.history-direction.up,
.history-direction.long {
  background: rgba(8, 153, 129, 0.15);
  color: #089981;
}

.history-direction.down,
.history-direction.short {
  background: rgba(242, 54, 69, 0.15);
  color: #F23645;
}

.history-direction.range {
  background: rgba(120, 123, 134, 0.15);
  color: #787B86;
}

.history-prob {
  font-size: 16px;
  font-weight: bold;
  color: #2C2C2C;
}

/* 过渡动画 */
.modal-enter-active,
.modal-leave-active {
  transition: all 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .history-modal,
.modal-leave-to .history-modal {
  transform: scale(0.9);
  opacity: 0;
}

/* 滚动条样式 */
.modal-content::-webkit-scrollbar {
  width: 6px;
}

.modal-content::-webkit-scrollbar-track {
  background: #F9F3E3;
  border-radius: 3px;
}

.modal-content::-webkit-scrollbar-thumb {
  background: #D4C4A8;
  border-radius: 3px;
  border: 1px solid #2C2C2C;
}

.modal-content::-webkit-scrollbar-thumb:hover {
  background: #BCAAA4;
}
</style>
