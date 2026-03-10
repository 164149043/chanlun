# -*- coding: utf-8 -*-
"""AI分析逻辑验证模块

功能：
1. 检测止损/目标位置逻辑错误
2. 检测方向与信号冲突
3. 检测概率总和异常
4. 检测盈亏比不合理
5. 检测文字分析与结构化数据不一致
6. 生成逻辑错误报告

P2 实现：AI分析输出的逻辑一致性验证
"""
import os
import sys
import re

# Windows 终端编码修复
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


class ErrorSeverity(Enum):
    """错误严重程度"""
    CRITICAL = "critical"  # 严重错误，可能导致重大损失
    WARNING = "warning"    # 警告，需要注意
    INFO = "info"          # 提示信息


@dataclass
class LogicError:
    """逻辑错误"""
    code: str              # 错误代码
    severity: ErrorSeverity
    message: str           # 错误描述
    field: str             # 相关字段
    suggestion: str        # 修复建议
    auto_fixed: bool = False  # 是否已自动修复


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[LogicError] = field(default_factory=list)
    warnings: List[LogicError] = field(default_factory=list)
    infos: List[LogicError] = field(default_factory=list)
    fixed_output: Optional[Dict] = None
    
    @property
    def has_critical_errors(self) -> bool:
        return len(self.errors) > 0
    
    @property
    def total_issues(self) -> int:
        return len(self.errors) + len(self.warnings) + len(self.infos)


class LogicValidator:
    """AI分析逻辑验证器"""
    
    def __init__(self, current_price: float = None):
        self.current_price = current_price
        self.errors: List[LogicError] = []
    
    def validate(
        self,
        ai_output: Dict[str, Any],
        chanlun_json: Dict[str, Any] = None,
        current_price: float = None,
        auto_fix: bool = True,
    ) -> ValidationResult:
        """执行完整的逻辑验证
        
        参数：
        - ai_output: AI输出的JSON
        - chanlun_json: 缠论结构JSON（用于信号一致性检查）
        - current_price: 当前价格（用于价格逻辑检查）
        - auto_fix: 是否自动修复可修复的错误
        
        返回：
        - ValidationResult
        """
        self.errors = []
        self.current_price = current_price or self._extract_price(ai_output)
        
        # 创建副本用于修复
        fixed_output = ai_output.copy() if auto_fix else None
        
        # 1. 验证主场景
        self._validate_primary_scenario(ai_output, fixed_output)
        
        # 2. 验证场景列表
        self._validate_scenarios(ai_output, fixed_output)
        
        # 3. 验证方向与信号一致性
        self._validate_signal_consistency(ai_output, chanlun_json)
        
        # 4. 验证概率总和
        self._validate_probability_sum(ai_output, fixed_output)
        
        # 5. 验证文字分析一致性
        self._validate_analysis_consistency(ai_output)

        # 6. 验证结构判断
        self._validate_structure_judgement(ai_output)

        # 7. v2.0 新增：验证状态机格式（如果存在）
        self._validate_state_machine(ai_output, fixed_output)

        # 分类错误
        critical_errors = [e for e in self.errors if e.severity == ErrorSeverity.CRITICAL]
        warnings = [e for e in self.errors if e.severity == ErrorSeverity.WARNING]
        infos = [e for e in self.errors if e.severity == ErrorSeverity.INFO]
        
        return ValidationResult(
            is_valid=len(critical_errors) == 0,
            errors=critical_errors,
            warnings=warnings,
            infos=infos,
            fixed_output=fixed_output,
        )
    
    def _extract_price(self, ai_output: Dict) -> float:
        """从输出中提取当前价格"""
        meta = ai_output.get("meta", {})
        return float(meta.get("price", 0))
    
    def _add_error(
        self,
        code: str,
        severity: ErrorSeverity,
        message: str,
        field: str,
        suggestion: str,
        auto_fixed: bool = False,
    ):
        """添加错误"""
        self.errors.append(LogicError(
            code=code,
            severity=severity,
            message=message,
            field=field,
            suggestion=suggestion,
            auto_fixed=auto_fixed,
        ))
    
    def _validate_primary_scenario(self, ai_output: Dict, fixed_output: Dict = None):
        """验证主场景逻辑"""
        primary = ai_output.get("primary_scenario", {})
        if not primary:
            self._add_error(
                "E001", ErrorSeverity.CRITICAL,
                "缺少主场景(primary_scenario)",
                "primary_scenario",
                "AI输出必须包含primary_scenario字段"
            )
            return
        
        direction = primary.get("direction", "unknown")
        target_pct = primary.get("target_pct", 0)
        stop_pct = primary.get("stop_pct", 0)
        probability = primary.get("probability", 0)
        
        # 1. 检查方向有效性
        if direction not in ["up", "down", "range"]:
            self._add_error(
                "E002", ErrorSeverity.CRITICAL,
                f"无效的方向值: {direction}",
                "primary_scenario.direction",
                "direction必须是 up/down/range 之一"
            )
        
        # 2. 检查目标幅度
        if target_pct <= 0:
            self._add_error(
                "E003", ErrorSeverity.WARNING,
                f"目标幅度无效: {target_pct}%",
                "primary_scenario.target_pct",
                "target_pct应该是正数"
            )
        elif target_pct > 20:
            self._add_error(
                "E004", ErrorSeverity.WARNING,
                f"目标幅度过大: {target_pct}%",
                "primary_scenario.target_pct",
                "目标幅度超过20%可能不合理，建议检查"
            )
        
        # 3. 检查止损幅度
        if stop_pct <= 0:
            self._add_error(
                "E005", ErrorSeverity.WARNING,
                f"止损幅度无效: {stop_pct}%",
                "primary_scenario.stop_pct",
                "stop_pct应该是正数"
            )
            # 自动修复
            if fixed_output:
                fixed_output["primary_scenario"]["stop_pct"] = target_pct * 0.5
        elif stop_pct > target_pct * 2:
            self._add_error(
                "E006", ErrorSeverity.WARNING,
                f"止损幅度过大: {stop_pct}% (目标 {target_pct}%)",
                "primary_scenario.stop_pct",
                "止损幅度不应超过目标幅度的2倍"
            )
        
        # 4. 检查盈亏比
        if stop_pct > 0:
            rr_ratio = target_pct / stop_pct
            if rr_ratio < 1:
                self._add_error(
                    "E007", ErrorSeverity.WARNING,
                    f"盈亏比不合理: {rr_ratio:.2f}:1 (目标{target_pct}% / 止损{stop_pct}%)",
                    "primary_scenario",
                    "盈亏比应至少为1:1，建议调整目标或止损"
                )
                # 自动修复
                if fixed_output:
                    fixed_output["primary_scenario"]["stop_pct"] = target_pct * 0.5
                    self.errors[-1].auto_fixed = True
        
        # 5. 检查概率
        if probability <= 0 or probability > 1:
            self._add_error(
                "E008", ErrorSeverity.WARNING,
                f"概率值无效: {probability}",
                "primary_scenario.probability",
                "probability应在(0, 1]范围内"
            )
            if fixed_output and probability > 1:
                fixed_output["primary_scenario"]["probability"] = min(0.9, probability / 100)
    
    def _validate_scenarios(self, ai_output: Dict, fixed_output: Dict = None):
        """验证场景列表"""
        scenarios = ai_output.get("scenarios", [])
        if not scenarios:
            return

        for i, scenario in enumerate(scenarios):
            prob = scenario.get("probability", 0)
            direction = scenario.get("direction", "unknown")
            target_range = scenario.get("target_range", [])
            entry_range = scenario.get("entry_range", [])

            # 检查概率
            if prob <= 0 or prob > 1:
                self._add_error(
                    "E009", ErrorSeverity.INFO,
                    f"场景{i+1}概率无效: {prob}",
                    f"scenarios[{i}].probability",
                    "概率应在(0, 1]范围内"
                )

            # 检查目标范围
            if len(target_range) == 2:
                low, high = target_range
                if low > high:
                    self._add_error(
                        "E010", ErrorSeverity.WARNING,
                        f"场景{i+1}目标范围顺序错误: [{low}, {high}]",
                        f"scenarios[{i}].target_range",
                        "目标范围应该是[低, 高]"
                    )
                    if fixed_output:
                        fixed_output["scenarios"][i]["target_range"] = [high, low]
                        self.errors[-1].auto_fixed = True

                # 检查目标与方向一致性
                if self.current_price > 0:
                    if direction == "up" and high < self.current_price:
                        self._add_error(
                            "E011", ErrorSeverity.CRITICAL,
                            f"场景{i+1}方向与目标冲突: 看涨但目标{high}低于当前价{self.current_price:.0f}",
                            f"scenarios[{i}]",
                            "看涨方向的目标价应高于当前价"
                        )
                    elif direction == "down" and low > self.current_price:
                        self._add_error(
                            "E012", ErrorSeverity.CRITICAL,
                            f"场景{i+1}方向与目标冲突: 看跌但目标{low}高于当前价{self.current_price:.0f}",
                            f"scenarios[{i}]",
                            "看跌方向的目标价应低于当前价"
                        )

            # ==================== 新增：入场区间校验 ====================
            if len(entry_range) == 2 and self.current_price > 0:
                entry_low, entry_high = entry_range

                # E022: 入场区间顺序检查
                if entry_low > entry_high:
                    self._add_error(
                        "E022", ErrorSeverity.WARNING,
                        f"场景{i+1}入场区间顺序错误: [{entry_low}, {entry_high}]",
                        f"scenarios[{i}].entry_range",
                        "入场区间应该是[低, 高]"
                    )
                    if fixed_output:
                        fixed_output["scenarios"][i]["entry_range"] = [entry_high, entry_low]
                        entry_low, entry_high = entry_high, entry_low
                        self.errors[-1].auto_fixed = True

                # 计算入场区间宽度（占当前价格的百分比）
                entry_range_pct = (entry_high - entry_low) / self.current_price * 100

                # E023: 入场区间过宽检查（不应超过当前价的3%）
                if entry_range_pct > 3:
                    self._add_error(
                        "E023", ErrorSeverity.WARNING,
                        f"场景{i+1}入场区间过宽: {entry_range_pct:.1f}% (建议不超过3%)",
                        f"scenarios[{i}].entry_range",
                        "入场区间过宽会导致交易时机不明确，建议收缩到当前价±1.5%范围内"
                    )
                    # 自动修复：收缩入场区间到当前价附近
                    if fixed_output:
                        # 根据方向调整入场区间
                        if direction == "up":
                            # 做多：入场区在当前价附近或略下方
                            new_entry_low = self.current_price * 0.985
                            new_entry_high = self.current_price * 1.005
                        elif direction == "down":
                            # 做空：入场区在当前价附近或略上方
                            new_entry_low = self.current_price * 0.995
                            new_entry_high = self.current_price * 1.015
                        else:  # range
                            # 震荡：在当前价两侧
                            new_entry_low = self.current_price * 0.99
                            new_entry_high = self.current_price * 1.01
                        fixed_output["scenarios"][i]["entry_range"] = [new_entry_low, new_entry_high]
                        self.errors[-1].auto_fixed = True

                # E024: 入场区间与方向一致性检查
                if direction == "up":
                    # 做多：入场区应在当前价附近或略下方，不应偏离太多
                    if entry_low > self.current_price * 1.02:
                        self._add_error(
                            "E024", ErrorSeverity.WARNING,
                            f"场景{i+1}做多入场区过高: 入场下限{entry_low:.0f} > 当前价{self.current_price:.0f}的102%",
                            f"scenarios[{i}].entry_range",
                            "做多时入场区应在当前价附近或略下方"
                        )
                        if fixed_output:
                            fixed_output["scenarios"][i]["entry_range"] = [
                                self.current_price * 0.985,
                                self.current_price * 1.005
                            ]
                            self.errors[-1].auto_fixed = True
                elif direction == "down":
                    # 做空：入场区应在当前价附近或略上方
                    if entry_high < self.current_price * 0.98:
                        self._add_error(
                            "E025", ErrorSeverity.WARNING,
                            f"场景{i+1}做空入场区过低: 入场上限{entry_high:.0f} < 当前价{self.current_price:.0f}的98%",
                            f"scenarios[{i}].entry_range",
                            "做空时入场区应在当前价附近或略上方"
                        )
                        if fixed_output:
                            fixed_output["scenarios"][i]["entry_range"] = [
                                self.current_price * 0.995,
                                self.current_price * 1.015
                            ]
                            self.errors[-1].auto_fixed = True

                # E026: 止损与入场区间逻辑检查
                # 从 target_range 推断止损位置
                if len(target_range) == 2:
                    if direction == "up":
                        # 做多：止损应在入场区下方
                        # 通常止损设在 target_range 下界或更低
                        stop_price = target_range[0]  # 做多的止损在目标下界
                        if stop_price > entry_low:
                            self._add_error(
                                "E026", ErrorSeverity.CRITICAL,
                                f"场景{i+1}做多止损逻辑错误: 止损{stop_price:.0f} > 入场区下限{entry_low:.0f}",
                                f"scenarios[{i}].target_range",
                                "做多时止损应低于入场价格"
                            )
                    elif direction == "down":
                        # 做空：止损应在入场区上方
                        stop_price = target_range[1]  # 做空的止损在目标上界
                        if stop_price < entry_high:
                            self._add_error(
                                "E026", ErrorSeverity.CRITICAL,
                                f"场景{i+1}做空止损逻辑错误: 止损{stop_price:.0f} < 入场区上限{entry_high:.0f}",
                                f"scenarios[{i}].target_range",
                                "做空时止损应高于入场价格"
                            )
    
    def _validate_signal_consistency(self, ai_output: Dict, chanlun_json: Dict = None):
        """验证方向与信号一致性"""
        primary = ai_output.get("primary_scenario", {})
        direction = primary.get("direction", "unknown")
        
        # 从AI输出获取信号
        signals = ai_output.get("signals", {})
        buy_sell_points = signals.get("buy_sell_points", [])
        
        # 也检查chanlun_json中的信号
        if chanlun_json:
            signal_data = chanlun_json.get("signal", {})
            buy_sell_points = buy_sell_points or signal_data.get("buy_sell_points", [])
        
        if not buy_sell_points:
            return
        
        # 分析信号类型
        has_buy_signal = any("buy" in s.lower() for s in buy_sell_points)
        has_sell_signal = any("sell" in s.lower() for s in buy_sell_points)
        
        # 检查冲突
        if direction == "up" and has_sell_signal and not has_buy_signal:
            self._add_error(
                "E013", ErrorSeverity.WARNING,
                f"方向与信号可能冲突: 看涨但有卖出信号 {buy_sell_points}",
                "primary_scenario.direction",
                "建议检查是否应该顺应信号方向"
            )
        elif direction == "down" and has_buy_signal and not has_sell_signal:
            self._add_error(
                "E014", ErrorSeverity.WARNING,
                f"方向与信号可能冲突: 看跌但有买入信号 {buy_sell_points}",
                "primary_scenario.direction",
                "建议检查是否应该顺应信号方向"
            )
    
    def _validate_probability_sum(self, ai_output: Dict, fixed_output: Dict = None):
        """验证概率总和"""
        scenarios = ai_output.get("scenarios", [])
        if not scenarios:
            return
        
        total_prob = sum(s.get("probability", 0) for s in scenarios)
        
        if total_prob > 1.1:
            self._add_error(
                "E015", ErrorSeverity.WARNING,
                f"场景概率总和过大: {total_prob:.2f} (应不超过1.0)",
                "scenarios",
                "各场景概率之和应约等于1.0"
            )
            # 自动归一化
            if fixed_output and total_prob > 0:
                for s in fixed_output["scenarios"]:
                    s["probability"] = round(s["probability"] / total_prob, 2)
                self.errors[-1].auto_fixed = True
        
        elif total_prob < 0.5:
            self._add_error(
                "E016", ErrorSeverity.INFO,
                f"场景概率总和过小: {total_prob:.2f}",
                "scenarios",
                "建议检查是否遗漏了某些场景"
            )
    
    def _validate_analysis_consistency(self, ai_output: Dict):
        """验证文字分析与结构化数据的一致性"""
        analysis = ai_output.get("analysis", "")
        primary = ai_output.get("primary_scenario", {})
        
        if not analysis or not primary:
            return
        
        direction = primary.get("direction", "unknown")
        
        # 检查方向关键词
        analysis_lower = analysis.lower()
        
        # 文字中提到的方向
        mentions_bullish = any(kw in analysis for kw in ["做多", "看涨", "上涨", "买入", "多头"])
        mentions_bearish = any(kw in analysis for kw in ["做空", "看跌", "下跌", "卖出", "空头"])
        
        # 检查是否只强调一个方向但结构化数据是另一个
        if direction == "up" and mentions_bearish and not mentions_bullish:
            self._add_error(
                "E017", ErrorSeverity.WARNING,
                "文字分析侧重看跌，但主场景方向是看涨",
                "analysis",
                "请检查文字分析与primary_scenario.direction是否一致"
            )
        elif direction == "down" and mentions_bullish and not mentions_bearish:
            self._add_error(
                "E018", ErrorSeverity.WARNING,
                "文字分析侧重看涨，但主场景方向是看跌",
                "analysis",
                "请检查文字分析与primary_scenario.direction是否一致"
            )
        
        # 检查文字中的止损价格逻辑
        if self.current_price > 0:
            self._check_price_logic_in_text(analysis, direction)
    
    def _check_price_logic_in_text(self, analysis: str, direction: str):
        """检查文字中的价格逻辑"""
        # 提取止损相关的价格
        stop_patterns = [
            r"止损[位价]?[：:设在为]?\s*(\d+(?:\.\d+)?)",
            r"止损设?在\s*(\d+(?:\.\d+)?)",
            r"stop.?loss[:\s]*(\d+(?:\.\d+)?)",
        ]
        
        for pattern in stop_patterns:
            matches = re.findall(pattern, analysis, re.IGNORECASE)
            for match in matches:
                try:
                    stop_price = float(match)
                    # 检查止损价格逻辑
                    if direction == "up" and stop_price > self.current_price * 1.01:
                        self._add_error(
                            "E019", ErrorSeverity.CRITICAL,
                            f"做多策略止损价格逻辑错误: 止损{stop_price:.0f} > 当前价{self.current_price:.0f}",
                            "analysis",
                            "做多时止损价应低于入场价/当前价"
                        )
                    elif direction == "down" and stop_price < self.current_price * 0.99:
                        self._add_error(
                            "E020", ErrorSeverity.CRITICAL,
                            f"做空策略止损价格逻辑错误: 止损{stop_price:.0f} < 当前价{self.current_price:.0f}",
                            "analysis",
                            "做空时止损价应高于入场价/当前价"
                        )
                except ValueError:
                    pass
    
    def _validate_structure_judgement(self, ai_output: Dict):
        """验证结构判断"""
        structure = ai_output.get("structure_judgement", {})
        if not structure:
            return
        
        # 检查趋势与价格位置一致性
        trend = structure.get("trend", "unknown")
        price_position = structure.get("price_position", "unknown")
        
        # 检查中枢数据
        zs = structure.get("zs", {})
        zg = zs.get("zg", 0)
        zd = zs.get("zd", 0)
        
        if zg > 0 and zd > 0 and zg < zd:
            self._add_error(
                "E021", ErrorSeverity.CRITICAL,
                f"中枢区间逻辑错误: ZG({zg}) < ZD({zd})",
                "structure_judgement.zs",
                "中枢高点(ZG)应大于等于中枢低点(ZD)"
            )

    def _validate_state_machine(self, ai_output: Dict, fixed_output: Dict = None):
        """验证状态机格式（v2.0 新增）

        检查项：
        1. active_strategy 必须唯一
        2. entry_gate.price_zone 宽度不超过 3%
        3. structure_required 不能为空
        4. invalidation 条件必须存在
        5. 风险等级与历史胜率匹配
        """
        state_machine = ai_output.get("state_machine", {})
        if not state_machine:
            return  # 状态机是可选的

        current_state = state_machine.get("current_state", "")
        active_strategy = state_machine.get("active_strategy", {})

        # E027: 检查状态值是否有效
        if current_state not in ["STRATEGY_ACTIVE", "WAIT_CONFIRMATION", "OBSERVE_ONLY"]:
            self._add_error(
                "E027", ErrorSeverity.WARNING,
                f"无效的当前状态: {current_state}",
                "state_machine.current_state",
                "状态必须是 STRATEGY_ACTIVE / WAIT_CONFIRMATION / OBSERVE_ONLY 之一"
            )

        # 如果是 OBSERVE_ONLY，不需要进一步验证
        if current_state == "OBSERVE_ONLY" or not active_strategy:
            return

        # 验证 active_strategy
        direction = active_strategy.get("direction", "")
        if direction not in ["up", "down"]:
            self._add_error(
                "E028", ErrorSeverity.CRITICAL,
                f"激活策略方向无效: {direction}",
                "state_machine.active_strategy.direction",
                "方向必须是 up 或 down"
            )

        # 验证 entry_gate
        entry_gate = active_strategy.get("entry_gate", {})
        price_zone = entry_gate.get("price_zone", [])
        structure_required = entry_gate.get("structure_required", [])

        # E029: 入场区间宽度检查
        if len(price_zone) == 2 and self.current_price > 0:
            low, high = price_zone
            if low > high:
                self._add_error(
                    "E029", ErrorSeverity.WARNING,
                    f"激活策略入场区间顺序错误: [{low}, {high}]",
                    "state_machine.active_strategy.entry_gate.price_zone",
                    "入场区间应该是 [低, 高]"
                )
                if fixed_output:
                    fixed_output["state_machine"]["active_strategy"]["entry_gate"]["price_zone"] = [high, low]
                    self.errors[-1].auto_fixed = True
            else:
                zone_width_pct = (high - low) / self.current_price * 100
                if zone_width_pct > 3:
                    self._add_error(
                        "E030", ErrorSeverity.WARNING,
                        f"激活策略入场区间过宽: {zone_width_pct:.1f}% (建议不超过3%)",
                        "state_machine.active_strategy.entry_gate.price_zone",
                        "入场区间过宽会导致交易时机不明确"
                    )

        # E031: 结构触发条件不能为空
        if not structure_required or len(structure_required) == 0:
            self._add_error(
                "E031", ErrorSeverity.CRITICAL,
                "激活策略缺少结构触发条件",
                "state_machine.active_strategy.entry_gate.structure_required",
                "entry_gate.structure_required 不能为空，必须包含具体的缠论术语条件"
            )

        # 验证 invalidation 条件
        invalidation = state_machine.get("invalidation", {})
        invalidate_if = invalidation.get("invalidate_active_if", [])

        # E032: 必须有否决条件
        if not invalidate_if or len(invalidate_if) == 0:
            self._add_error(
                "E032", ErrorSeverity.CRITICAL,
                "状态机缺少否决条件",
                "state_machine.invalidation",
                "必须定义 invalidation 条件（什么情况下放弃当前策略）"
            )

        # 验证执行参数
        execution = active_strategy.get("execution", {})
        stop_loss = execution.get("stop_loss", 0)
        target = execution.get("target", 0)

        # E033: 止损和目标必须存在
        if stop_loss == 0:
            self._add_error(
                "E033", ErrorSeverity.CRITICAL,
                "激活策略缺少止损价格",
                "state_machine.active_strategy.execution.stop_loss",
                "execution.stop_loss 必须大于 0"
            )

        if target == 0:
            self._add_error(
                "E034", ErrorSeverity.CRITICAL,
                "激活策略缺少目标价格",
                "state_machine.active_strategy.execution.target",
                "execution.target 必须大于 0"
            )

        # E035: 盈亏比检查
        rr = execution.get("rr", 0)
        if rr > 0 and rr < 0.8:
            self._add_error(
                "E035", ErrorSeverity.WARNING,
                f"激活策略盈亏比过低: {rr:.2f}:1 (建议至少 1:1)",
                "state_machine.active_strategy.execution.rr",
                "盈亏比过低可能导致风险收益不合理"
            )


def validate_ai_output(
    ai_output: Dict[str, Any],
    chanlun_json: Dict[str, Any] = None,
    current_price: float = None,
    auto_fix: bool = True,
) -> ValidationResult:
    """验证AI输出（便捷函数）
    
    参数：
    - ai_output: AI输出JSON
    - chanlun_json: 缠论结构JSON
    - current_price: 当前价格
    - auto_fix: 是否自动修复
    
    返回：
    - ValidationResult
    """
    validator = LogicValidator(current_price)
    return validator.validate(ai_output, chanlun_json, current_price, auto_fix)


def format_validation_report(result: ValidationResult) -> str:
    """格式化验证报告"""
    lines = []
    
    if result.is_valid and result.total_issues == 0:
        return "✅ 逻辑验证通过，无异常"
    
    lines.append("")
    lines.append("=" * 60)
    lines.append("  AI分析逻辑验证报告")
    lines.append("=" * 60)
    
    # 统计
    lines.append(f"\n  验证结果: {'通过' if result.is_valid else '未通过'}")
    lines.append(f"  严重错误: {len(result.errors)} 个")
    lines.append(f"  警告: {len(result.warnings)} 个")
    lines.append(f"  提示: {len(result.infos)} 个")
    
    # 严重错误
    if result.errors:
        lines.append("\n  【严重错误】")
        lines.append("-" * 60)
        for err in result.errors:
            fixed_tag = " [已修复]" if err.auto_fixed else ""
            lines.append(f"  [{err.code}] {err.message}{fixed_tag}")
            lines.append(f"       字段: {err.field}")
            lines.append(f"       建议: {err.suggestion}")
    
    # 警告
    if result.warnings:
        lines.append("\n  【警告】")
        lines.append("-" * 60)
        for warn in result.warnings:
            fixed_tag = " [已修复]" if warn.auto_fixed else ""
            lines.append(f"  [{warn.code}] {warn.message}{fixed_tag}")
            lines.append(f"       建议: {warn.suggestion}")
    
    # 提示
    if result.infos:
        lines.append("\n  【提示】")
        lines.append("-" * 60)
        for info in result.infos:
            lines.append(f"  [{info.code}] {info.message}")
    
    lines.append("\n" + "=" * 60)

    return "\n".join(lines)


def format_entry_range_fixes(result: ValidationResult, current_price: float) -> str:
    """格式化入场区间修复摘要（用于 chanlun_ai.py 显示）

    参数：
    - result: 验证结果
    - current_price: 当前价格

    返回：
    - 格式化的修复摘要
    """
    if not result.warnings and not result.errors:
        return ""

    # 筛选出入场区间相关的修复
    entry_fixes = []
    for err in result.errors + result.warnings:
        if err.auto_fixed and "entry_range" in err.field and err.code in ["E022", "E023", "E024", "E025"]:
            entry_fixes.append(err)

    if not entry_fixes:
        return ""

    lines = ["\n📋 入场区间优化："]
    for err in entry_fixes[:3]:  # 最多显示3条
        if err.code == "E023":
            lines.append(f"  - 入场区间过宽已收缩至当前价±1.5%")
        elif err.code == "E024":
            lines.append(f"  - 做多入场区调整至当前价附近")
        elif err.code == "E025":
            lines.append(f"  - 做空入场区调整至当前价附近")
        elif err.code == "E022":
            lines.append(f"  - 入场区间顺序已修正")

    return "\n".join(lines)


# ============================================
# 测试
# ============================================

def main():
    """测试逻辑验证"""
    # 模拟AI输出（包含一些错误）
    test_output = {
        "meta": {
            "symbol": "BTC/USDT",
            "interval": "1h",
            "price": 92000,
        },
        "analysis": "当前看跌趋势，建议做空策略。止损设在91000附近，目标90000。",
        "primary_scenario": {
            "direction": "down",
            "target_pct": 2.0,
            "stop_pct": 1.0,
            "probability": 0.5,
        },
        "scenarios": [
            {
                "rank": 1,
                "probability": 0.5,
                "direction": "down",
                "target_range": [90000, 91000],
            },
            {
                "rank": 2,
                "probability": 0.4,
                "direction": "up",
                "target_range": [93000, 95000],
            },
            {
                "rank": 3,
                "probability": 0.3,  # 总和超过1
                "direction": "range",
                "target_range": [91000, 93000],
            },
        ],
        "signals": {
            "buy_sell_points": ["1sell"],
            "divergences": [],
        },
        "structure_judgement": {
            "trend": "down_trend",
            "price_position": "above_zs",
            "zs": {
                "zg": 93000,
                "zd": 91000,
            }
        }
    }
    
    print("测试AI分析逻辑验证...")
    print("=" * 60)
    
    result = validate_ai_output(
        test_output,
        current_price=92000,
        auto_fix=True,
    )
    
    report = format_validation_report(result)
    print(report)
    
    if result.fixed_output:
        import json
        print("\n修复后的scenarios概率:")
        for s in result.fixed_output.get("scenarios", []):
            print(f"  场景{s['rank']}: {s['probability']}")


if __name__ == "__main__":
    main()
