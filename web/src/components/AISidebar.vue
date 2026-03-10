<template>
  <div class="ai-sidebar">
    <div class="sidebar-header">
      <RoughIcon type="ai" :size="28" color="#2962FF" />
      <span>AI 分析结果</span>
    </div>

    <div v-if="loading" class="sidebar-loading">
      <div class="spinner"></div>
      <p>正在分析中...</p>
    </div>

    <div v-else-if="!result" class="sidebar-empty">
      <RoughIcon type="ai" :size="64" color="#E0E3EB" />
      <p>点击「AI 分析」按钮开始</p>
    </div>

    <div v-else class="sidebar-content">
      <div class="sidebar-section">
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

      <div v-if="result.primary_scenario" class="sidebar-section primary-scenario">
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
            <span class="detail-value target">{{ formatPrice(calculateTarget(result.primary_scenario)) }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">止损</span>
            <span class="detail-value stop">{{ formatPrice(calculateStop(result.primary_scenario)) }}</span>
          </div>
          <div v-if="result.primary_scenario.trigger" class="detail-row">
            <span class="detail-label">触发</span>
            <span class="detail-value">{{ result.primary_scenario.trigger }}</span>
          </div>
        </div>
      </div>

      <div v-if="result.scenarios && result.scenarios.length" class="sidebar-section">
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
              <span class="detail-value">{{ scenario.entry ? formatPrice(scenario.entry) : '-' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">目标</span>
              <span class="detail-value">{{ scenario.target ? formatPrice(scenario.target) : '-' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">止损</span>
              <span class="detail-value">{{ scenario.stop ? formatPrice(scenario.stop) : '-' }}</span>
            </div>
            <div v-if="scenario.reason || scenario.logic" class="detail-row detail-reason">
              <span class="detail-label">逻辑</span>
              <span class="detail-value">{{ truncateText(scenario.reason || scenario.logic || '', 40) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="result.analysis" class="sidebar-section">
        <h4>分析内容</h4>
        <div class="analysis-text">{{ result.analysis }}</div>
      </div>

      <div v-if="result.risk_notes && result.risk_notes.length" class="sidebar-section risk-notes">
        <h4>风险提示</h4>
        <ul>
          <li v-for="(note, i) in result.risk_notes.slice(0, 3)" :key="i">{{ note }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import RoughIcon from './RoughIcon.vue';
import { formatPrice, formatPercentage } from '../utils/formatters';
import type { AIAnalysisResult } from '../types/chanlun';

const props = defineProps<{
  result: AIAnalysisResult | null;
  loading?: boolean;
}>();

function getCurrentPrice(): number {
  return props.result?.meta?.price || 0;
}

function calculateTarget(scenario: any): number {
  const current = getCurrentPrice();
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

function calculateStop(scenario: any): number {
  const current = getCurrentPrice();
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
.ai-sidebar {
  width: 700px;
  min-width: 400px;
  height: 100%;
  background: #FFFFFF;
  border-left: 1px solid #E0E3EB;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: #F8F9FD;
  border-bottom: 1px solid #E0E3EB;
  font-weight: 600;
  font-size: 16px;
  color: #131722;
}

.sidebar-loading,
.sidebar-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #787B86;
}

.sidebar-loading p,
.sidebar-empty p {
  margin-top: 16px;
  font-size: 14px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #E0E3EB;
  border-top-color: #2962FF;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.sidebar-section {
  margin-bottom: 20px;
  padding: 16px;
  background: #F8F9FD;
  border-radius: 8px;
}

.sidebar-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #787B86;
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
  font-size: 13px;
  color: #787B86;
}

.value {
  font-size: 14px;
  font-weight: 600;
  color: #131722;
}

.trend-badge {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
}

.trend-up {
  background: rgba(8, 153, 129, 0.1);
  color: #089981;
}

.trend-down {
  background: rgba(242, 54, 69, 0.1);
  color: #F23645;
}

.trend-unknown {
  background: rgba(120, 123, 134, 0.1);
  color: #787B86;
}

.primary-scenario {
  background: linear-gradient(135deg, rgba(41, 98, 255, 0.05) 0%, rgba(41, 98, 255, 0.02) 100%);
  border: 1px solid rgba(41, 98, 255, 0.2);
}

.scenario-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.scenario-direction {
  font-size: 14px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 4px;
}

.scenario-direction.up,
.scenario-direction.long {
  background: rgba(8, 153, 129, 0.1);
  color: #089981;
}

.scenario-direction.down,
.scenario-direction.short {
  background: rgba(242, 54, 69, 0.1);
  color: #F23645;
}

.scenario-direction.range {
  background: rgba(120, 123, 134, 0.1);
  color: #787B86;
}

.scenario-prob {
  font-size: 20px;
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
  font-size: 13px;
}

.detail-label {
  color: #787B86;
}

.detail-value {
  color: #131722;
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
  padding-top: 6px;
  border-top: 1px solid rgba(0, 0, 0, 0.05);
}

.scenario-card {
  padding: 12px;
  background: #FFFFFF;
  border-radius: 6px;
  margin-bottom: 10px;
  border-left: 4px solid #E0E3EB;
}

.scenario-card.up,
.scenario-card.long {
  border-left-color: #089981;
}

.scenario-card.down,
.scenario-card.short {
  border-left-color: #F23645;
}

.scenario-card.range {
  border-left-color: #787B86;
}

.scenario-title {
  font-size: 14px;
  font-weight: 600;
  color: #131722;
}

.scenario-card .scenario-details {
  margin-top: 8px;
}

.analysis-text {
  font-size: 13px;
  line-height: 1.6;
  color: #131722;
  white-space: pre-wrap;
}

.risk-notes {
  background: rgba(242, 54, 69, 0.05);
  border: 1px solid rgba(242, 54, 69, 0.2);
}

.risk-notes h4 {
  color: #F23645;
}

.risk-notes ul {
  margin: 0;
  padding-left: 20px;
}

.risk-notes li {
  font-size: 12px;
  color: #787B86;
  line-height: 1.6;
  margin-bottom: 6px;
}
</style>
