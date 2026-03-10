// 缠论数据类型定义

export interface KlineData {
  date: string;
  o: number;
  h: number;
  l: number;
  c: number;
  a?: number;
}

export interface BiData {
  index: number;
  type: 'up' | 'down';
  start_price: number;
  end_price: number;
  start_date: string;
  end_date: string;
  buy_sell_point?: string;
  divergence?: string;
  is_done?: boolean;
}

export interface XdData {
  index: number;
  type: 'up' | 'down';
  start_price: number;
  end_price: number;
  start_date: string;
  end_date: string;
  buy_sell_point?: string;
  divergence?: string;
  is_done?: boolean;
}

export interface ZsData {
  zg: number;
  zd: number;
  gg: number;
  dd: number;
}

export interface FxData {
  index: number;
  type: 'ding' | 'di';
  price: number;
  date: string;
}

export interface ChanlunData {
  meta: {
    symbol: string;
    interval: string;
    count: number;
  };
  klines: KlineData[];
  bi: BiData[];
  xd: XdData[];
  zs: ZsData[];
  fx: FxData[];
}

// AI 分析结果类型 - 表格模式（Markdown）
export interface AITableResult {
  mode: 'table';
  content: string;  // Markdown 格式的分析文本
  meta: {
    symbol: string;
    interval: string;
    price: number;
  };
}

// AI 分析结果类型 - 结构化模式（JSON）
export interface ScenarioData {
  rank: number;
  probability: number;
  direction: 'up' | 'down' | 'range';
  target_range?: [number, number];
  target_pct?: number;
  stop_pct?: number;
  entry?: number;
  target?: number;
  stop?: number;
  trigger?: string;
  reasoning?: string;
  logic?: string;
  reason?: string;
  type?: 'long' | 'short' | 'range';
}

export interface StructureJudgment {
  trend: string;
  price_position: string;
  zs?: {
    zg: number;
    zd: number;
    gg: number;
    dd: number;
  };
  latest_bi?: {
    direction: string;
    is_done: boolean;
  };
  latest_xd?: {
    direction: string;
    is_done: boolean;
  };
}

export interface AIStructuredResult {
  mode?: 'structured';
  meta: {
    symbol: string;
    interval: string;
    price: number;
    timestamp?: string;
  };
  structure_judgement?: StructureJudgment;
  signals?: {
    buy_sell_points?: string[];
    divergences?: string[];
    bi?: string;
    direction?: string;
  };
  primary_scenario?: {
    direction: 'up' | 'down' | 'range';
    target_pct: number;
    stop_pct: number;
    probability: number;
    trigger?: string;
    reasoning?: string;
  };
  scenarios: ScenarioData[];
  analysis?: string;
  risk_notes?: string[];
  structure?: string;
  position?: string;
  pivot?: [number, number];

  // v2.0 新增：状态机数据
  state_machine?: StateMachineData;
  version?: string;
  output_mode?: 'scenarios' | 'state_machine';
}

// AI 分析结果类型 - 联合类型
export type AIAnalysisResult = AIStructuredResult | AITableResult;

// 周期类型
export type IntervalType = '15m' | '1h' | '4h' | '1d';

// 交易对类型
export type SymbolType = 'BTCUSDT' | 'ETHUSDT' | string;

// ============================================
// v2.0 新增：状态机类型定义
// ============================================

export type StateValue = 'STRATEGY_ACTIVE' | 'WAIT_CONFIRMATION' | 'OBSERVE_ONLY';
export type StrategyStatus = 'WAIT' | 'READY' | 'ACTIVE' | 'INVALIDATED';

export interface EntryGate {
  price_zone: [number, number];
  structure_required: string[];
}

export interface ExecutionParams {
  entry_type: 'market' | 'limit' | 'split';
  stop_loss: number;
  target: number;
  rr: number;
}

export interface ActiveStrategy {
  direction: 'up' | 'down';
  status: StrategyStatus;
  entry_gate: EntryGate;
  execution: ExecutionParams;
}

export interface Invalidation {
  invalidate_active_if: string[];
  next_state: string;
}

export interface StandbyStrategy {
  direction: 'up' | 'down' | 'range';
  activate_if: string[];
}

export interface StateMachineData {
  current_state: StateValue;
  active_strategy: ActiveStrategy;
  invalidation: Invalidation;
  standby_strategies?: StandbyStrategy[];
}

// 扩展 ScenarioData 接口，支持 entry_range
export interface ScenarioDataExtended extends ScenarioData {
  entry_range?: [number, number];
}
