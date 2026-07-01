from flask import Flask, jsonify, request
import yfinance as yf
import pandas as pd
import os
import datetime
import requests

app = Flask(__name__)

JPX_CSV_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
LOCAL_CSV = "jpx_list.xls"

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

    df = df.sort_values(by="code", ascending=True)

    return df[["code", "name", "market", "sector17"]]


from bs4 import BeautifulSoup


def load_nikkei225_list():
    print("固定リストから日経225銘柄を読み込みます")

    return [
        "1332", "1333", "1605", "1721", "1801", "1802", "1803", "1808", "1812",
        "1925", "1928", "1963", "2002", "2269", "2282", "2413", "2432", "2501",
        "2502", "2503", "2531", "2768", "2801", "2802", "2871", "2914", "3086",
        "3099", "3101", "3103", "3105", "3289", "3382", "3401", "3402", "3405",
        "3407", "3861", "3863", "4004", "4005", "4021", "4042", "4043", "4061",
        "4063", "4151", "4183", "4185", "4188", "4208", "4272", "4324", "4452",
        "4502", "4503", "4506", "4507", "4519", "4523", "4543", "4555", "4568",
        "4578", "4612", "4661", "4689", "4704", "4751", "4901", "4902", "4911",
        "5020", "5101", "5108", "5201", "5202", "5214", "5232", "5233", "5301",
        "5332", "5333", "5401", "5406", "5411", "5413", "5486", "5541", "5631",
        "5703", "5706", "5707", "5711", "5713", "5714", "5801", "5802", "5803",
        "5901", "6098", "6113", "6178", "6301", "6302", "6305", "6326", "6361",
        "6366", "6370", "6383", "6395", "6417", "6471", "6472", "6473", "6481",
        "6501", "6503", "6504", "6506", "6535", "6586", "6594", "6645", "6674",
        "6701", "6702", "6703", "6723", "6724", "6752", "6753", "6754", "6758",
        "6762", "6770", "6779", "6806", "6857", "6902", "6952", "6954", "6971",
        "6976", "6988", "7011", "7012", "7013", "7014", "7018", "7021", "7033",
        "7201", "7202", "7203", "7205", "7211", "7261", "7267", "7269", "7270",
        "7272", "7731", "7733", "7735", "7741", "7745", "7751", "7752", "7762",
        "7832", "7911", "7912", "7951", "8001", "8002", "8015", "8031", "8035",
        "8053", "8058", "8113", "8252", "8253", "8267", "8303", "8304", "8306",
        "8308", "8309", "8316", "8331", "8354", "8355", "8411", "8410", "8418",
        "8424", "8439", "8601", "8604", "8606", "8628", "8630", "8697", "8725",
        "8750", "8766", "8795", "8801", "8802", "8804", "8830", "9001", "9005",
        "9007", "9008", "9009", "9020", "9021", "9022", "9064", "9065", "9069",
        "9101", "9104", "9107", "9110", "9202", "9301", "9412", "9432", "9433",
        "9434", "9501", "9502", "9503", "9531", "9532", "9602", "9613", "9684",
        "9735", "9766", "9783", "9810", "9843", "9983", "9984"
    ]


NIKKEI225_CODES = load_nikkei225_list()


def fetch_real_data(ticker, interval="1d", period=None):
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
.ad-banner img {
    height: 100%;
    width: auto;
    object-fit: cover;
}

    body {
        margin: 0;
        padding: 0;
        background-color: #131722;
        color: #d1d4dc;
        font-family: sans-serif;
    }

#app {
    display: grid;
    grid-template-columns: 1fr 1fr;   /* 横に2列 */
    gap: 10px;                        /* チャート同士の余白 */
    width: 100%;
}


    /* ★ fixed → sticky に変更 */
    #filter-bar {
        position: sticky;
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

    #market-row {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        justify-content: flex-start;
    }

    .market-label,
    .filter-group label {
        font-size: 14px;
    }

    #nikkei225-box {
        font-size: 14px;
        margin-left: 8px;
        padding: 0;
        background: none;
        border: none;
        white-space: nowrap;
        display: flex;
        align-items: center;
    }

    #interval-row label {
        font-size: 14px;
    }

    /* ★ ボタン構造を完全統一 */
    .top-button {
        flex: 1 1 0;
        box-sizing: border-box;
        padding: 10px;
        background: #2a2e39;
        color: white;
        border-radius: 6px;
        font-size: 14px;
        height: 48px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
    }


/* ★ 描画開始だけ緑色に戻す */
#start-button {
    background: #26a69a;
}


    /* gap を使わず space-between に変更 */
#top-buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;   /* 横に2列 */
    gap: 10px;
    margin-right: 20px;               /* ★ 右端2cmくらい使わない */
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
    justify-content: space-between;   /* ← 左右に分かれる */
    align-items: center;
}

#interval-right {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-right: 8px;   /* ← PC画面が右端で切れないように調整 */
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

.pc-like-button {
    background: #4da3ff;
    color: white;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: bold;
    text-decoration: none;
    margin-right: 10px;
    cursor: pointer;
}


    @media (max-width: 480px) {
        .market-label,
        .filter-group label,
        #nikkei225-box,
        #interval-row label {
            font-size: 12px;
        }

        #market-row {
            gap: 6px;
        }

        .top-button {
            padding: 8px;
            height: 44px;
            font-size: 13px;
        }
    }
</style>

</head>
<body>

    <div id="filter-bar">

        <div id="site-title">東証チャートの縦流し</div>

        <h3>市場区分（複数選択可）</h3>
        <div id="market-row">
            <div class="filter-group">
                <label><input type="checkbox" class="market" value="プライム"> プライム</label>
                <label><input type="checkbox" class="market" value="スタンダード"> スタンダード</label>
                <label><input type="checkbox" class="market" value="グロース"> グロース</label>
            </div>

            <div class="filter-group" id="nikkei225-box">
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

    <div id="interval-right">
        <a id="notice-link" class="pc-like-button">注意事項▼</a>
        <a id="pc-link" href="https://あなたのPC版URL">スマホ画面</a>
    </div>
</div>

        <h3>17業種</h3>

        <div id="top-buttons">
            <div class="top-button" id="toggle-sector">業種を選択 ▼</div>
            <div class="top-button" id="start-button">描画開始</div>
        </div>

        <div id="sector-box-wrapper" style="display:none;">
            <div class="filter-group">
                <label><input type="checkbox" id="sector-all"> 全業種</label>
            </div>
            <div class="filter-group" id="sector-box"></div>
        </div>

    </div>

<div id="notice-box" style="display:none; background:#1c2030; padding:10px; border-radius:6px; margin-top:10px; color:#d1d4dc;">
    <p>・時間帯によっては描画開始を押しても「データ取得エラー」になる可能性があります。</p>
    <p>・本サイトのチャートはリアルタイムデータではありません。デイトレードに使用することを想定していません。スイングトレード、中長期投資の判断にご使用ください。</p>
    <p>・データ異常等で正しくチャートが表示されない可能性があります。投資の最終判断には証券会社等の信頼できるデータをご使用ください。</p>
    <p>・記載の注意事項を承諾の上ご使用ください。</p>
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


// ▼ 注意事項の開閉
document.getElementById("notice-link").addEventListener("click", () => {
    const box = document.getElementById("notice-box");
    const btn = document.getElementById("notice-link");

    if (box.style.display === "none") {
        box.style.display = "block";
        btn.innerText = "注意事項▲";
    } else {
        box.style.display = "none";
        btn.innerText = "注意事項▼";
    }
});





        // ▼ 業種折りたたみ
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

        // ▼ 17業種一覧を取得
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

        // ▼ 日経225チェックボックスの動作
        const nikkei225Checkbox = document.getElementById("nikkei225");
        nikkei225Checkbox.addEventListener("change", (e) => {
            const checked = e.target.checked;
            selectedNikkei225 = checked;

            if (checked) {
                document.querySelectorAll(".market").forEach(cb => cb.checked = false);
                selectedMarkets = [];

                document.querySelectorAll(".sector").forEach(cb => cb.checked = false);
                selectedSectors = [];

                document.getElementById("sector-all").checked = false;
            }
        });

        // ▼ 市場区分を触ったら日経225をオフ
        document.addEventListener("change", e => {
            if (e.target.classList.contains("market")) {
                selectedMarkets = [...document.querySelectorAll(".market:checked")].map(x => x.value);
                if (selectedMarkets.length > 0) {
                    nikkei225Checkbox.checked = false;
                    selectedNikkei225 = false;
                }
            }
        });

        // ▼ 業種を触ったら日経225をオフ
        document.addEventListener("change", e => {
            if (e.target.classList.contains("sector")) {
                selectedSectors = [...document.querySelectorAll(".sector:checked")].map(x => x.value);
                if (selectedSectors.length > 0) {
                    nikkei225Checkbox.checked = false;
                    selectedNikkei225 = false;
                }
            }
        });

        // ▼ 描画開始
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
				const marginRight = 80;  // ★ 右端の余白（2cm相当）
				chart.resize((window.innerWidth - marginRight) / 2, h);
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
                `<a href="あなたのA8リンク1"><img src="あなたの画像URL1"></a>`,
                `<a href="あなたのA8リンク2"><img src="あなたの画像URL2"></a>`,
                `<a href="あなたのA8リンク3"><img src="あなたの画像URL3"></a>`,
		`<a href="あなたのA8リンク4"><img src="あなたの画像URL4"></a>`,
                `<a href="あなたのA8リンク5"><img src="あなたの画像URL5"></a>`,
                `<a href="あなたのA8リンク6"><img src="あなたの画像URL6"></a>`,
		`<a href="あなたのA8リンク7"><img src="あなたの画像URL7"></a>`,
                `<a href="あなたのA8リンク8"><img src="あなたの画像URL8"></a>`,
                `<a href="あなたのA8リンク9"><img src="あなたの画像URL9"></a>`
            ];

            const randomAd = ads[Math.floor(Math.random() * ads.length)];

            const ad = document.createElement('div');
            ad.className = 'ad-banner';
            ad.innerHTML = randomAd;

	    // ★ チャートと同じ高さにする
	    const h = window.innerHeight * 0.25;
            const marginRight = 80;  // ★ 右端の余白（2cm相当）
	    ad.style.height = `${h}px`;

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
    layout: { backgroundColor: '#1c2030', textColor: '#333333' },  // ★ 文字色を濃く

    grid: {
        vertLines: { color: '#2a2e39' },
        horzLines: { color: '#2a2e39' }
    },

    // ★ 横軸の文字色
    timeScale: {
        borderColor: '#2a2e39',
        textColor: '#333333'
    },

    // ★ 縦軸の文字色
    priceScale: {
        borderColor: '#2a2e39',
        textColor: '#333333'
    },

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
                    const marginRight = 80;  // ★ 右端の余白（2cm相当）
		    chart.resize((window.innerWidth - marginRight) / 2, h);
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