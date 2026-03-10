<template>
  <div class="ai-panel" :class="{ loading: analyzing }">
    <!-- 面板头部 -->
    <div class="panel-header doodle-header">
      <div class="header-left">
        <span class="header-icon">📊</span>
        <h2>AI 分析</h2>
      </div>
      <div class="header-controls">
        <!-- 币种选择 -->
        <select v-model="localSymbol" @change="onSymbolChange" class="control-select">
          <option value="BTCUSDT">BTC</option>
          <option value="ETHUSDT">ETH</option>
        </select>
        <!-- 周期选择 -->
        <select v-model="localInterval" @change="onIntervalChange" class="control-select">
          <option value="15m">15分</option>
          <option value="1h">1小时</option>
          <option value="4h">4小时</option>
          <option value="1d">1天</option>
        </select>
        <!-- 模式选择 -->
        <select v-model="localMode" @change="onModeChange" class="control-select mode-select">
          <option value="structured">结构化</option>
          <option value="table">表格</option>
        </select>
        <!-- AI Provider 选择 -->
        <select v-model="localProvider" @change="onProviderChange" class="control-select provider-select">
          <option v-for="p in providerOptions" :key="p.value" :value="p.value">
            🤖 {{ p.label }}
          </option>
        </select>
        <!-- API Key 按钮 -->
        <button @click="toggleApiKeyInput" class="api-key-btn" :class="{ 'has-key': !!localApiKey }" :title="localApiKey ? 'API Key 已设置' : '设置 API Key'">
          {{ localApiKey ? '🔑' : '➕🔑' }}
        </button>
      </div>
    </div>

    <!-- 操作按钮区 -->
    <div class="panel-actions">
      <button @click="$emit('analyze')" :disabled="analyzing" class="analyze-btn doodle-btn" style="font-family: 'Patrick Hand', 'Caveat', cursive; font-weight: 700;">
        <span class="btn-icon">🔍</span>
        {{ analyzing ? '分析中...' : '开始分析' }}
      </button>
      <button @click="$emit('show-history')" class="history-btn doodle-btn-secondary" style="font-family: 'Patrick Hand', 'Caveat', cursive; font-weight: 700;">
        <span class="btn-icon">📜</span>
        记录
      </button>
    </div>

    <!-- 内容区 -->
    <div class="panel-content">
      <!-- 加载状态 - 带进度条和日志 -->
      <div v-if="analyzing" class="panel-analyzing">
        <!-- 进度条 -->
        <div class="progress-section">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progress + '%' }"></div>
          </div>
          <div class="progress-label">{{ Math.round(progress) }}%</div>
        </div>

        <!-- 日志容器 -->
        <div class="log-container" ref="logContainer">
          <div v-for="(log, index) in progressLogs" :key="index"
               class="log-line"
               :class="log.level">
            {{ log.message }}
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!result" class="panel-empty">
        <span class="empty-icon">📋</span>
        <p>点击「开始分析」获取策略建议</p>
      </div>

      <!-- 结构化输出 -->
      <div v-else-if="localMode === 'structured'" class="structured-content">
        <!-- 状态机策略 -->
        <div v-if="hasStateMachine" class="result-section state-machine-section">
          <h4>状态机策略</h4>
          <StateMachineCard :data="(result as AIStructuredResult).state_machine!" />
        </div>

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
            <span class="scenario-direction" :class="getPrimaryScenarioData()?.direction || getPrimaryScenarioData()?.type">
              {{ getPrimaryScenarioLabel() }}
            </span>
            <span class="scenario-prob" :class="getPrimaryScenarioData()?.direction || getPrimaryScenarioData()?.type">
              {{ formatPercentage(getPrimaryScenarioData()?.probability) }}
            </span>
          </div>
          <div class="scenario-details">
            <div class="detail-row">
              <span class="detail-label">入场</span>
              <span class="detail-value">{{ getPrimaryEntry() }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">目标</span>
              <span class="detail-value target">{{ getPrimaryTarget() }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">止损</span>
              <span class="detail-value stop">{{ getPrimaryStop() }}</span>
            </div>
            <div v-if="getPrimaryTrigger()" class="detail-row">
              <span class="detail-label">触发</span>
              <span class="detail-value">{{ getPrimaryTrigger() }}</span>
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
                <span class="detail-value">{{ getScenarioEntry(scenario) }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">目标</span>
                <span class="detail-value">{{ getScenarioTarget(scenario) }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">止损</span>
                <span class="detail-value">{{ getScenarioStop(scenario) }}</span>
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

      <!-- 表格输出 -->
      <div v-else-if="localMode === 'table'" class="table-content">
        <!-- 原始 Markdown 输出 -->
        <div v-if="isTableResult(result)" class="markdown-content" v-html="renderMarkdown(markdownContent)"></div>

        <!-- 兼容旧版：如果没有 table 格式，显示结构化数据的表格视图 -->
        <template v-else-if="isStructuredResult(result) && result.scenarios">
          <table class="strategy-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>方向</th>
                <th>概率</th>
                <th>入场价</th>
                <th>目标价</th>
                <th>止损价</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="scenario in result.scenarios" :key="scenario.rank" :class="scenario.direction || scenario.type">
                <td>{{ scenario.rank }}</td>
                <td>{{ getDirectionLabel(scenario.direction || scenario.type) }}</td>
                <td>{{ formatPercentage(scenario.probability) }}</td>
                <td>{{ getScenarioEntry(scenario) }}</td>
                <td class="target">{{ getScenarioTarget(scenario) }}</td>
                <td class="stop">{{ getScenarioStop(scenario) }}</td>
              </tr>
            </tbody>
          </table>

          <!-- 风险提示 -->
          <div v-if="result.risk_notes && result.risk_notes.length" class="result-section risk-notes">
            <h4>风险提示</h4>
            <ul>
              <li v-for="(note, i) in result.risk_notes.slice(0, 3)" :key="i">{{ note }}</li>
            </ul>
          </div>
        </template>
      </div>
    </div>

    <!-- API Key 输入弹窗 -->
    <Teleport to="body">
      <div v-if="showApiKeyInput" class="api-key-modal-overlay" @click.self="cancelApiKeyInput">
        <div class="api-key-modal">
          <h3>🔑 API Key 设置</h3>
          <p class="provider-label">{{ getCurrentProviderLabel() }}</p>
          <input
            v-model="localApiKey"
            type="password"
            placeholder="请输入 API Key"
            class="api-key-input"
            @keyup.enter="saveApiKey"
          />
          <div class="api-key-actions">
            <button @click="saveApiKey" class="save-btn">保存</button>
            <button @click="cancelApiKeyInput" class="cancel-btn">取消</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onUnmounted } from 'vue';
import type { AIAnalysisResult, AITableResult, AIStructuredResult } from '@/types/chanlun';
import StateMachineCard from './StateMachineCard.vue';

const props = defineProps<{
  symbol?: string;
  interval?: string;
  result?: AIAnalysisResult | null;
  analyzing?: boolean;
  mode?: 'structured' | 'table';
  // 新增：AI 配置
  aiProvider?: string;
  aiModel?: string;
  apiKey?: string;
}>();

const emit = defineEmits<{
  (e: 'analyze'): void;
  (e: 'update:mode', value: 'structured' | 'table'): void;
  (e: 'update:symbol', value: string): void;
  (e: 'update:interval', value: string): void;
  (e: 'show-history'): void;
  (e: 'analysis-complete', result: AIAnalysisResult): void;
  // 新增：AI 配置事件
  (e: 'update:aiProvider', value: string): void;
  (e: 'update:aiModel', value: string): void;
  (e: 'update:apiKey', value: string): void;
}>();

const localSymbol = ref(props.symbol || 'BTCUSDT');
const localInterval = ref(props.interval || '1h');
const localMode = ref(props.mode || 'structured');
// 新增：AI 配置本地状态
const localProvider = ref(props.aiProvider || 'siliconflow');
const localModel = ref(props.aiModel || 'Pro/deepseek-ai/DeepSeek-V3.2');
const localApiKey = ref(props.apiKey || '');
const showApiKeyInput = ref(false);

// Provider 选项配置
const providerOptions = [
  { value: 'siliconflow', label: 'SiliconFlow' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'anthropic', label: 'Anthropic' }
];

// 进度条相关
const progress = ref(0);
const progressLogs = ref<Array<{level: string, message: string}>>([]);
const logContainer = ref<HTMLElement | null>(null);

// 虚假进度条相关
let progressInterval: number | null = null;
let currentLogIndex = 0;

// 生成动态日志（根据实际币种和周期）
function generateMockLogs(symbol: string, interval: string): Array<{type: string, text: string}> {
  const displaySymbol = symbol.replace('USDT', '/USDT');
  const intervalDisplay = interval;

  return [
    { type: 'step', text: `🚀 开始分析 ${displaySymbol} @ ${intervalDisplay} (1000 根K线)` },
    { type: 'divider', text: '============================================================' },
    { type: 'step', text: '📊 步骤 1/5: 获取 Binance K 线数据...' },
    { type: 'success', text: '   ✓ 获取到 1000 根 K 线' },
    { type: 'step', text: '🧮 步骤 2/5: 缠论结构计算...' },
    { type: 'success', text: '   ✓ 缠论计算完成' },
    { type: 'step', text: '📦 步骤 3/5: 构造 AI 输入数据...' },
    { type: 'success', text: '   ✓ 数据构造完成' },
    { type: 'divider', text: '============================================================' },
    { type: 'info', text: `【${displaySymbol} · ${intervalDisplay} 缠论结构快览】` },
    { type: 'divider', text: '============================================================' },
    { type: 'info', text: '💰 当前价格：计算中...' },
    { type: 'info', text: '🧱 中枢信息分析中...' },
    { type: 'info', text: '📊 最新笔分析中...' },
    { type: 'info', text: '🚨 近期信号分析中...' },
    { type: 'info', text: '📈 结构统计中...' },
    { type: 'divider', text: '============================================================' },
    { type: 'step', text: '🤖 步骤 4/5: 调用 AI 进行分析...' },
    { type: 'divider', text: '============================================================' },
    { type: 'info', text: '⚙️  配置信息：' },
    { type: 'info', text: '   Provider: siliconflow' },
    { type: 'info', text: '   Model: Pro/deepseek-ai/DeepSeek-V3.2' },
    { type: 'info', text: '   Temperature: 0.3' },
    { type: 'info', text: '   Max Tokens: 2800' },
    { type: 'divider', text: '============================================================' },
    { type: 'step', text: '📈 步骤 4.5/6: 获取历史统计数据...' },
    { type: 'divider', text: '============================================================' },
    { type: 'success', text: '   ✓ 已加载历史记录' },
    { type: 'success', text: '   ✓ 整体命中率计算中' },
    { type: 'success', text: '   ✓ 平均得分计算中' },
    { type: 'info', text: '   🔍 查找相似案例...' },
    { type: 'info', text: '   📈 相似案例胜率分析中' },
    { type: 'info', text: '   💡 历史建议生成中' },
    { type: 'info', text: '   🧠 AI自我认知分析中' },
    { type: 'info', text: '   🔒 使用结构化 Prompt（强制 JSON 输出）' },
    { type: 'info', text: '   📊 已注入历史统计数据' },
    { type: 'info', text: '   📚 已注入相似案例分析' },
    { type: 'info', text: '   🧠 已注入AI自我认知' },
    { type: 'info', text: '   ...' },
    { type: 'step', text: '   ⏳ 等待 AI 响应（可能需要20-60 秒）...' },
    { type: 'success', text: '   ✓ AI 分析完成' },
    { type: 'info', text: '   🔍 验证 JSON 输出...' },
    { type: 'success', text: '   ✓ JSON 验证通过' },
    { type: 'info', text: '   🔍 校验条件检查中...' },
    { type: 'info', text: '   🔍 执行预测校验...' },
    { type: 'info', text: '📋 预测校验与调整：' },
    { type: 'info', text: '   ✅ 预测校验完成' },
    { type: 'info', text: '   🔧 逻辑检查中...' },
    { type: 'info', text: '   🔧 已应用自动修复（如有需要）' },
    { type: 'info', text: '   🎯 置信度约束已应用' },
    { type: 'info', text: '   🔄 已生成状态机格式' },
    { type: 'success', text: '   💾 已保存分析快照' },
  ];
}

// 当前使用的日志列表
let mockLogs: Array<{type: string, text: string}> = [];

// 启动进度条和日志模拟
function startProgressSimulation() {
  progress.value = 0;
  progressLogs.value = [];
  currentLogIndex = 0;

  // 根据当前币种和周期生成动态日志
  mockLogs = generateMockLogs(localSymbol.value, localInterval.value);

  // 55-60秒完成，每100ms更新一次
  const totalDuration = 55000; // 58秒（在55-60秒范围内）
  const updateInterval = 100;
  const progressStep = (updateInterval / totalDuration) * 100;

  // 进度条定时器
  progressInterval = window.setInterval(() => {
    if (progress.value < 99) {
      progress.value = Math.min(progress.value + progressStep, 99);
    }

    // 添加日志（模拟真实的分析步骤）
    addNextLog();
  }, updateInterval);
}

function addNextLog() {
  // 每隔一定时间添加一条日志，使日志在分析过程中逐步显示
  // 总时间约 55 秒，共 58 条日志，大约每秒添加 1 条
  // 但定时器每 100ms 执行一次，所以每 10 次执行添加一条日志
  if (progressInterval && Math.random() < 0.12) {  // 约 1.2% 的概率每次执行时添加日志
    if (currentLogIndex >= mockLogs.length) return;

    const log = mockLogs[currentLogIndex];
    progressLogs.value.push({
      level: log.type,
      message: log.text
    });

    // 自动滚动到底部
    setTimeout(() => {
      if (logContainer.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight;
      }
    }, 10);

    currentLogIndex++;
  }
}

// 停止进度模拟
function stopProgressSimulation() {
  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }
  progress.value = 100;
}

// 监听 analyzing 状态
watch(() => props.analyzing, (newVal) => {
  if (newVal) {
    startProgressSimulation();
  } else {
    // 添加完成日志
    progressLogs.value.push({
      level: 'success',
      message: '✅ 分析完成！'
    });
    // 滚动到底部
    setTimeout(() => {
      if (logContainer.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight;
      }
    }, 10);

    // 停止进度条并跳到 100%
    stopProgressSimulation();

    // 延迟清空日志
    setTimeout(() => {
      progressLogs.value = [];
      progress.value = 0;
    }, 2000);
  }
});

// 组件卸载时清理
onUnmounted(() => {
  stopProgressSimulation();
});

// 类型守卫：判断是否为 table 模式结果
function isTableResult(result: AIAnalysisResult | null | undefined): result is AITableResult {
  return result !== null && result !== undefined && 'mode' in result && result.mode === 'table';
}

// 类型守卫：判断是否为 structured 模式结果
function isStructuredResult(result: AIAnalysisResult | null | undefined): result is AIStructuredResult {
  return result !== null && result !== undefined && (!('mode' in result) || result.mode !== 'table');
}

// 判断是否有状态机数据
const hasStateMachine = computed(() => {
  return isStructuredResult(props.result) && props.result.state_machine;
});

// 获取 Markdown 内容（用于 table 模式）
const markdownContent = computed(() => {
  if (isTableResult(props.result)) {
    return props.result.content;
  }
  return '';
});

// 简单的 Markdown 到 HTML 转换函数
function renderMarkdown(markdown: string): string {
  if (!markdown) return '';

  let html = markdown
    // 转义 HTML 特殊字符
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // 标题
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    // 加粗
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    // 斜体
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    // 代码块
    .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    // 行内代码
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // 链接
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
    // 无序列表
    .replace(/^\- (.*$)/gim, '<li>$1</li>')
    .replace(/^(\d+)\. (.*$)/gim, '<li>$2</li>')
    // 换行
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');

  // 包裹列表项
  html = html.replace(/(<li>.*<\/li>)/g, '<ul>$1</ul>');
  // 合并相邻的 ul
  html = html.replace(/<\/ul><br><ul>/g, '');
  // 添加段落包裹
  html = '<p>' + html + '</p>';

  return html;
}

watch(() => props.symbol, (newVal) => {
  if (newVal) localSymbol.value = newVal;
});

watch(() => props.interval, (newVal) => {
  if (newVal) localInterval.value = newVal;
});

watch(() => props.mode, (newVal) => {
  if (newVal) localMode.value = newVal;
});

function onSymbolChange() {
  emit('update:symbol', localSymbol.value);
}

function onIntervalChange() {
  emit('update:interval', localInterval.value);
}

function onModeChange() {
  emit('update:mode', localMode.value);
}

// AI Provider 变更
function onProviderChange() {
  emit('update:aiProvider', localProvider.value);
  // 切换 provider 时可以更新默认模型
  const defaultModels: Record<string, string> = {
    'siliconflow': 'Pro/deepseek-ai/DeepSeek-V3.2',
    'openrouter': 'anthropic/claude-3.5-sonnet',
    'deepseek': 'deepseek-reasoner',
    'anthropic': 'claude-3-5-sonnet-20241022'
  };
  localModel.value = defaultModels[localProvider.value] || localModel.value;
  emit('update:aiModel', localModel.value);
}

// 切换 API Key 输入框
function toggleApiKeyInput() {
  showApiKeyInput.value = !showApiKeyInput.value;
}

// 保存 API Key
function saveApiKey() {
  emit('update:apiKey', localApiKey.value);
  showApiKeyInput.value = false;
}

// 取消 API Key 输入
function cancelApiKeyInput() {
  showApiKeyInput.value = false;
}

// 获取当前 Provider 标签
function getCurrentProviderLabel(): string {
  const provider = providerOptions.find(p => p.value === localProvider.value);
  return provider ? provider.label : '';
}

function getCurrentPrice(): number {
  return props.result?.meta?.price || 0;
}

function formatPrice(price: number): string {
  if (!price || price === 0) return '-';
  return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatPercentage(value: number | undefined): string {
  if (value === undefined || value === null) return '-';
  const displayValue = value <= 1 ? value * 100 : value;
  return `${displayValue.toFixed(1)}%`;
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

function getScenarioEntry(scenario: any): string {
  // 优先使用 entry_range
  if (scenario.entry_range && Array.isArray(scenario.entry_range) && scenario.entry_range.length === 2) {
    const [low, high] = scenario.entry_range;
    const current = getCurrentPrice();
    const direction = scenario.direction || scenario.type;

    // 构建详细说明
    let note = '';
    if (direction === 'up' || direction === 'long') {
      if (high < current) note = '（当前价下方）';
      else if (low > current) note = '（当前价上方）';
      else note = '（当前价附近）';
    } else if (direction === 'down' || direction === 'short') {
      if (low > current) note = '（当前价上方）';
      else if (high < current) note = '（当前价下方）';
      else note = '（当前价附近）';
    } else {
      note = '（震荡区间内）';
    }

    return `${formatPrice(low)}-${formatPrice(high)}${note}`;
  }
  if (scenario.entry) return formatPrice(scenario.entry);
  if (scenario.target_range && Array.isArray(scenario.target_range) && scenario.target_range.length === 2) {
    const direction = scenario.direction;
    if (direction === 'up') {
      return formatPrice(scenario.target_range[0]);
    } else if (direction === 'down') {
      return formatPrice(scenario.target_range[1]);
    } else {
      return formatPrice(getCurrentPrice());
    }
  }
  return '-';
}

function getScenarioTarget(scenario: any): string {
  // 优先使用 target_range 并显示完整区间
  if (scenario.target_range && Array.isArray(scenario.target_range) && scenario.target_range.length === 2) {
    const [low, high] = scenario.target_range;
    return `${formatPrice(low)}-${formatPrice(high)}`;
  }
  if (scenario.target) return formatPrice(scenario.target);
  if (scenario.target_pct) return formatPrice(calculateTarget(scenario));
  return '-';
}

function getScenarioStop(scenario: any): string {
  // 优先使用 stop
  if (scenario.stop) {
    let note = getStopNote(scenario);
    return `${formatPrice(scenario.stop)}${note ? `（${note}）` : ''}`;
  }
  if (scenario.stop_pct) {
    const stop = calculateStop(scenario);
    let note = getStopNote(scenario);
    return `${formatPrice(stop)}${note ? `（${note}）` : ''}`;
  }
  // 从 target_range 推算止损
  if (scenario.target_range && Array.isArray(scenario.target_range) && scenario.target_range.length === 2) {
    const current = getCurrentPrice();
    const direction = scenario.direction;
    const rangeSize = scenario.target_range[1] - scenario.target_range[0];
    if (direction === 'up') {
      const entry = scenario.target_range[0];
      const stop = entry - rangeSize * 0.3;
      return `${formatPrice(stop)}（跌破近期低点）`;
    } else if (direction === 'down') {
      const entry = scenario.target_range[1];
      const stop = entry + rangeSize * 0.3;
      return `${formatPrice(stop)}（有效突破ZD则止损）`;
    }
  }
  return '-';
}

// 获取止损说明
function getStopNote(scenario: any): string {
  const direction = scenario.direction || scenario.type;
  const current = getCurrentPrice();
  const stop = scenario.stop || calculateStop(scenario);

  // 根据方向和价格关系给出说明
  if (direction === 'up' || direction === 'long') {
    if (stop < current) return '跌破近期低点';
    return '止损位';
  } else if (direction === 'down' || direction === 'short') {
    if (stop > current) return '有效突破ZD则止损';
    return '止损位';
  }
  return '止损';
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
  if (dir === 'up' || dir === 'long') return '做多';
  if (dir === 'down' || dir === 'short') return '做空';
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

// 获取主推策略数据（优先使用 scenarios 中 rank=1 的）
function getPrimaryScenarioData(): any {
  if (!isStructuredResult(props.result)) {
    return null;
  }
  if (!props.result.scenarios || props.result.scenarios.length === 0) {
    return props.result.primary_scenario;
  }
  // 返回 rank=1 的场景
  return props.result.scenarios.find((s: any) => s.rank === 1) || props.result.scenarios[0];
}

// 获取主推策略标签
function getPrimaryScenarioLabel(): string {
  const scenario = getPrimaryScenarioData();
  if (!scenario) return '-';
  return getScenarioLabel(scenario.direction || scenario.type);
}

// 获取主推策略的入场价
function getPrimaryEntry(): string {
  const scenario = getPrimaryScenarioData();
  if (scenario) {
    return getScenarioEntry(scenario);
  }
  // fallback: 使用 primary_scenario 的 trigger 或当前价格
  const trigger = props.result?.primary_scenario?.trigger;
  const current = getCurrentPrice();
  if (trigger) return trigger;
  return formatPrice(current);
}

// 获取主推策略的目标价
function getPrimaryTarget(): string {
  const scenario = getPrimaryScenarioData();
  if (scenario) {
    return getScenarioTarget(scenario);
  }
  // fallback: 使用 primary_scenario 的 target_pct 计算
  const primary = props.result?.primary_scenario;
  if (primary?.target_pct) {
    return formatPrice(calculateTarget(primary));
  }
  return '-';
}

// 获取主推策略的止损价
function getPrimaryStop(): string {
  const scenario = getPrimaryScenarioData();
  if (scenario) {
    return getScenarioStop(scenario);
  }
  // fallback: 使用 primary_scenario 的 stop_pct 计算
  const primary = props.result?.primary_scenario;
  if (primary?.stop_pct) {
    return formatPrice(calculateStop(primary));
  }
  return '-';
}

// 获取主推策略的触发条件
function getPrimaryTrigger(): string {
  const scenario = getPrimaryScenarioData();
  if (scenario) {
    return scenario.trigger || scenario.reason || scenario.logic || '';
  }
  return props.result?.primary_scenario?.trigger || '';
}
</script>

<style scoped>
.ai-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #F9F3E3;
}

/* 面板头部 - 涂鸦风格 */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #FFF8DC;
  border-bottom: 3px solid #2C2C2C;
  flex-wrap: wrap;
  gap: 8px;
}

.doodle-header {
  font-family: 'Patrick Hand', 'Caveat', cursive;
  background: #FFF8DC;
  border: 3px solid #2C2C2C;
  border-radius: 12px 4px 10px 6px / 6px 10px 4px 12px;
  margin: 8px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.header-icon {
  font-size: 18px;
}

.panel-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #2C2C2C;
}

.header-controls {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}

.control-select {
  padding: 5px 8px;
  font-size: 16px;
  font-weight: 600;
  font-family: 'Patrick Hand', 'Caveat', cursive;
  color: #131722;
  background: #F8F9FD;
  border: 2px solid #2C2C2C;
  border-radius: 5px 2px 4px 3px / 3px 4px 2px 5px;
  cursor: pointer;
  outline: none;
}

.control-select.mode-select {
  background: #FFE0B2;
}

/* 操作按钮区 */
.panel-actions {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  background: #F9F3E3;
}

.doodle-btn {
  font-family: 'Patrick Hand', 'Caveat', cursive !important;
  font-size: 16px;
  padding: 8px 16px;
  background: #FFE0B2;
  border: 2px solid #2C2C2C;
  border-radius: 6px 2px 5px 3px / 3px 5px 2px 6px;
  color: #2C2C2C;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 2px 2px 0 #2C2C2C;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 记录按钮单独样式 */
.doodle-btn-secondary {
  font-family: 'Patrick Hand', 'Caveat', cursive !important;
  font-size: 16px;
  background: #FFFFFF;
  min-width: 100px;
  justify-content: center;
}

.doodle-btn:hover:not(:disabled) {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 #2C2C2C;
  background: #FFCC80;
}

.doodle-btn:active:not(:disabled) {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 #2C2C2C;
}

.doodle-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.doodle-btn-secondary {
  background: #FFFFFF;
}

.doodle-btn-secondary:hover:not(:disabled) {
  background: #F8F9FD;
}

.btn-icon {
  font-size: 16px;
}

/* 内容区 */
.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

/* 加载和空状态 */
.panel-analyzing {
  display: flex;
  flex-direction: column;
  padding: 16px;
  gap: 16px;
}

.panel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #666;
}

.panel-empty p {
  margin-top: 12px;
  font-size: 14px;
}

.empty-icon {
  font-size: 40px;
}

.doodle-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #E0E3EB;
  border-top-color: #2C2C2C;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 结果内容 */
.structured-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-section {
  padding: 12px;
  background: #FFF8DC;
  border: 2px solid #D4C4A8;
  border-radius: 10px 4px 8px 5px / 5px 8px 4px 10px;
}

.result-section h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  font-weight: 700;
  color: #2C2C2C;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}

.label {
  font-size: 13px;
  color: #666;
}

.value {
  font-size: 14px;
  font-weight: 600;
  color: #2C2C2C;
}

.trend-badge {
  padding: 3px 10px;
  border-radius: 5px 2px 4px 4px / 4px 4px 2px 5px;
  font-size: 12px;
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
  margin-bottom: 10px;
}

.scenario-direction {
  font-size: 14px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 4px 2px 3px 2px / 2px 3px 2px 4px;
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
  font-size: 18px;
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
  gap: 4px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
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
  padding-top: 6px;
  border-top: 2px dashed rgba(0, 0, 0, 0.1);
}

.scenario-card {
  padding: 10px;
  background: #FFFFFF;
  border-radius: 6px;
  margin-bottom: 8px;
  border-left: 3px solid #D4C4A8;
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
  font-size: 14px;
  font-weight: 600;
  color: #2C2C2C;
}

.scenario-card .scenario-details {
  margin-top: 6px;
}

.analysis-text {
  font-size: 13px;
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
  padding-left: 18px;
}

.risk-notes li {
  font-size: 12px;
  color: #666;
  line-height: 1.5;
  margin-bottom: 4px;
}

/* 状态机区域样式 */
.state-machine-section {
  background: rgba(41, 98, 255, 0.05) !important;
  border-color: #2962FF !important;
}

.state-machine-section h4 {
  color: #2962FF;
}

/* 表格样式 */
.table-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.strategy-table {
  width: 100%;
  border-collapse: collapse;
  background: #FFFFFF;
  border: 2px solid #2C2C2C;
  border-radius: 8px 3px 6px 4px / 4px 6px 3px 8px;
  overflow: hidden;
  font-size: 12px;
}

.strategy-table thead {
  background: #2C2C2C;
  color: #FFF8DC;
}

.strategy-table th {
  padding: 8px 6px;
  text-align: center;
  font-size: 12px;
  font-weight: 600;
}

.strategy-table td {
  padding: 6px 4px;
  text-align: center;
  font-size: 12px;
  border-bottom: 1px solid #E0E3EB;
}

.strategy-table tbody tr:last-child td {
  border-bottom: none;
}

.strategy-table tbody tr.up,
.strategy-table tbody tr.long {
  background: rgba(8, 153, 129, 0.05);
}

.strategy-table tbody tr.down,
.strategy-table tbody tr.short {
  background: rgba(242, 54, 69, 0.05);
}

.strategy-table tbody tr.range {
  background: rgba(120, 123, 134, 0.05);
}

.strategy-table td.target {
  color: #089981;
  font-weight: 600;
}

.strategy-table td.stop {
  color: #F23645;
  font-weight: 600;
}

/* 滚动条样式 */
.panel-content::-webkit-scrollbar {
  width: 6px;
}

.panel-content::-webkit-scrollbar-track {
  background: #F9F3E3;
  border-radius: 3px;
}

.panel-content::-webkit-scrollbar-thumb {
  background: #D4C4A8;
  border-radius: 3px;
  border: 1px solid #2C2C2C;
}

.panel-content::-webkit-scrollbar-thumb:hover {
  background: #BCAAA4;
}

/* Markdown 内容样式 */
.markdown-content {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 15px;
  line-height: 1.6;
  color: #2C2C2C;
}

.markdown-content h1,
.markdown-content h2,
.markdown-content h3 {
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 700;
  color: #2C2C2C;
}

.markdown-content h1 {
  font-size: 18px;
  border-bottom: 2px solid #D4C4A8;
  padding-bottom: 6px;
}

.markdown-content h2 {
  font-size: 16px;
}

.markdown-content h3 {
  font-size: 14px;
}

.markdown-content p {
  margin-bottom: 10px;
}

.markdown-content strong {
  color: #2C2C2C;
  font-weight: 600;
}

.markdown-content ul {
  margin: 8px 0;
  padding-left: 20px;
}

.markdown-content li {
  margin-bottom: 4px;
  color: #444;
}

.markdown-content code {
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 4px;
  border-radius: 3px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: #D32F2F;
}

.markdown-content pre {
  background: #2C2C2C;
  color: #FFF8DC;
  padding: 10px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 10px 0;
}

.markdown-content pre code {
  background: transparent;
  color: inherit;
  padding: 0;
}

.markdown-content a {
  color: #2962FF;
  text-decoration: none;
}

.markdown-content a:hover {
  text-decoration: underline;
}

/* 进度条样式 */
.progress-section {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 8px;
  border-bottom: 2px dashed rgba(80, 60, 40, 0.2);
}

.progress-bar {
  flex: 1;
  height: 20px;
  background: #E5D8C2;
  border-radius: 6px;
  border: 2px dashed rgba(80, 60, 40, 0.3);
  overflow: hidden;
  position: relative;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3FB950, #2EA043);
  border-right: 2px dashed #3F5E2E;
  transition: width 0.3s ease-out;
}

.progress-label {
  font-size: 14px;
  font-weight: 600;
  color: #5E4B38;
  min-width: 40px;
  text-align: right;
}

/* 日志容器样式 */
.log-container {
  background: rgba(240, 230, 210, 0.5);
  border-radius: 8px;
  padding: 12px;
  max-height: 300px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.5;
  color: #3A332B;
}

.log-container::-webkit-scrollbar {
  width: 8px;
}

.log-container::-webkit-scrollbar-track {
  background: #E5D8C2;
  border-radius: 4px;
}

.log-container::-webkit-scrollbar-thumb {
  background: #B7A48B;
  border-radius: 4px;
}

.log-line {
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 4px;
  padding-left: 10px;
  border-left: 3px solid;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.log-line.step {
  border-left-color: #C57C5C;
  font-weight: 600;
}

.log-line.success {
  border-left-color: #7FB07C;
  color: #2d5a2d;
}

.log-line.info {
  border-left-color: #7C9FB0;
}

.log-line.warning {
  border-left-color: #D9A066;
}

.log-line.error {
  border-left-color: #F23645;
  color: #c53030;
}

.log-line.divider {
  border-left: none;
  color: #B7A48B;
  font-size: 11px;
  margin: 8px 0;
  padding-left: 0;
  letter-spacing: 1px;
}

/* Provider 选择器样式 */
.provider-select {
  background: #E8F4FD !important;
}

/* API Key 按钮样式 */
.api-key-btn {
  padding: 5px 10px;
  background: #F8F9FD;
  border: 2px solid #2C2C2C;
  border-radius: 5px 2px 4px 3px / 3px 4px 2px 5px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
}

.api-key-btn:hover {
  background: #FFE0B2;
  transform: translate(-1px, -1px);
}

.api-key-btn.has-key {
  background: #C8E6C9;
}

/* API Key 弹窗样式 */
.api-key-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.api-key-modal {
  background: #FFF8DC;
  border: 3px solid #2C2C2C;
  border-radius: 12px 4px 10px 6px / 6px 10px 4px 12px;
  padding: 20px;
  min-width: 320px;
  text-align: center;
  font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", "微软雅黑", "Segoe UI", Roboto, sans-serif;
}

.api-key-modal h3 {
  margin: 0 0 5px 0;
  font-size: 16px;
  color: #2C2C2C;
}

.provider-label {
  color: #666;
  margin-bottom: 15px;
  font-size: 14px;
}

.api-key-input {
  width: 100%;
  padding: 10px;
  border: 2px solid #2C2C2C;
  border-radius: 5px;
  font-size: 14px;
  margin-bottom: 15px;
  box-sizing: border-box;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
}

.api-key-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}

.save-btn, .cancel-btn {
  padding: 8px 24px;
  border: 2px solid #2C2C2C;
  border-radius: 5px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.15s;
}

.save-btn {
  background: #FFE0B2;
}

.save-btn:hover {
  background: #FFCC80;
  transform: translate(-1px, -1px);
}

.cancel-btn {
  background: #FFFFFF;
}

.cancel-btn:hover {
  background: #F8F9FD;
}
</style>

<!-- 非scoped样式：强制按钮字体 -->
<style>
.ai-panel .doodle-btn,
.ai-panel .doodle-btn-secondary {
  font-family: 'Patrick Hand', 'Caveat', cursive !important;
}
</style>
