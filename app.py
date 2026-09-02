import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import os

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="🎯 可轉債 (CB) 每日智慧監控雷達", layout="wide")
st.title("🎯 可轉債 (CB) 每日智慧監控雷達")

# --- 2. 爬取櫃買中心 (TPEx) 當日 CB 資料 (加入快取避免頻繁請求) ---
@st.cache_data(ttl=3600)  # 資料快取 1 小時，避免每次重整都去爬一次
def fetch_cb_data():
    try:
        # 櫃買中心公開行情資料 (範例 API / 格式)
        url = "https://www.tpex.org.tw/web/bond/tradeinfo/cb/cb_result.php?l=zh-tw"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        
        # 這裡以示範欄位建立 (實際串接時直接解析 API JSON / 網頁表格)
        # 櫃買中心提供：代碼、名稱、CB收盤價、標的股票代碼、標的股價、轉換價
        data = res.json().get('aaData', [])
        
        # 轉成 DataFrame 並整理欄位 (依實際回傳格式對應)
        df = pd.DataFrame(data)
        # 假設整理後的標準欄位：
        # df = df[['CB代號', 'CB名稱', 'CB市價', '現股市價', '最新轉換價']]
        return df
    except Exception as e:
        st.warning(f"資料擷取展示模式中（測試用）：{e}")
        # 提供一組測試假資料以供預覽網頁介面
        test_data = {
            "CB代號": ["12341", "23451", "34561", "45671"],
            "CB名稱": ["台塑一", "聯電二", "鴻海三", "廣達四"],
            "CB市價": [102.5, 98.0, 115.0, 104.0],
            "現股市價": [50.0, 48.0, 120.0, 95.0],
            "最新轉換價": [52.0, 45.0, 100.0, 100.0]
        }
        return pd.DataFrame(test_data)

# --- 3. 指標計算 ---
df = fetch_cb_data()

# 轉換價值 = (現股市價 / 最新轉換價) * 100
df['轉換價值'] = (df['現股市價'] / df['最新轉換價']) * 100
# 溢價率 = ((CB市價 - 轉換價值) / 轉換價值) * 100
df['溢價率(%)'] = ((df['CB市價'] - df['轉換價值']) / df['轉換價值']) * 100
df['轉換價值'] = df['轉換價值'].round(2)
df['溢價率(%)'] = df['溢價率(%)'].round(2)

# 篩選特定策略
negative_premium = df[df['溢價率(%)'] < 0]  # 負溢價（折價套利）
double_low = df[(df['CB市價'] <= 105) & (df['溢價率(%)'] <= 15)]  # 雙低防守型

# --- 4. AI 每日總結區塊 ---
st.subheader("💡 AI 每日盤後洞察")

api_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", None)

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # 組合 Prompt
    prompt = f"""
    你是一位專業的可轉債(CB)交易分析師。以下是今日篩選出的重點標的：
    【負溢價標的】: {negative_premium.to_dict(orient='records')}
    【雙低防守標的】: {double_low.to_dict(orient='records')}
    
    請用繁體中文以條列式輸出：
    1. 今日市場是否存在套利/負溢價亮點？
    2. 雙低標的中是否有值得留意的防守型標的？
    3. 給投資人的一句話風險提示。
    """
    
    if st.button("🤖 點擊生成今日 AI 深度點評"):
        with st.spinner("AI 正在分析全市場數據..."):
            response = model.generate_content(prompt)
            st.info(response.text)
else:
    st.info("💡 提示：設定 Gemini API Key 即可在此處啟用 AI 自動解讀功能。")

# --- 5. 數據表格呈現 (分頁籤 Tab 顯示) ---
st.divider()

tab1, tab2, tab3 = st.tabs(["🔥 負溢價標的 (折價套利)", "🛡️ 雙低防守標的", "📊 全市場 CB 清單"])

with tab1:
    st.markdown("##### 📌 轉換價值 > CB市價（溢價率為負，存在潛在套利或現股補漲空間）")
    st.dataframe(negative_premium, use_container_width=True)

with tab2:
    st.markdown("##### 📌 CB市價 <= 105 元 且 溢價率 <= 15%（下檔有保底、上檔有機會）")
    st.dataframe(double_low, use_container_width=True)

with tab3:
    # 搜尋與排序功能
    search = st.text_input("🔍 搜尋 CB 名稱或代號")
    if search:
        filtered_df = df[df['CB名稱'].str.contains(search) | df['CB代號'].str.contains(search)]
        st.dataframe(filtered_df, use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)
