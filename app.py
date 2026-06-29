from flask import Flask, jsonify, request
import yfinance as yf
import pandas as pd
import os
import datetime
import requests

app = Flask(__name__)

JPX_CSV_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
LOCAL_CSV = "jpx_list.xls"

# 日経225用（HTMLテーブルから取得）
NIKKEI225_URL = "https://indexes.nikkei.co.jp/nkave/index/component?idx=nk225"


def update_jpx_list():
    today = datetime.date.today()

    if os.path.exists(LOCAL_CSV):
        mtime = datetime.date.fromtimestamp(os.path.getmtime(LOCAL_CSV))
        if mtime == today:
            return

    print("JPX銘柄一覧をダウンロード中...")
    r = requests.get(JPX_CSV_URL)
    r.raise_for_status()
    with open(LOCAL_CSV, "wb") as f:
        f.write(r.content)
    print("JPX銘柄一覧更新完了")


def load_jpx_list():
    update_jpx_list()

    df = pd.read_excel(LOCAL_CSV)

    df = df.rename(columns={
        "コード": "code",
        "銘柄名": "name",
        "市場・商品区分": "market",
        "17業種区分": "sector17"
    })

    df["code"] = df["code"].astype(str).str.zfill(4)
    df["sector17"] = df["sector17"].astype(str).str.strip()

    df["sector17"] = df["sector17"].replace(
        ["", "_", "-", "‐", "–", "—", "None", "nan", "NaN", "　"],
        "その他"
    )

    # コードの小さい順に固定
    df = df.sort_values(by="code", ascending=True)

    return df[["code", "name", "market", "sector17"]]


def load_nikkei225_list():
    """
    日経225採用銘柄のコード一覧を取得（起動時に毎回最新化）
    """
    print("日経225銘柄一覧を取得中...")
    try:
        tables = pd.read_html(NIKKEI225_URL)
        df = tables[0]
        # 列名はページ構造に依存するので、コードらしき列を探す
        code_col = None
        for col in df.columns:
            if "コード" in str(col) or "Code" in str(col):
                code_col = col
                break
        if code_col is None:
            raise ValueError("コード列が見つかりませんでした（日経225）")

        codes = df[code_col].astype(str).str.zfill(4).tolist()
        print(f"日経225銘柄数: {len(codes)}")
        return codes
    except Exception as e:
        print("日経225銘柄取得エラー:", e)
        return []


NIKKEI225_CODES = load_nikkei225_list()


def fetch_real_data(ticker, interval="1d", period=None):
    # interval に応じて期間を自動設定
    if period is None:
        if interval == "1d":
            period = "3mo"
        elif interval == "1wk":
            period = "1y"
        elif interval == "1mo":
            period = "5y"

    df = yf.download(f"{ticker}.T", period=period, interval=interval)

    if df is None or df.empty:
        raise ValueError(f"データが取得できませんでした: {ticker}")

    df = df.reset_index()
    df.columns = df.columns.get_level_values(0)

    ohlc = []
    for _, row in df.iterrows():
        date_col = "Date" if "Date" in row else "Datetime"

        ohlc.append({
            "time": row[date_col].strftime("%Y-%m-%d"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
        })

    return ohlc


@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>東証チャートの縦流し</title>

        <script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>

        <style>
            body {
                margin: 0;
                padding: 0;
                background-color: #131722;
                color: #d1d4dc;
                font-family: sans-serif;
            }

            #filter-bar {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                z-index: 999;
                background: #1c2030;
                padding: 10px;
                border-bottom: 1px solid #333;
            }

            #filter-bar h3 {
                margin: 5px 0;
                font-size: 14px;
            }

            .filter-group {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 10px;
            }

            #start-button {
                width: 100%;
                padding: 10px;
                background: #26a69a;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                margin-top: 10px;
                cursor: pointer;
            }

            #content {
                padding-top: 340px;
            }

            .chart-container {
                margin: 10px;
                background: #1c2030;
                border-radius: 6px;
                padding: 6px;
            }

            .chart-title {
                font-size: 14px;
                font-weight: bold;
                margin-bottom: 4px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            .chart-area {
                width: 100%;
                height: 23vh;
                min-height: 150px;
                cursor: pointer;
            }

            .ad-banner {
                width: 100%;
                height: 80px;
                background: #2a2e39;
                border-radius: 6px;
                margin: 10px;
                display: flex;
                justify-content: center;
                align-items: center;
                color: #aaa;
                font-size: 14px;
            }

            #loading {
                text-align: center;
                padding: 20px;
                color: #aaa;
                font-size: 14px;
            }

            #site-title {
                position: absolute;
                top: 6px;
                right: 10px;
                background: #007bff;
                color: white;
                padding: 3px 10px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
                z-index: 1000;
                margin-right: 10px;
            }

            #interval-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                position: relative;
                margin-top: 5px;
            }

            #pc-link {
                background: #4da3ff;
                color: white;
                padding: 4px 10px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                text-decoration: none;
                margin-right: 10px;
            }

            /* 市場区分＋日経225を横並びにする */
            #market-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 10px;
            }

            #nikkei225-box {
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 14px;
            }
        </style>
    </head>
    <body>

        <div id="filter-bar">

            <div id="site-title">東証チャートの縦流し</div>

            <h3>市場区分（複数選択可）</h3>
            <div id="market-row">
                <div class="filter-group" style="flex: 1;">
                    <label><input type="checkbox" class="market" value="プライム"> プライム</label>
                    <label><input type="checkbox" class="market" value="スタンダード"> スタンダード</label>
                    <label><input type="checkbox" class="market" value="グロース"> グロース</label>
                </div>

                <div id="nikkei225-box">
                    <label><input type="checkbox" id="nikkei225"> 日経225</label>
                </div>
            </div>

            <h3>足種（1つだけ）</h3>
            <div id="interval-row">
                <div class="interval-options">
                    <label><input type="radio" name="interval" value="1d" checked> 日足</label>
                    <label><input type="radio" name="interval" value="1wk"> 週足</label>
                    <label><input type="radio" name="interval" value="1mo"> 月足</label>
                </div>

                <a id="pc-link" href="https://あなたのPC版URL">PC画面</a>
            </div>

            <h3>17業種</h3>
            <button id="toggle-sector" style="
                width:100%; padding:10px; background:#2a2e39; color:white;
                border:none; border-radius:6px; font-size:15px; margin-bottom:10px;">
                業種を選択 ▼
            </button>

            <div id="sector-box-wrapper" style="display:none;">
                <div class="filter-group">
                    <label><input type="checkbox" id="sector-all"> 全業種</label>
                </div>
                <div class="filter-group" id="sector-box"></div>
            </div>

            <button id="start-button">描画開始</button>
        </div>

        <div id="content">
            <div id="app"></div>
            <div id="loading"></div>
        </div>

        <script>
            let page = 1;
            let loading = false;
            let globalIndex = 0;
            let currentInterval = "1d";

            let selectedMarkets = [];
            let selectedSectors = [];
            let selectedNikkei225 = false;

            let drawing = false;

            document.getElementById("toggle-sector").addEventListener("click", () => {
                const box = document.getElementById("sector-box-wrapper");
                const btn = document.getElementById("toggle-sector");

                if (box.style.display === "none") {
                    box.style.display = "block";
                    btn.innerText = "業種を選択 ▲";
                } else {
                    box.style.display = "none";
                    btn.innerText = "業種を選択 ▼";
                }
            });

            // 17業種一覧を取得
            fetch("/api/sectors")
                .then(res => res.json())
                .then(json => {
                    const box = document.getElementById("sector-box");

                    const sectors = json.sectors.filter(s => s !== "その他");
                    sectors.push("その他");

                    sectors.forEach(sec => {
                        const label = document.createElement("label");
                        label.innerHTML = `<input type="checkbox" class="sector" value="${sec}"> ${sec}`;
                        box.appendChild(label);
                    });
                });

            document.getElementById("sector-all").addEventListener("change", (e) => {
                const checked = e.target.checked;
                document.querySelectorAll(".sector").forEach(cb => cb.checked = checked);
                selectedSectors = checked
                    ? [...document.querySelectorAll(".sector")].map(x => x.value)
                    : [];
            });

            document.querySelectorAll("input[name='interval']").forEach(radio => {
                radio.addEventListener("change", () => {
                    currentInterval = radio.value;
                });
            });

            // 日経225チェックボックスの動作
            const nikkei225Checkbox = document.getElementById("nikkei225");
            nikkei225Checkbox.addEventListener("change", (e) => {
                const checked = e.target.checked;
                selectedNikkei225 = checked;

                if (checked) {
                    // 市場区分を全部オフ
                    document.querySelectorAll(".market").forEach(cb => cb.checked = false);
                    selectedMarkets = [];

                    // 17業種を全部オフ
                    document.querySelectorAll(".sector").forEach(cb => cb.checked = false);
                    selectedSectors = [];

                    // 全業種チェックもオフ
                    document.getElementById("sector-all").checked = false;
                }
            });

            // 市場区分を触ったら日経225をオフ
            document.addEventListener("change", e => {
                if (e.target.classList.contains("market")) {
                    selectedMarkets = [...document.querySelectorAll(".market:checked")].map(x => x.value);
                    if (selectedMarkets.length > 0) {
                        nikkei225Checkbox.checked = false;
                        selectedNikkei225 = false;
                    }
                }
            });

            // 業種を触ったら日経225をオフ
            document.addEventListener("change", e => {
                if (e.target.classList.contains("sector")) {
                    selectedSectors = [...document.querySelectorAll(".sector:checked")].map(x => x.value);
                    if (selectedSectors.length > 0) {
                        nikkei225Checkbox.checked = false;
                        selectedNikkei225 = false;
                    }
                }
            });

            document.getElementById("start-button").addEventListener("click", () => {
                drawing = true;

                const nextMarkets = [...document.querySelectorAll(".market:checked")].map(x => x.value);
                const nextSectors = [...document.querySelectorAll(".sector:checked")].map(x => x.value);
                const nextNikkei225 = document.getElementById("nikkei225").checked;

                const checkedInterval = document.querySelector("input[name='interval']:checked");
                const nextInterval = checkedInterval ? checkedInterval.value : "1d";

                const isMarketChanged = JSON.stringify(selectedMarkets) !== JSON.stringify(nextMarkets);
                const isSectorChanged = JSON.stringify(selectedSectors) !== JSON.stringify(nextSectors);
                const isNikkeiChanged = selectedNikkei225 !== nextNikkei225;
                const isIntervalSame = currentInterval === nextInterval;
                const isInitial = document.getElementById("app").innerHTML === "";

                selectedMarkets = nextMarkets;
                selectedSectors = nextSectors;
                selectedNikkei225 = nextNikkei225;

                document.getElementById("sector-box-wrapper").style.display = "none";
                document.getElementById("toggle-sector").innerText = "業種を選択 ▼";

                if (isInitial || isMarketChanged || isSectorChanged || isNikkeiChanged || isIntervalSame) {
                    currentInterval = nextInterval;

                    document.getElementById("app").innerHTML = "";
                    document.getElementById("loading").innerText = "読み込み中...";
                    page = 1;
                    globalIndex = 0;
                    loadNextPage();
                } else {
                    currentInterval = nextInterval;

                    const containers = document.querySelectorAll(".chart-container");

                    containers.forEach(container => {
                        const titleElement = container.querySelector(".chart-title");
                        const area = container.querySelector(".chart-area");

                        const titleText = titleElement.innerText.trim();
                        const tickerCode = titleText.split(" ")[0];

                        area.innerHTML = "<div style='padding:20px; color:#aaa; font-size:12px;'>足種更新中...</div>";

                        fetch(`/api/chart?ticker=${tickerCode}&interval=${currentInterval}`)
                            .then(res => res.json())
                            .then(json => {
                                if (!json.data) {
                                    area.innerText = "データ取得エラー";
                                    return;
                                }
                                area.innerHTML = "";

                                const chart = LightweightCharts.createChart(area, {
                                    layout: { backgroundColor: '#1c2030', textColor: '#d1d4dc' },
                                    grid: { vertLines: { color: '#2a2e39' }, horzLines: { color: '#2a2e39' } },
                                    handleScale: false,
                                    handleScroll: false,
                                    wheel: { scroll: false, pinch: false },
                                    touch: { mode: 'none' },
                                    drag: { scroll: false }
                                });

                                const series = chart.addCandlestickSeries({
                                    upColor: '#26a69a', downColor: '#ef5350',
                                    borderUpColor: '#26a69a', borderDownColor: '#ef5350',
                                    wickUpColor: '#26a69a', wickDownColor: '#ef5350'
                                });

                                series.setData(json.data);
                                chart.timeScale().fitContent();

                                function resizeChart() {
                                    const h = window.innerHeight * 0.23;
                                    chart.resize(area.clientWidth, h);
                                }
                                window.addEventListener('resize', resizeChart);
                                resizeChart();
                            })
                            .catch(() => {
                                area.innerText = "データ取得エラー";
                            });
                    });
                }
            });

            async function loadNextPage() {
                if (!drawing) return;
                if (loading) return;
                loading = true;

                const params = new URLSearchParams({
                    page: page,
                    markets: selectedMarkets.join(","),
                    sectors: selectedSectors.join(","),
                    nikkei225: selectedNikkei225 ? "1" : "0"
                });

                const res = await fetch(`/api/list?${params}`);
                const json = await res.json();

                if (!json.data || json.data.length === 0) {
                    document.getElementById("loading").innerText = "すべて読み込みました";
                    loading = false;
                    return;
                }

                for (const stock of json.data) {
                    globalIndex++;

                    if (globalIndex % 10 === 0) {
                        createAdBlock();
                    }

                    await createChartCard(stock.code, stock.name);
                }

                page++;
                loading = false;
            }

            function createAdBlock() {
                const app = document.getElementById('app');

                const ads = [
                    `
                    <!-- A8広告1 -->
                    <a href="あなたのA8リンク1"><img src="あなたの画像URL1"></a>
                    `,
                    `
                    <!-- A8広告2 -->
                    <a href="あなたのA8リンク2"><img src="あなたの画像URL2"></a>
                    `,
                    `
                    <!-- A8広告3 -->
                    <a href="あなたのA8リンク3"><img src="あなたの画像URL3"></a>
                    <!-- A8広告4 -->
                    <a href="あなたのA8リンク4"><img src="あなたの画像URL4"></a>
                    `,
                    `
                    <!-- A8広告5 -->
                    <a href="あなたのA8リンク5"><img src="あなたの画像URL5"></a>
                    `,
                    `
                    <!-- A8広告6 -->
                    <a href="あなたのA8リンク6"><img src="あなたの画像URL6"></a>
                    <!-- A8広告7 -->
                    <a href="あなたのA8リンク7"><img src="あなたの画像URL7"></a>
                    `,
                    `
                    <!-- A8広告8 -->
                    <a href="あなたのA8リンク2"><img src="あなたの画像URL8"></a>
                    `,
                    `
                    <!-- A8広告9 -->
                    <a href="あなたのA8リンク9"><img src="あなたの画像URL9"></a>
                    `
                ];

                const randomAd = ads[Math.floor(Math.random() * ads.length)];

                const ad = document.createElement('div');
                ad.className = 'ad-banner';
                ad.innerHTML = randomAd;

                app.appendChild(ad);
            }

            async function createChartCard(code, name) {
                const app = document.getElementById('app');

                const box = document.createElement('div');
                box.className = 'chart-container';

                const title = document.createElement('div');
                title.className = 'chart-title';
                title.innerText = `${code} ${name}`;
                box.appendChild(title);

                const area = document.createElement('div');
                area.className = 'chart-area';
                box.appendChild(area);

                app.appendChild(box);

                area.addEventListener("click", () => {
                    window.open(`https://finance.yahoo.co.jp/quote/${code}.T`, "_blank");
                });

                let touchStartY = 0;
                let touchEndY = 0;

                area.addEventListener("touchstart", (e) => {
                    touchStartY = e.changedTouches[0].clientY;
                });

                area.addEventListener("touchend", (e) => {
                    touchEndY = e.changedTouches[0].clientY;
                    const diff = Math.abs(touchEndY - touchStartY);
                    if (diff < 20) {
                        window.open(`https://finance.yahoo.co.jp/quote/${code}.T`, "_blank");
                    }
                });

                try {
                    const res = await fetch(`/api/chart?ticker=${code}&interval=${currentInterval}`);
                    const json = await res.json();

                    if (!json.data) {
                        area.innerText = "データ取得エラー";
                        return;
                    }

                    const chart = LightweightCharts.createChart(area, {
                        layout: { backgroundColor: '#1c2030', textColor: '#d1d4dc' },
                        grid: { vertLines: { color: '#2a2e39' }, horzLines: { color: '#2a2e39' } },
                        handleScale: false,
                        handleScroll: false,
                        wheel: { scroll: false, pinch: false },
                        touch: { mode: 'none' },
                        drag: { scroll: false }
                    });

                    const series = chart.addCandlestickSeries({
                        upColor: '#26a69a', downColor: '#ef5350',
                        borderUpColor: '#26a69a', borderDownColor: '#ef5350',
                        wickUpColor: '#26a69a', wickDownColor: '#ef5350'
                    });

                    series.setData(json.data);
                    chart.timeScale().fitContent();

                    function resizeChart() {
                        const h = window.innerHeight * 0.23;
                        chart.resize(area.clientWidth, h);
                    }
                    window.addEventListener('resize', resizeChart);
                    resizeChart();

                } catch (e) {
                    area.innerText = "データ取得エラー";
                }
            }

            window.addEventListener("scroll", () => {
                if (!drawing) return;
                if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 300) {
                    loadNextPage();
                }
            });
        </script>
    </body>
    </html>
    """


@app.route('/api/sectors')
def api_sectors():
    df = load_jpx_list()
    sectors = sorted(df["sector17"].unique().tolist())
    return jsonify({"sectors": sectors})


@app.route('/api/list')
def api_list():
    page = int(request.args.get("page", 1))
    per_page = 20

    markets = request.args.get("markets", "").split(",")
    sectors = request.args.get("sectors", "").split(",")
    nikkei225_flag = request.args.get("nikkei225", "0") == "1"

    df = load_jpx_list()

    if nikkei225_flag and NIKKEI225_CODES:
        df = df[df["code"].isin(NIKKEI225_CODES)]
    else:
        if markets and markets != [""]:
            df = df[df["market"].apply(
                lambda x: isinstance(x, str) and any(m in x for m in markets)
            )]

        if sectors and sectors != [""]:
            df = df[df["sector17"].apply(
                lambda x: isinstance(x, str) and any(s in x for s in sectors)
            )]

    df = df.sort_values(by="code", ascending=True)

    start = (page - 1) * per_page
    end = start + per_page

    data = df.iloc[start:end].to_dict(orient="records")
    return jsonify({"data": data})


@app.route('/api/chart')
def api_chart():
    ticker = request.args.get('ticker')
    interval = request.args.get('interval', "1d")

    try:
        data = fetch_real_data(ticker, interval=interval)
        return jsonify({"data": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)