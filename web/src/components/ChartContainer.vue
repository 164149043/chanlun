<template>
  <div class="chart-container" ref="containerRef">
    <div ref="chartRef" class="echart-chart"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import type { ChanlunData } from '@/types/chanlun';

const props = defineProps<{
  data: ChanlunData | null;
  showBi?: boolean;
  showXd?: boolean;
  showZs?: boolean;
  showFx?: boolean;
  showMmd?: boolean;
}>();

const emit = defineEmits<{
  (e: 'ready', chart: any): void;
}>();

const containerRef: any = ref(null);
const chartRef: any = ref(null);
let chart: any = null;

// Color configuration (TradingView style)
const colors = {
  up: '#089981',      // Rise - Green
  down: '#F23645',    // Fall - Red
  biUp: '#2962FF',    // Up Bi - Blue
  biDown: '#FF6D00',  // Down Bi - Orange
  xd: '#9C27B0',      // XD - Purple
  zsBg: 'rgba(120, 123, 134, 0.15)',
  zsBorder: '#787B86',
  fxUp: '#388E3C',    // Bottom FX - Green
  fxDown: '#D32F2F',  // Top FX - Red
  buy1: '#089981',
  buy2: '#26A69A',
  sell1: '#F23645',
  sell2: '#EF5350',
  sell3: '#E57373',
  bg: '#FFFFFF',
  grid: '#F0F3FA'
};

function initChart() {
  if (!chartRef.value) {
    console.error('[ChartContainer] chartRef is null');
    return;
  }
  console.log('[ChartContainer] Initializing ECharts');
  chart = echarts.init(chartRef.value, 'light', {
    renderer: 'canvas',
    backgroundColor: colors.bg
  });
  emit('ready', chart);
}

function renderChart() {
  console.log('[ChartContainer] renderChart called, data:', !!props.data);
  if (!chart) {
    console.warn('[ChartContainer] chart is null');
    return;
  }
  if (!props.data) {
    console.warn('[ChartContainer] props.data is null');
    return;
  }

  const { klines, bi, xd, zs, fx } = props.data;

  // Guard against undefined data
  if (!klines || !Array.isArray(klines)) {
    console.warn('[ChartContainer] klines data is invalid');
    return;
  }

  console.log('[ChartContainer] Rendering chart with', klines.length, 'klines');

  // Prepare K-line data
  const dates: string[] = [];
  const klineData: [number, number, number, number][] = [];

  klines.forEach((k: any) => {
    dates.push(k.date);
    // ECharts candlestick: [open, close, lowest, highest]
    klineData.push([k.o, k.c, k.l, k.h]);
  });

  // Prepare Bi data (连接起点到终点的线)
  const biLineData: any[] = [];
  if (bi && Array.isArray(bi)) {
    bi.forEach((b: any) => {
      // 添加起点
      biLineData.push([b.start_date, b.start_price]);
      // 添加终点
      biLineData.push([b.end_date, b.end_price]);
      // 添加 null 断开不同的笔
      biLineData.push(null);
    });
    // 移除最后一个 null
    if (biLineData.length > 0 && biLineData[biLineData.length - 1] === null) {
      biLineData.pop();
    }
  }

  // Prepare XD data (segment 连接线)
  const xdLineData: any[] = [];
  if (xd && Array.isArray(xd)) {
    xd.forEach((x: any) => {
      // 添加起点
      xdLineData.push({
        value: [x.start_date, x.start_price]
      });
      // 添加终点
      xdLineData.push({
        value: [x.end_date, x.end_price]
      });
      // 添加 null 断开不同的线段
      xdLineData.push(null);
    });
    // 移除最后一个 null
    if (xdLineData.length > 0 && xdLineData[xdLineData.length - 1] === null) {
      xdLineData.pop();
    }
  }

  // Prepare FX markers (top/bottom fractals)
  const fxMarkers: any[] = [];
  if (fx && Array.isArray(fx)) {
    fx.forEach((f: any) => {
      const isDing = f.type === 'ding';
      const color = isDing ? colors.fxDown : colors.fxUp;

      fxMarkers.push({
        name: f.type,
        coord: [f.date, f.price],
        value: f.price,
        symbol: isDing ? 'triangle' : 'triangle',
        symbolSize: 10,
        symbolRotate: isDing ? 0 : 180,
        symbolOffset: isDing ? [0, -10] : [0, 10],
        itemStyle: {
          color: color,
          borderColor: color
        },
        label: {
          show: false
        }
      });
    });
  }

  // Prepare buy/sell point markers
  const mmdMarkers: any[] = [];
  if (bi && Array.isArray(bi)) {
    bi.forEach((b: any) => {
      if (b.buy_sell_point) {
        const pointType = b.buy_sell_point.toLowerCase();
        const isBuy = pointType.includes('buy');
        const color = isBuy ? colors.buy1 : colors.sell1;
        const symbolOffset = isBuy ? [0, 15] : [0, -15];

        mmdMarkers.push({
          name: b.buy_sell_point,
          coord: [b.end_date, b.end_price],
          value: b.end_price,
          symbol: 'circle',
          symbolSize: 12,
          symbolOffset: symbolOffset,
          itemStyle: {
            color: color,
            borderColor: '#FFFFFF',
            borderWidth: 2
          },
          label: {
            show: true,
            position: isBuy ? 'top' : 'bottom',
            formatter: b.buy_sell_point,
            color: color,
            fontSize: 11,
            fontWeight: 'bold'
          }
        });
      }
    });
  }

  // Configure option
  const option: any = {
    animation: true,
    animationDuration: 300,
    backgroundColor: colors.bg,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: function (params: any) {
        if (!params || params.length === 0) return '';
        let result = params[0].axisValue + '<br/>';
        params.forEach((p: any) => {
          if (p.seriesName === 'K-Line' && p.data) {
            const [open, close, low, high] = p.data;
            result += `O: ${open}<br/>H: ${high}<br/>L: ${low}<br/>C: ${close}<br/>`;
          }
        });
        return result;
      }
    },
    grid: {
      left: '60px',
      right: '60px',
      top: '20px',
      bottom: '60px'
    },
    xAxis: {
      type: 'category',
      data: dates,
      scale: true,
      boundaryGap: false,
      axisLine: { onZero: false, lineStyle: { color: '#787B86' } },
      splitLine: { show: false }
    },
    yAxis: {
      scale: true,
      axisLine: { lineStyle: { color: '#787B86' } },
      splitLine: { lineStyle: { color: colors.grid, width: 1 } }
    },
    dataZoom: [
      {
        type: 'inside',
        start: 70,
        end: 100
      },
      {
        type: 'slider',
        show: true,
        start: 70,
        end: 100,
        height: 20,
        bottom: 10
      }
    ],
    series: []
  };

  // Add K-Line series
  option.series.push({
    type: 'candlestick',
    name: 'K-Line',
    data: klineData,
    itemStyle: {
      color: colors.up,
      color0: colors.down,
      borderColor: colors.up,
      borderColor0: colors.down
    }
  });

  // Add Bi lines (笔的连接线)
  if (props.showBi && biLineData.length > 0) {
    option.series.push({
      type: 'line',
      name: 'Bi',
      data: biLineData,
      lineStyle: { width: 2 },
      symbol: 'circle',
      symbolSize: 6,
      z: 2,
      connectNulls: false
    });
  }

  // Add XD line (线段连接线)
  if (props.showXd && xdLineData.length > 0) {
    option.series.push({
      type: 'line',
      name: 'XD',
      data: xdLineData,
      lineStyle: { color: colors.xd, width: 2, type: 'solid' },
      symbol: 'circle',
      symbolSize: 4,
      z: 3,
      connectNulls: false,
      showSymbol: false
    });
  }

  // Add FX markers
  if (props.showFx && fxMarkers.length > 0) {
    option.series.push({
      type: 'scatter',
      name: 'FX',
      data: fxMarkers,
      symbolSize: 10,
      z: 4
    });
  }

  // Add buy/sell markers
  if (props.showMmd && mmdMarkers.length > 0) {
    option.series.push({
      type: 'scatter',
      name: 'MMD',
      data: mmdMarkers,
      symbolSize: 16,
      symbol: 'circle',
      z: 5,
      label: {
        show: true,
        position: function (params: any) {
          const marker = mmdMarkers[params.dataIndex];
          const isBuy = marker?.name?.toLowerCase().includes('buy');
          return isBuy ? 'top' : 'bottom';
        },
        formatter: function (params: any) {
          const marker = mmdMarkers[params.dataIndex];
          return marker?.name || '';
        },
        fontSize: 10,
        color: function (params: any) {
          const marker = mmdMarkers[params.dataIndex];
          return marker?.itemStyle?.color || '#131722';
        },
        fontWeight: 'bold'
      }
    });
  }

  // Add ZS (中枢) - 使用 markArea 在 K-Line 上添加背景区域
  if (props.showZs && zs && zs.length > 0) {
    // 为每个中枢创建一个背景区域（包含时间范围和价格范围）
    const zsAreas = zs.map((z: any) => [{
      xAxis: z.start_date,  // 中枢开始时间
      yAxis: z.zd,           // 中枢低点
      label: { show: false }
    }, {
      xAxis: z.end_date,    // 中枢结束时间
      yAxis: z.zg           // 中枢高点
    }]);

    // 将 markArea 添加到 K-Line 系列
    const klineSeries = option.series.find((s: any) => s.name === 'K-Line');
    if (klineSeries) {
      klineSeries.markArea = {
        silent: true,
        itemStyle: {
          color: 'rgba(120, 123, 134, 0.15)',
          borderColor: '#787B86',
          borderWidth: 1
        },
        data: zsAreas
      };
    }
  }

  chart.setOption(option, true);
}

function resize() {
  if (chart) {
    chart.resize();
  }
}

// Watch data changes
watch(() => props.data, (newData) => {
  console.log('[ChartContainer] data changed', newData ? `(${newData.klines?.length} klines)` : 'null');
  nextTick(() => {
    renderChart();
  });
}, { deep: true });

// Watch layer visibility changes
watch([() => props.showBi, () => props.showXd, () => props.showZs, () => props.showFx, () => props.showMmd], () => {
  renderChart();
});

onMounted(() => {
  initChart();
  renderChart();
});

onUnmounted(() => {
  if (chart) {
    chart.dispose();
  }
});

defineExpose({
  resize
});
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.echart-chart {
  width: 100%;
  height: 100%;
  min-height: 400px;
}
</style>
