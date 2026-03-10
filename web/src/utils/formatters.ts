// 格式化工具函数

export function formatPrice(price: number | string): string {
  if (typeof price === 'string') {
    price = parseFloat(price);
  }
  if (isNaN(price)) return '-';

  // 根据价格大小决定小数位数
  if (price >= 1000) {
    return price.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  } else if (price >= 1) {
    return price.toFixed(2);
  } else {
    return price.toFixed(6);
  }
}

export function formatPercentage(value: number): string {
  return (value * 100).toFixed(1) + '%';
}

export function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

export function getIntervalLabel(interval: string): string {
  const labels: Record<string, string> = {
    '15m': '15分钟',
    '1h': '1小时',
    '4h': '4小时',
    '1d': '1天'
  };
  return labels[interval] || interval;
}

export function getSymbolLabel(symbol: string): string {
  if (symbol.includes('BTC')) return 'BTC/USDT';
  if (symbol.includes('ETH')) return 'ETH/USDT';
  return symbol;
}
