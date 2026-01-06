import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "chanlun_ai.db"


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        sql = """
        SELECT
          symbol,
          COUNT(*) AS total,
          SUM(json_extract(outcome_json, '$.hit_target')) AS wins,
          ROUND(1.0 * SUM(json_extract(outcome_json, '$.hit_target')) / COUNT(*), 3) AS win_rate
        FROM analysis_snapshot
        WHERE evaluated = 1 AND outcome_json IS NOT NULL
        GROUP BY symbol
        ORDER BY total DESC;
        """

        rows = conn.execute(sql).fetchall()

        print("\n📊 AI 按品种统计")
        print("=" * 50)
        if not rows:
            print("（暂无已评估数据，可先运行 chanlun_ai.py + evaluate_outcome.py）")
            return

        for symbol, total, wins, win_rate in rows:
            print(
                f"{symbol:10} | 样本:{total:<4} | 命中:{int(wins or 0):<4} | 胜率:{win_rate:.3f}"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
