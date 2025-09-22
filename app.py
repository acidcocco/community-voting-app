import streamlit as st
import pandas as pd
import io
import qrcode
import base64
import zipfile
from urllib.parse import urlencode
from PIL import Image, ImageDraw, ImageFont

# 應用程式標題與頁面設定
st.set_page_config(page_title="社區區權會投票")
st.title("社區區權會多議題投票應用程式")

# 設定您的應用程式公開網址
# 如果您重新部署或網址變動，請務必更新此處
APP_URL = "https://acidcocco-community-voting-app-mzmbfqfjngzhskk7ugsgai.streamlit.app"

# 設定議題清單
# --- 在這裡輸入您的所有議題內容 ---
ISSUES = [
    "議題一：是否同意實施社區公設改善工程？",
    "議題二：是否同意調整社區管理費？",
    "議題三：是否同意續聘現有物業管理公司？"
]

# 針對每個議題建立獨立的 vote_results DataFrame
for i, issue in enumerate(ISSUES):
    if f'vote_results_{i}' not in st.session_state:
        st.session_state[f'vote_results_{i}'] = pd.DataFrame(columns=['戶號', '姓名', '區分比例', '投票'])

if 'data' not in st.session_state:
    st.session_state.data = None

# --- 圖片處理函式 ---
def generate_qr_with_label(text, label):
    """
    生成帶有文字標註的 QR Code 圖片
    """
    # 產生 QR Code
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(text)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    # 建立一個新的圖片，寬度和高度足夠容納 QR Code 和文字
    width, height = img_qr.size
    img_final = Image.new("RGBA", (width, height + 50), "white")
    img_final.paste(img_qr, (0, 0))

    # 在圖片下方新增文字
    draw = ImageDraw.Draw(img_final)
    try:
        font = ImageFont.truetype("Arial.ttf", 30)
    except IOError:
        font = ImageFont.load_default()
    
    text_width = draw.textlength(label, font=font)
    
    text_x = (width - text_width) / 2
    text_y = height + 5
    draw.text((text_x, text_y), label, (0, 0, 0), font=font)

    return img_final

# -----------------
# 投票界面
# -----------------
st.header("住戶投票區")
st.divider()

query_params = st.query_params
household_id_from_url = query_params.get("戶號")

if household_id_from_url:
    if st.session_state.data is None:
        st.error("請先請管理者上傳區分所有權人名冊。")
    else:
        if household_id_from_url in st.session_state.data.index:
            household_id = household_id_from_url
            voter_name = st.session_state.data.loc[household_id, '姓名']
            st.info(f"歡迎 {voter_name} 戶！您的戶號是 **{household_id}**。")

            st.subheader("請對以下所有議題進行投票：")
            
            voted_issues_count = 0
            for i, issue in enumerate(ISSUES):
                st.markdown(f"**{issue}**")
                
                if household_id in st.session_state[f'vote_results_{i}']['戶號'].values:
                    st.success("您已完成此議題的投票。")
                    voted_issues_count += 1
                else:
                    vote_option = st.radio("您的選擇：", ('同意', '不同意'), key=f"radio_{i}")
                    
                    if st.button(f"確認對「議題 {i+1}」投票", key=f"button_{i}"):
                        voter_data = st.session_state.data.loc[household_id]
                        new_vote = pd.DataFrame([{
                            '戶號': household_id,
                            '姓名': voter_data['姓名'],
                            '區分比例': voter_data['區分比例'],
                            '投票': vote_option
                        }])
                        st.session_state[f'vote_results_{i}'] = pd.concat([st.session_state[f'vote_results_{i}'], new_vote], ignore_index=True)
                        st.success(f"投票成功！感謝 {voter_name} 您的參與。")
                        st.rerun()

            if voted_issues_count == len(ISSUES):
                st.success("您已完成所有議題的投票！")
                
        else:
            st.error("您掃描的 QR Code 無效。請確認您使用的是正確的投票連結。")
else:
    st.warning("請掃描您的專屬 QR Code 以進行投票。")

# -----------------
# 管理者報表區
# -----------------
st.sidebar.header("管理者專區")
st.sidebar.markdown("請先上傳名冊檔案")

uploaded_file = st.sidebar.file_uploader("上傳區分所有權人名冊 (Excel 檔案)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        required_columns = ['戶號', '姓名', '區分比例']
        if not all(col in df.columns for col in required_columns):
            st.sidebar.error("Excel 檔案中缺少必要的欄位。請確認檔案包含 '戶號', '姓名' 和 '區分比例'。")
        else:
            st.sidebar.success("檔案上傳成功！")
            st.session_state.data = df.set_index('戶號')
            
            st.sidebar.divider()
            st.sidebar.subheader("QR Code 產生器")
            
            # 批次產生 QR Code 功能
            st.sidebar.markdown("##### 批次產生所有戶號的 QR Code")
            if st.sidebar.button("產生所有 QR Code 壓縮檔"):
                if 'data' in st.session_state and not st.session_state.data.empty:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for household_id in st.session_state.data.index.tolist():
                            params = {'戶號': household_id}
                            full_url = f"{APP_URL}?{urlencode(params)}"
                            
                            img = generate_qr_with_label(full_url, f"戶號: {household_id}")
                            
                            img_buffer = io.BytesIO()
                            img.save(img_buffer, format="PNG")
                            img_buffer.seek(0)
                            
                            zipf.writestr(f"{household_id}_qrcode.png", img_buffer.read())
                    
                    st.sidebar.download_button(
                        label="下載 QR Code 壓縮檔",
                        data=zip_buffer.getvalue(),
                        file_name="all_qrcodes.zip",
                        mime="application/zip"
                    )
                    st.sidebar.success("QR Code 壓縮檔已產生！請點擊上方按鈕下載。")
                else:
                    st.sidebar.warning("請先上傳區分所有權人名冊。")

            st.sidebar.markdown("---")
            
            # 單一產生 QR Code 功能
            st.sidebar.markdown("##### 單一產生 QR Code")
            household_for_qr = st.sidebar.selectbox("請選擇要產生 QR Code 的戶號：", options=['請選擇'] + st.session_state.data.index.tolist())
            
            if household_for_qr != '請選擇':
                params = {'戶號': household_for_qr}
                full_url = f"{APP_URL}?{urlencode(params)}"
                
                img = generate_qr_with_label(full_url, f"戶號: {household_for_qr}")
                
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                st.sidebar.markdown(f"#### 戶號: {household_for_qr}")
                st.sidebar.image(img, caption="請掃描此 QR Code 進行投票")
                st.sidebar.download_button(
                    label="下載 QR Code 圖片",
                    data=buf.getvalue(),
                    file_name=f"{household_for_qr}_qrcode.png",
                    mime="image/png"
                )

    except Exception as e:
        st.sidebar.error(f"讀取檔案時發生錯誤：{e}")

# -----------------
# 報表顯示區
# -----------------
st.divider()
st.header("投票即時報表")
if st.session_state.data is not None:
    for i, issue in enumerate(ISSUES):
        st.subheader(f"📊 {issue}")
        vote_results = st.session_state[f'vote_results_{i}']

        if not vote_results.empty:
            total_votes = len(vote_results)
            st.info(f"目前總投票人數：{total_votes}")
            
            agree_votes = vote_results[vote_results['投票'] == '同意']
            disagree_votes = vote_results[vote_results['投票'] == '不同意']
            
            agree_count = len(agree_votes)
            disagree_count = len(disagree_votes)
            
            total_ratio = st.session_state.data['區分比例'].sum()
            agree_ratio = agree_votes['區分比例'].sum()
            disagree_ratio = disagree_votes['區分比例'].sum()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="同意票數", value=agree_count, delta=f"{agree_ratio:.2%}")
                st.write("區分比例：", f"{agree_ratio:.2%}")
            
            with col2:
                st.metric(label="不同意票數", value=disagree_count, delta=f"{disagree_ratio:.2%}")
                st.write("區分比例：", f"{disagree_ratio:.2%}")
                
            st.write("已投票清單：")
            st.dataframe(vote_results[['戶號', '姓名', '投票']])
        else:
            st.info("尚無投票記錄。")
        st.write("---")
else:
    st.info("請先上傳名冊檔案以查看報表。")
