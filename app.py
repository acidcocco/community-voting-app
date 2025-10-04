import streamlit as st
import pandas as pd
import qrcode
import io
import zipfile
from urllib.parse import urlencode
import matplotlib.pyplot as plt

# 初始化 session state
if "data" not in st.session_state:
    st.session_state.data = None

ISSUES = [
    "議題一：是否同意實施社區公設改善工程？",
    "議題二：是否同意調整社區管理費？"
]

# 固定 APP_URL（避免 st.runtime.get_url() 錯誤）
APP_URL = "https://acidcocco.onrender.com"

# 側邊欄 - QR Code 產生器
st.sidebar.header("QR Code 產生器")

if st.session_state.data is not None:
    # 批次產生所有戶號 QR Code
    if st.sidebar.button("產生所有 QR Code 壓縮檔"):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for household_id in st.session_state.data.index:
                params = {"戶號": household_id}
                full_url = f"{APP_URL}?{urlencode(params)}"
                qr = qrcode.make(full_url)
                img_byte_arr = io.BytesIO()
                qr.save(img_byte_arr, format="PNG")
                zip_file.writestr(f"{household_id}.png", img_byte_arr.getvalue())
        zip_buffer.seek(0)
        st.sidebar.download_button(
            "下載所有 QR Code 壓縮檔",
            data=zip_buffer,
            file_name="all_qrcodes.zip",
            mime="application/zip"
        )

    # 單一產生 QR Code
    household_selected = st.sidebar.selectbox(
        "選擇要產生 QR Code 的戶號：",
        st.session_state.data.index.tolist()
    )
    if household_selected:
        params = {"戶號": household_selected}
        full_url = f"{APP_URL}?{urlencode(params)}"
        qr = qrcode.make(full_url)
        img_byte_arr = io.BytesIO()
        qr.save(img_byte_arr, format="PNG")
        st.sidebar.image(qr, caption=f"戶號: {household_selected}")
        st.sidebar.download_button(
            "下載 QR Code 圖片",
            data=img_byte_arr.getvalue(),
            file_name=f"{household_selected}.png",
            mime="image/png"
        )

# 主頁面
st.title("社區區權會多議題投票應用程式")

# 上傳名冊
uploaded_file = st.file_uploader("請上傳區分所有權人名冊 (CSV)", type="csv")
if uploaded_file is not None:
    st.session_state.data = pd.read_csv(uploaded_file, dtype={"戶號": str})
    st.session_state.data.set_index("戶號", inplace=True)
    st.success("檔案上傳成功！")

# 讀取 URL 參數
query_params = st.query_params
household_id_from_url = query_params.get("戶號")
is_admin = query_params.get("admin") == "1"

# ========= 管理者頁面 =========
if is_admin:
    st.header("📊 管理者專用頁面")
    if st.session_state.data is None:
        st.warning("請先上傳名冊才能查看投票結果。")
    else:
        all_results = {}
        for i, issue in enumerate(ISSUES):
            st.subheader(issue)

            if f'vote_results_{i}' not in st.session_state:
                st.session_state[f'vote_results_{i}'] = pd.DataFrame(
                    columns=["戶號", "姓名", "區分比例", "投票"]
                )

            results = st.session_state[f'vote_results_{i}']
            all_results[issue] = results

            if results.empty:
                st.info("尚無投票紀錄")
            else:
                # 顯示完整投票明細
                st.dataframe(results, use_container_width=True)

                # 統計票數
                vote_count = results["投票"].value_counts().to_dict()
                agree_weight = results.loc[results["投票"] == "同意", "區分比例"].sum()
                disagree_weight = results.loc[results["投票"] == "不同意", "區分比例"].sum()

                st.write("📌 投票數統計：", vote_count)
                st.write(f"✅ 同意（加權）：{agree_weight}")
                st.write(f"❌ 不同意（加權）：{disagree_weight}")

                # 長條圖
                fig, ax = plt.subplots()
                results["投票"].value_counts().plot(kind="bar", ax=ax)
                st.pyplot(fig)

                # 圓餅圖
                fig, ax = plt.subplots()
                results["投票"].value_counts().plot(kind="pie", autopct='%1.1f%%', ax=ax)
                st.pyplot(fig)

                st.divider()

        # 匯出 Excel 報表
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            for issue, df in all_results.items():
                df.to_excel(writer, sheet_name=issue[:20], index=False)
        output.seek(0)
        st.download_button(
            "📥 匯出投票結果 Excel 報表",
            data=output,
            file_name="vote_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.stop()  # 管理者模式不會進到一般住戶頁面

# ========= 住戶投票頁 =========
st.header("住戶投票區")
st.divider()

if household_id_from_url:
    if st.session_state.data is None:
        st.error("請先請管理者上傳區分所有權人名冊。")
    else:
        if household_id_from_url in st.session_state.data.index:
            household_id = household_id_from_url
            voter_name = st.session_state.data.loc[household_id, "姓名"]
            st.info(f"歡迎 {voter_name} 戶！您的戶號是 **{household_id}**。")

            st.subheader("請對以下所有議題進行投票：")

            # 初始化投票紀錄
            for i, issue in enumerate(ISSUES):
                if f'vote_results_{i}' not in st.session_state:
                    st.session_state[f'vote_results_{i}'] = pd.DataFrame(
                        columns=["戶號", "姓名", "區分比例", "投票"]
                    )

            voted_issues_count = 0
            for i, issue in enumerate(ISSUES):
                st.markdown(f"**{issue}**")

                if household_id in st.session_state[f'vote_results_{i}']["戶號"].values:
                    st.success("您已完成此議題的投票。")
                    voted_issues_count += 1
                else:
                    vote_option = st.radio("您的選擇：", ("同意", "不同意"), key=f"radio_{i}")
                    if st.button(f"確認對「議題 {i+1}」投票", key=f"button_{i}"):
                        voter_data = st.session_state.data.loc[household_id]
                        new_vote = pd.DataFrame([{
                            "戶號": household_id,
                            "姓名": voter_data["姓名"],
                            "區分比例": voter_data["區分比例"],
                            "投票": vote_option
                        }])
                        st.session_state[f'vote_results_{i}'] = pd.concat(
                            [st.session_state[f'vote_results_{i}'], new_vote],
                            ignore_index=True
                        )
                        st.success(f"投票成功！感謝 {voter_name} 您的參與。")
                        st.rerun()

            if voted_issues_count == len(ISSUES):
                st.success("您已完成所有議題的投票！")
        else:
            st.error("您掃描的 QR Code 無效。請確認您使用的是正確的投票連結。")
else:
    st.warning("請掃描您的專屬 QR Code 以進行投票。")
