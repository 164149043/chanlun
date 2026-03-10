<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="modal-overlay" @click.self="$emit('close')">
        <div class="modal-wrapper">
          <div class="modal-content doodle-modal" :class="{ 'loading': loading }">
            <!-- 弹窗头部 -->
            <div class="modal-header">
              <div class="header-left">
                <span class="header-icon">📊</span>
                <h2>AI 分析结果</h2>
              </div>
              <button class="close-btn" @click="$emit('close')" title="关闭">✕</button>
            </div>

            <!-- 弹窗内容 -->
            <div class="modal-body">
              <!-- 加载状态 -->
              <div v-if="loading" class="modal-loading">
                <div class="doodle-spinner"></div>
                <p>正在分析中...</p>
              </div>

              <!-- 空状态 -->
              <div v-else-if="!result" class="modal-empty">
                <span class="empty-icon">📋</span>
                <p>暂无分析结果</p>
                <p class="empty-hint">点击「结构化输出」或「表格输出」开始分析</p>
              </div>

              <!-- 分析结果 -->
              <div v-else class="result-content">
                <!-- 结构判断 -->
                <div class="result-section">
                  <h4>结构判断</h4>
                  <div class="info-row">
                    <span class="label">趋势</span>
                    <span class="value trend-badge" :class="getTrendClass(result.structure_judgement?.trend)">
                      {{ getTrendLabel(result.structure_judgement?.trend) }}
                    </span>
                  </div>
                  <div class="info-row">
                    <span class="label">位置</span>
                    <span class="value">{{ getPositionLabel(result.structure_judgement?.price_position) }}</span>
                  </div>
                  <div v-if="result.structure_judgement?.zs" class="info-row">
                    <span class="label">中枢区间</span>
                    <span class="value">
                      {{ formatPrice(result.structure_judgement.zs.zd) }} ~ {{ formatPrice(result.structure_judgement.zs.zg) }}
                    </span>
                  </div>
                </div>

                <!-- 主推策略 -->
                <div v-if="result.primary_scenario" class="result-section primary-scenario">
                  <h4>主推策略</h4>
                  <div class="scenario-header">
                    <span class="scenario-direction" :class="result.primary_scenario.direction">
                      {{ getDirectionLabel(result.primary_scenario.direction) }}
                    </span>
                    <span class="scenario-prob" :class="result.primary_scenario.direction">
                      {{ formatPercentage(result.primary_scenario.probability) }}
                    </span>
                  </div>
                  <div class="scenario-details">
                    <div class="detail-row">
                      <span class="detail-label">目标</span>
                      <span class="detail-value target">{{ formatPrice(calculateTarget(result.primary_scenario, result)) }}</span>
                    </div>
                    <div class="detail-row">
                      <span class="detail-label">止损</span>
                      <span class="detail-value stop">{{ formatPrice(calculateStop(result.primary_scenario, result)) }}</span>
                    </div>
                    <div v-if="result.primary_scenario.trigger" class="detail-row">
                      <span class="detail-label">触发</span>
                      <span class="detail-value">{{ result.primary_scenario.trigger }}</span>
                    </div>
                  </div>
                </div>

                <!-- 策略分析 -->
                <div v-if="result.scenarios && result.scenarios.length" class="result-section">
                  <h4>策略分析</h4>
                  <div
                    v-for="scenario in result.scenarios"
                    :key="scenario.rank"
                    class="scenario-card"
                    :class="scenario.direction || scenario.type"
                  >
                    <div class="scenario-header">
                      <span class="scenario-title">
                        {{ getScenarioLabel(scenario.direction || scenario.type) }}
                      </span>
                      <span class="scenario-prob" :class="scenario.direction || scenario.type">
                        {{ formatPercentage(scenario.probability) }}
                      </span>
                    </div>
                    <div class="scenario-details">
                      <div class="detail-row">
                        <span class="detail-label">入场</span>
                        <span class="detail-value">{{ getScenarioEntry(scenario, result) }}</span>
                      </div>
                      <div class="detail-row">
                        <span class="detail-label">目标</span>
                        <span class="detail-value">{{ getScenarioTarget(scenario, result) }}</span>
                      </div>
                      <div class="detail-row">
                        <span class="detail-label">止损</span>
                        <span class="detail-value">{{ getScenarioStop(scenario, result) }}</span>
                      </div>
                      <div v-if="scenario.reason || scenario.logic" class="detail-row detail-reason">
                        <span class="detail-label">逻辑</span>
                        <span class="detail-value">{{ truncateText(scenario.reason || scenario.logic || '', 60) }}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 分析内容 -->
                <div v-if="result.analysis" class="result-section">
                  <h4>分析内容</h4>
                  <div class="analysis-text">{{ result.analysis }}</div>
                </div>

                <!-- 风险提示 -->
                <div v-if="result.risk_notes && result.risk_notes.length" class="result-section risk-notes">
                  <h4>风险提示</h4>
                  <ul>
                    <li v-for="(note, i) in result.risk_notes.slice(0, 3)" :key="i">{{ note }}</li>
                  </ul>
                </div>
              </div>
            </div>

            <!-- 弹窗底部 -->
            <div class="modal-footer">
              <button class="doodle-close-btn" @click="$emit('close')">
                <span>关闭</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { formatPrice, formatPercentage } from '../utils/formatters';
import type { AIAnalysisResult } from '../types/chanlun';

defineProps<{
  show: boolean;
  result: AIAnalysisResult | null;
  loading?: boolean;
}>();

defineEmits<{
  close: [];
}>();

function getCurrentPrice(result: AIAnalysisResult | null): number {
  return result?.meta?.price || 0;
}

function calculateTarget(scenario: any, result: AIAnalysisResult | null): number {
  const current = getCurrentPrice(result);
  if (scenario.target_pct) {
    const direction = scenario.direction;
    if (direction === 'up') {
      return current * (1 + scenario.target_pct / 100);
    } else if (direction === 'down') {
      return current * (1 - scenario.target_pct / 100);
    }
  }
  if (scenario.target_range && scenario.target_range.length === 2) {
    return scenario.direction === 'up' ? scenario.target_range[1] : scenario.target_range[0];
  }
  if (scenario.target) return scenario.target;
  return current;
}

function calculateStop(scenario: any, result: AIAnalysisResult | null): number {
  const current = getCurrentPrice(result);
  if (scenario.stop_pct) {
    const direction = scenario.direction;
    if (direction === 'up') {
      return current * (1 - scenario.stop_pct / 100);
    } else if (direction === 'down') {
      return current * (1 + scenario.stop_pct / 100);
    }
  }
  if (scenario.stop) return scenario.stop;
  return current;
}

// 获取策略的入场价格
function getScenarioEntry(scenario: any, result: AIAnalysisResult | null): string {
  if (scenario.entry) return formatPrice(scenario.entry);
  // 从 target_range 推算入场位置：做多取低值，做空取高值
  if (scenario.target_range && Array.isArray(scenario.target_range) && scenario.target_range.length === 2) {
    const direction = scenario.direction;
    if (direction === 'up') {
      return formatPrice(scenario.target_range[0]);
    } else if (direction === 'down') {
      return formatPrice(scenario.target_range[1]);
    } else {
      // 震荡策略使用当前价格作为参考
      return formatPrice(getCurrentPrice(result));
    }
  }
  return '-';
}

// 获取策略的目标价格（优先使用直接值，否则计算）
function getScenarioTarget(scenario: any, result: AIAnalysisResult | null): string {
  if (scenario.target) return formatPrice(scenario.target);
  if (scenario.target_pct) return formatPrice(calculateTarget(scenario, result));
  // 支持从 target_range 数组获取目标价格
  if (scenario.target_range && Array.isArray(scenario.target_range) && scenario.target_range.length === 2) {
    const current = getCurrentPrice(result);
    const direction = scenario.direction;
    // 做多取高值，做空取低值
    if (direction === 'up') {
      return formatPrice(scenario.target_range[1]);
    } else if (direction === 'down') {
      return formatPrice(scenario.target_range[0]);
    } else {
      // 震荡显示区间
      return `${formatPrice(scenario.target_range[0])} ~ ${formatPrice(scenario.target_range[1])}`;
    }
  }
  return '-';
}

// 获取策略的止损价格（优先使用直接值，否则基于 target_range 计算）
function getScenarioStop(scenario: any, result: AIAnalysisResult | null): string {
  if (scenario.stop) return formatPrice(scenario.stop);
  if (scenario.stop_pct) return formatPrice(calculateStop(scenario, result));
  // 基于 target_range 和方向推算止损位
  if (scenario.target_range && Array.isArray(scenario.target_range) && scenario.target_range.length === 2) {
    const current = getCurrentPrice(result);
    const direction = scenario.direction;
    const rangeSize = scenario.target_range[1] - scenario.target_range[0];
    // 止损设为入场位外推约 1-2% 的 range
    if (direction === 'up') {
      // 做多：止损在入场下方
      const entry = scenario.target_range[0];
      const stop = entry - rangeSize * 0.3;
      return formatPrice(stop);
    } else if (direction === 'down') {
      // 做空：止损在入场上方
      const entry = scenario.target_range[1];
      const stop = entry + rangeSize * 0.3;
      return formatPrice(stop);
    }
  }
  return '-';
}

function getTrendClass(trend?: string): string {
  if (!trend) return '';
  if (trend.includes('up')) return 'trend-up';
  if (trend.includes('down')) return 'trend-down';
  return 'trend-unknown';
}

function getTrendLabel(trend?: string): string {
  if (!trend) return '未知';
  if (trend.includes('up')) return '上升';
  if (trend.includes('down')) return '下降';
  if (trend.includes('consol')) return '震荡';
  return trend;
}

function getPositionLabel(pos?: string): string {
  if (!pos) return '未知';
  if (pos.includes('above')) return '中枢上方';
  if (pos.includes('below')) return '中枢下方';
  if (pos.includes('inside')) return '中枢内部';
  return pos;
}

function getDirectionLabel(dir?: string): string {
  if (dir === 'up') return '做多';
  if (dir === 'down') return '做空';
  if (dir === 'range') return '震荡';
  return dir || '-';
}

function getScenarioLabel(type?: string): string {
  if (type === 'long') return '做多策略';
  if (type === 'short') return '做空策略';
  if (type === 'range') return '震荡策略';
  if (type === 'up') return '做多策略';
  if (type === 'down') return '做空策略';
  return type || '-';
}

function truncateText(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.substring(0, maxLen) + '...';
}
</script>

<style scoped>
/* 模态框遮罩 */
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

.modal-wrapper {
  width: 100%;
  max-width: 600px;
  max-height: 90vh;
}

/* 涂鸦风格弹窗 */
.doodle-modal {
  font-family: 'Patrick Hand', 'Caveat', cursive;
  background: #F9F3E3;
  border: 4px solid #2C2C2C;
  /* 不规则边框 - 手绘效果 */
  border-radius: 25px 8px 20px 12px / 12px 20px 8px 25px;
  /* 马克笔阴影 */
  box-shadow:
    4px 4px 0 #2C2C2C,
    8px 8px 0 rgba(44, 44, 44, 0.15);
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  transform: rotate(-0.3deg);
}

/* 纸张纹理 */
.doodle-modal::before {
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

/* 弹窗头部 */
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

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  font-size: 24px;
}

.modal-header h2 {
  margin: 0;
  font-size: 22px;
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

.close-btn:active {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 #2C2C2C;
}

/* 弹窗内容区域 */
.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

/* 加载状态 */
.modal-loading,
.modal-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #666;
}

.modal-loading p,
.modal-empty p {
  margin-top: 16px;
  font-size: 16px;
}

.empty-hint {
  font-size: 14px !important;
  color: #999 !important;
}

.doodle-spinner {
  width: 50px;
  height: 50px;
  border: 4px solid #E0E3EB;
  border-top-color: #2C2C2C;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 结果内容 */
.result-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-section {
  padding: 16px;
  background: #FFF8DC;
  border: 2px solid #D4C4A8;
  border-radius: 12px 4px 10px 6px / 6px 10px 4px 12px;
}

.result-section h4 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 700;
  color: #2C2C2C;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}

.label {
  font-size: 14px;
  color: #666;
}

.value {
  font-size: 15px;
  font-weight: 600;
  color: #2C2C2C;
}

.trend-badge {
  padding: 4px 12px;
  border-radius: 6px 3px 4px 5px / 5px 4px 3px 6px;
  font-size: 13px;
  border: 1px solid currentColor;
}

.trend-up {
  background: rgba(8, 153, 129, 0.15);
  color: #089981;
}

.trend-down {
  background: rgba(242, 54, 69, 0.15);
  color: #F23645;
}

.trend-unknown {
  background: rgba(120, 123, 134, 0.15);
  color: #787B86;
}

.primary-scenario {
  background: rgba(41, 98, 255, 0.08);
  border-color: #2962FF;
}

.scenario-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.scenario-direction {
  font-size: 15px;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 5px 2px 4px 3px / 3px 4px 2px 5px;
  border: 1px solid currentColor;
}

.scenario-direction.up,
.scenario-direction.long {
  background: rgba(8, 153, 129, 0.15);
  color: #089981;
}

.scenario-direction.down,
.scenario-direction.short {
  background: rgba(242, 54, 69, 0.15);
  color: #F23645;
}

.scenario-direction.range {
  background: rgba(120, 123, 134, 0.15);
  color: #787B86;
}

.scenario-prob {
  font-size: 22px;
  font-weight: bold;
}

.scenario-prob.up,
.scenario-prob.long {
  color: #089981;
}

.scenario-prob.down,
.scenario-prob.short {
  color: #F23645;
}

.scenario-prob.range {
  color: #787B86;
}

.scenario-details {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}

.detail-label {
  color: #666;
}

.detail-value {
  color: #2C2C2C;
  font-weight: 500;
}

.detail-value.target {
  color: #089981;
  font-weight: 600;
}

.detail-value.stop {
  color: #F23645;
  font-weight: 600;
}

.detail-reason {
  margin-top: 4px;
  padding-top: 8px;
  border-top: 2px dashed rgba(0, 0, 0, 0.1);
}

.scenario-card {
  padding: 12px;
  background: #FFFFFF;
  border-radius: 8px;
  margin-bottom: 10px;
  border-left: 4px solid #D4C4A8;
  border: 2px solid #E0E3EB;
}

.scenario-card.up,
.scenario-card.long {
  border-left-color: #089981;
  border-color: #089981;
}

.scenario-card.down,
.scenario-card.short {
  border-left-color: #F23645;
  border-color: #F23645;
}

.scenario-card.range {
  border-left-color: #787B86;
  border-color: #787B86;
}

.scenario-title {
  font-size: 15px;
  font-weight: 600;
  color: #2C2C2C;
}

.scenario-card .scenario-details {
  margin-top: 8px;
}

.analysis-text {
  font-size: 14px;
  line-height: 1.6;
  color: #2C2C2C;
  white-space: pre-wrap;
}

.risk-notes {
  background: rgba(242, 54, 69, 0.08) !important;
  border-color: #F23645 !important;
}

.risk-notes h4 {
  color: #F23645;
}

.risk-notes ul {
  margin: 0;
  padding-left: 20px;
}

.risk-notes li {
  font-size: 13px;
  color: #666;
  line-height: 1.6;
  margin-bottom: 6px;
}

/* 弹窗底部 */
.modal-footer {
  padding: 12px 20px;
  background: #FFF8DC;
  border-top: 2px solid #D4C4A8;
  border-radius: 0 0 20px 10px / 10px 0 20px 10px;
  display: flex;
  justify-content: flex-end;
}

.doodle-close-btn {
  font-family: 'Patrick Hand', 'Caveat', cursive;
  font-size: 16px;
  padding: 8px 24px;
  background: #FFE0B2;
  border: 3px solid #2C2C2C;
  border-radius: 8px 3px 6px 4px / 4px 6px 3px 8px;
  color: #2C2C2C;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 2px 2px 0 #2C2C2C;
}

.doodle-close-btn:hover {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 #2C2C2C;
  background: #FFCC80;
}

.doodle-close-btn:active {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 #2C2C2C;
}

/* 过渡动画 */
.modal-enter-active,
.modal-leave-active {
  transition: all 0.3s ease;
}

.modal-enter-active .modal-content,
.modal-leave-active .modal-content {
  transition: all 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-content,
.modal-leave-to .modal-content {
  transform: scale(0.9) rotate(-0.3deg);
  opacity: 0;
}

/* 滚动条样式 */
.modal-body::-webkit-scrollbar {
  width: 8px;
}

.modal-body::-webkit-scrollbar-track {
  background: #F9F3E3;
  border-radius: 4px;
}

.modal-body::-webkit-scrollbar-thumb {
  background: #D4C4A8;
  border-radius: 4px;
  border: 1px solid #2C2C2C;
}

.modal-body::-webkit-scrollbar-thumb:hover {
  background: #BCAAA4;
}
</style>
