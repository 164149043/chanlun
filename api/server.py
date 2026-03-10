#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""FastAPI Server - ChanLun Analysis API Service"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.staticfiles import StaticFiles
import uvicorn
import json
import asyncio

# Import project modules
from binance import get_klines
from chanlun_adapter import convert_to_chanlun_bars
from chanlun_local.engine import ChanlunEngine, EngineConfig

app = FastAPI()

# 全局存储分析结果（用于 SSE 流式端点）
analysis_progress = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

web_dir = Path(__file__).parent.parent / "web"


@app.get("/")
async def root():
    return {"service": "ChanLun Analysis API", "version": "1.0.0"}


@app.get("/web")
async def web_index():
    html_file = web_dir / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return {"error": "Web interface not found"}


@app.get("/api/kline/{symbol}/{interval}")
async def get_kline(symbol: str, interval: str, limit: int = 1000):
    try:
        raw_klines = get_klines(symbol, interval, limit)

        if not raw_klines or len(raw_klines) < 3:
            return {"error": "Insufficient data"}

        # Prepare klines in the format expected by ChanlunEngine
        # Engine expects: date, open, high, low, close, volume
        engine_klines = [
            {
                "date": k["open_time"],
                "open": k["open"],
                "high": k["high"],
                "low": k["low"],
                "close": k["close"],
                "volume": 0.0,  # Binance data doesn't include volume in our simplified format
            }
            for k in raw_klines
        ]

        config = EngineConfig()
        engine_wrapper = ChanlunEngine(config)
        icl_result = engine_wrapper.analyze_klines(
            code=symbol,
            frequency=interval,
            klines=engine_klines
        )

        bi_list = icl_result.get_bis()
        xd_list = icl_result.get_xds()
        bi_zs_list = icl_result.get_bi_zss()
        fx_list = icl_result.get_fx_list()

        # Convert to frontend format (o/h/l/c) for the chart
        frontend_bars = convert_to_chanlun_bars(raw_klines)

        result = {
            "meta": {"symbol": symbol, "interval": interval, "count": len(frontend_bars)},
            "klines": frontend_bars,
            "bi": [
                {
                    "index": bi.index,
                    "type": bi.type,
                    "start_price": bi.start_price,
                    "end_price": bi.end_price,
                    "start_date": str(bi.start_time),
                    "end_date": str(bi.end_time),
                    "buy_sell_point": bi.mmds[0].name if bi.mmds and len(bi.mmds) > 0 else None
                }
                for bi in bi_list
            ],
            "xd": [
                {"index": xd.index, "type": xd.type, "start_price": xd.start_price,
                 "end_price": xd.end_price, "start_date": str(xd.start_time),
                 "end_date": str(xd.end_time)}
                for xd in xd_list
            ],
            "zs": [
                {
                    "zg": zs.zg,
                    "zd": zs.zd,
                    "gg": zs.gg,
                    "dd": zs.dd,
                    "start_date": str(zs.start_time),
                    "end_date": str(zs.end_time)
                }
                for zs in bi_zs_list
            ],
            "fx": [
                {"index": fx.index, "type": fx.type, "price": fx.val,
                 "date": str(fx.time)}
                for fx in fx_list
            ]
        }
        return result

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.post("/api/analyze")
async def analyze(request: Request):
    try:
        # Get JSON data from request
        data = await request.json()

        symbol = data.get("symbol")
        interval = data.get("interval")
        mode = data.get("mode", "structured")
        test = data.get("test", False)

        # 新增：从前端获取 AI 配置
        ai_provider = data.get("ai_provider")
        ai_model = data.get("ai_model")
        api_key = data.get("api_key")

        if not symbol or not interval:
            return JSONResponse(content={"error": "Missing symbol or interval"}, status_code=400)

        from api.analyze_service import analyze_chanlun

        # Execute AI analysis (pass test parameter, mode, and AI config)
        result = analyze_chanlun(
            symbol, interval,
            limit=500,
            test_mode=test,
            mode=mode,
            ai_provider=ai_provider,
            ai_model=ai_model,
            api_key=api_key
        )

        # Use JSONResponse to ensure proper encoding
        return JSONResponse(content=result)

    except Exception as e:
        import traceback
        return JSONResponse(content={"error": str(e), "traceback": traceback.format_exc()})


@app.post("/api/analyze/stream")
async def analyze_stream(request: Request):
    """流式分析端点 - SSE（Server-Sent Events）"""
    try:
        data = await request.json()
        symbol = data.get("symbol")
        interval = data.get("interval")
        mode = data.get("mode", "structured")
        test = data.get("test", False)

        if not symbol or not interval:
            return JSONResponse(content={"error": "Missing symbol or interval"}, status_code=400)

        # 生成唯一任务ID
        task_id = f"{symbol}_{interval}_{int(asyncio.get_event_loop().time() * 1000)}"

        async def event_generator():
            """SSE 事件生成器"""
            try:
                # 导入流式分析模块
                from api.analyze_streaming import analyze_streaming_async

                # 发送开始事件
                yield f"event: start\ndata: {json.dumps({'task_id': task_id}, ensure_ascii=False)}\n\n"

                # 流式执行分析并发送日志
                async for log_event in analyze_streaming_async(symbol, interval, mode, test, task_id):
                    yield f"event: log\ndata: {json.dumps(log_event, ensure_ascii=False)}\n\n"

                # 发送完成事件
                yield f"event: complete\ndata: {json.dumps({'task_id': task_id}, ensure_ascii=False)}\n\n"

            except Exception as e:
                import traceback
                yield f"event: error\ndata: {json.dumps({'error': str(e), 'traceback': traceback.format_exc()}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
            }
        )

    except Exception as e:
        import traceback
        return JSONResponse(content={"error": str(e), "traceback": traceback.format_exc()})


@app.get("/api/analyze/{task_id}/result")
async def get_analysis_result(task_id: str):
    """获取分析结果（用于 SSE 完成后获取最终结果）"""
    # 从流式模块获取存储
    from api.analyze_streaming import get_analysis_progress
    progress_storage = get_analysis_progress()
    if task_id in progress_storage:
        result = progress_storage[task_id]
        # 可选：返回后删除以节省内存
        # del progress_storage[task_id]
        return result
    return {"error": "Task not found"}


app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


if __name__ == "__main__":
    print("Starting ChanLun Analysis API Server...")
    print("API: http://0.0.0.0:8001")
    print("Web: http://0.0.0.0:8001/web")
    uvicorn.run(app, host="0.0.0.0", port=8001)
