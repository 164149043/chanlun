<template>
  <div class="state-machine-card" :class="stateClass">
    <!-- 状态徽章 -->
    <div class="state-badge">
      <span class="state-icon">{{ stateIcon }}</span>
      <span class="state-label">{{ stateLabel }}</span>
    </div>

    <!-- 策略方向 -->
    <div v-if="activeStrategy" class="strategy-direction" :class="activeStrategy.direction">
      <span class="direction-icon">{{ directionIcon }}</span>
      <span class="direction-label">{{ directionLabel }}</span>
      <span class="strategy-status">{{ statusLabel }}</span>
    </div>

    <!-- 入场区间 -->
    <div v-if="activeStrategy" class="entry-section">
      <div class="section-title">入场区间</div>
      <div class="price-zone">
        {{ formatPrice(activeStrategy.entry_gate.price_zone[0]) }}
        <span class="separator">→</span>
        {{ formatPrice(activeStrategy.entry_gate.price_zone[1]) }}
      </div>
    </div>

    <!-- 结构触发条件 -->
    <div v-if="activeStrategy && activeStrategy.entry_gate.structure_required.length" class="structure-section">
      <div class="section-title">结构触发</div>
      <ul class="condition-list">
        <li v-for="(cond, i) in activeStrategy.entry_gate.structure_required" :key="i">
          {{ formatCondition(cond) }}
        </li>
      </ul>
    </div>

    <!-- 执行参数 -->
    <div v-if="activeStrategy" class="execution-section">
      <div class="section-title">执行参数</div>
      <div class="param-grid">
        <div class="param-item">
          <span class="param-label">止损</span>
          <span class="param-value stop">{{ formatPrice(activeStrategy.execution.stop_loss) }}</span>
        </div>
        <div class="param-item">
          <span class="param-label">目标</span>
          <span class="param-value target">{{ formatPrice(activeStrategy.execution.target) }}</span>
        </div>
        <div class="param-item">
          <span class="param-label">盈亏比</span>
          <span class="param-value">{{ activeStrategy.execution.rr.toFixed(1) }}:1</span>
        </div>
      </div>
    </div>

    <!-- 否决条件 -->
    <div v-if="invalidation && invalidation.invalidate_active_if.length" class="invalidation-section">
      <details class="invalidation-details">
        <summary>否决条件 ({{ invalidation.invalidate_active_if.length }})</summary>
        <ul class="condition-list">
          <li v-for="(cond, i) in invalidation.invalidate_active_if" :key="i">
            {{ formatCondition(cond) }} → {{ formatNextState(invalidation.next_state) }}
          </li>
        </ul>
      </details>
    </div>

    <!-- 备用策略 -->
    <div v-if="standbyStrategies && standbyStrategies.length" class="standby-section">
      <details class="standby-details">
        <summary>备用策略 ({{ standbyStrategies.length }})</summary>
        <div class="standby-list">
          <div v-for="(strategy, i) in standbyStrategies" :key="i" class="standby-item" :class="strategy.direction">
            <span class="standby-direction">{{ getDirectionLabel(strategy.direction) }}</span>
            <span class="standby-conditions">
              {{ strategy.activate_if.join(', ') }}
            </span>
          </div>
        </div>
      </details>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { StateMachineData, StateValue } from '@/types/chanlun';

const props = defineProps<{
  data: StateMachineData;
}>();

// 当前状态
const currentState = computed<StateValue>(() => props.data.current_state || 'OBSERVE_ONLY');

// 激活策略
const activeStrategy = computed(() => props.data.active_strategy);

// 否决条件
const invalidation = computed(() => props.data.invalidation);

// 备用策略
const standbyStrategies = computed(() => props.data.standby_strategies || []);

// 状态样式类
const stateClass = computed(() => currentState.value);

// 状态图标和标签
const stateIcon = computed(() => {
  switch (currentState.value) {
    case 'STRATEGY_ACTIVE': return '🎯';
    case 'WAIT_CONFIRMATION': return '⏳';
    case 'OBSERVE_ONLY': return '👁';
    default: return '❓';
  }
});

const stateLabel = computed(() => {
  switch (currentState.value) {
    case 'STRATEGY_ACTIVE': return '策略激活';
    case 'WAIT_CONFIRMATION': return '等待确认';
    case 'OBSERVE_ONLY': return '仅观察';
    default: return '未知';
  }
});

// 方向图标
const directionIcon = computed(() => {
  if (!activeStrategy.value) return '';
  return activeStrategy.value.direction === 'up' ? '📈' : '📉';
});

// 方向标签
const directionLabel = computed(() => {
  if (!activeStrategy.value) return '';
  return activeStrategy.value.direction === 'up' ? '做多' : '做空';
});

// 策略状态标签
const statusLabel = computed(() => {
  if (!activeStrategy.value) return '';
  switch (activeStrategy.value.status) {
    case 'WAIT': return '等待';
    case 'READY': return '就绪';
    case 'ACTIVE': return '执行中';
    case 'INVALIDATED': return '已否决';
    default: return activeStrategy.value.status || '';
  }
});

// 格式化价格
function formatPrice(price: number): string {
  if (!price || price === 0) return '-';
  return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// 格式化结构条件
function formatCondition(cond: string): string {
  const conditionMap: Record<string, string> = {
    'price_hold_dd': '价格守住 DD',
    'price_break_gg': '价格突破 GG',
    'price_break_zd': '价格突破 ZD',
    'price_reject_zg': '价格受阻 ZG',
    '15m_break_zd': '15分钟突破 ZD',
    '15m_failed_break_zd': '15分钟未能突破 ZD',
    '15m_reclaim_zg_with_strength': '15分钟强势站回 ZG',
    '1h_new_up_bi': '1小时新向上笔',
    '1h_new_down_bi': '1小时新向下笔',
    '1h_trend_flip_up': '1小时趋势翻多',
    'no_new_down_bi': '无新向下笔',
    'no_new_up_bi': '无新向上笔',
    'volume_confirm': '成交量确认',
    'strong_volume': '大成交量',
    // 额外条件
    'price_reject_zd': '价格受阻 ZD',
    'price_hold_zg': '价格守住 ZG',
    'price_reclaim_zg': '价格站回 ZG',
    '15m_break_gg': '15分钟突破 GG',
    '1h_break_zg': '1小时突破 ZG',
    '1h_break_dd': '1小时跌破 DD',
    'volume_surge': '成交量激增',
    'volume_weak': '成交量萎缩',
  };

  return conditionMap[cond] || cond;
}

// 格式化下一个状态
function formatNextState(state: string): string {
  const stateMap: Record<string, string> = {
    'OBSERVE_ONLY': '观察模式',
    'RANGE_STRATEGY': '震荡策略',
    'STRATEGY_ACTIVE': '激活模式',
    'WAIT_CONFIRMATION': '等待确认',
  };

  return stateMap[state] || state;
}

function getDirectionLabel(dir: string): string {
  if (dir === 'up') return '做多';
  if (dir === 'down') return '做空';
  if (dir === 'range') return '震荡';
  return dir;
}
</script>

<style scoped>
/* 状态机卡片 - 使用微软雅黑字体 */
.state-machine-card {
  background: #FFF8DC;
  border: 2px solid #2C2C2C;
  border-radius: 12px 6px 10px 8px / 8px 10px 6px 12px;
  padding: 12px;
  margin-bottom: 12px;
  font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", "微软雅黑", "Segoe UI", Roboto, sans-serif;
}

/* 状态颜色 */
.state-machine-card.STRATEGY_ACTIVE {
  border-color: #089981;
  box-shadow: 2px 2px 0 #089981;
  background: linear-gradient(135deg, #FFF8DC 0%, rgba(8, 153, 129, 0.08) 100%);
}

.state-machine-card.WAIT_CONFIRMATION {
  border-color: #F59E0B;
  box-shadow: 2px 2px 0 #F59E0B;
  background: linear-gradient(135deg, #FFF8DC 0%, rgba(245, 158, 11, 0.08) 100%);
}

.state-machine-card.OBSERVE_ONLY {
  border-color: #787B86;
  box-shadow: 2px 2px 0 #787B86;
  opacity: 0.75;
  background: linear-gradient(135deg, #FFF8DC 0%, rgba(120, 123, 134, 0.08) 100%);
}

.state-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  font-weight: 700;
  font-size: 16px;
}

.state-icon {
  font-size: 20px;
}

.state-label {
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* 策略方向 */
.strategy-direction {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
  border-radius: 6px 3px 5px 3px / 3px 5px 3px 6px;
  border: 2px solid #2C2C2C;
  background: #FFFFFF;
}

.strategy-direction.up {
  background: rgba(8, 153, 129, 0.15);
  color: #089981;
}

.strategy-direction.down {
  background: rgba(242, 54, 69, 0.15);
  color: #F23645;
}

.direction-icon {
  font-size: 18px;
}

.direction-label {
  font-size: 15px;
  font-weight: 700;
}

.strategy-status {
  margin-left: auto;
  font-size: 12px;
  opacity: 0.8;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid currentColor;
}

/* 入场区间 */
.entry-section {
  margin-bottom: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #666;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.price-zone {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 16px;
  font-weight: 600;
  color: #2C2C2C;
  display: flex;
  align-items: center;
  gap: 8px;
}

.separator {
  color: #999;
}

/* 结构触发条件 */
.structure-section {
  margin-bottom: 12px;
}

.condition-list {
  margin: 0;
  padding-left: 18px;
  list-style-type: none;
}

.condition-list li {
  font-size: 13px;
  color: #444;
  line-height: 1.6;
  margin-bottom: 4px;
  position: relative;
}

.condition-list li::before {
  content: '•';
  position: absolute;
  left: -12px;
  color: #D4C4A8;
}

/* 执行参数 */
.execution-section {
  margin-bottom: 12px;
}

.param-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.param-item {
  display: flex;
  flex-direction: column;
  padding: 6px 8px;
  background: #FFFFFF;
  border-radius: 4px 2px 3px 2px / 2px 3px 2px 4px;
  border: 1px solid #E0E3EB;
}

.param-label {
  font-size: 11px;
  color: #666;
  margin-bottom: 2px;
}

.param-value {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 14px;
  font-weight: 600;
}

.param-value.stop {
  color: #F23645;
}

.param-value.target {
  color: #089981;
}

/* 否决条件 */
.invalidation-section {
  margin-bottom: 12px;
}

.invalidation-details {
  font-size: 13px;
}

.invalidation-details summary {
  cursor: pointer;
  font-weight: 600;
  color: #666;
  margin-bottom: 6px;
  list-style: none;
  padding: 0;
}

.invalidation-details summary::-webkit-details-marker {
  display: none;
}

.invalidation-details summary::before {
  content: '▶ ';
  margin-right: 4px;
}

.invalidation-details[open] summary::before {
  content: '▼ ';
}

.invalidation-details .condition-list li {
  color: #888;
  font-size: 12px;
}

/* 备用策略 */
.standby-section {
  margin-top: 8px;
}

.standby-details {
  font-size: 13px;
}

.standby-details summary {
  cursor: pointer;
  font-weight: 600;
  color: #999;
  margin-bottom: 6px;
  list-style: none;
  padding: 0;
}

.standby-details summary::-webkit-details-marker {
  display: none;
}

.standby-details summary::before {
  content: '▶ ';
  margin-right: 4px;
}

.standby-details[open] summary::before {
  content: '▼ ';
}

.standby-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.standby-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: rgba(120, 123, 134, 0.05);
  border-radius: 4px;
  font-size: 12px;
}

.standby-item.up {
  color: #089981;
}

.standby-item.down {
  color: #F23645;
}

.standby-item.range {
  color: #787B86;
}

.standby-direction {
  font-weight: 600;
}

.standby-conditions {
  color: #666;
  font-size: 11px;
}
</style>
