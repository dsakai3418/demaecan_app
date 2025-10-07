import streamlit as st
import pandas as pd
from datetime import datetime
import io

# 元のデータ処理関数
def process_csv_data(input_df):
    try:
        # 日付カラムをdatetime型に変換
        for col_name in ["設定完了締切日\n（記入日+N日　自動）", "記入日"]:
            if col_name in input_df.columns:
                input_df[col_name] = pd.to_datetime(input_df[col_name], errors='coerce')
            else:
                st.warning(f"Warning: カラム '{col_name}' が入力データに存在しません。")
                return None # カラムがない場合は処理を中断しNoneを返す

        # 本日日付を取得 (タイムスタンプを考慮しない日付のみの比較)
        today = datetime.now().date()

        # 本日日付の行をフィルタリング
        # NaT (Not a Time) は比較から除外される
        df_today = input_df[input_df["設定完了締切日\n（記入日+N日　自動）"].dt.date == today].copy()

        # 過去日付の行をフィルタリング (本日より前の日付)
        df_past = input_df[input_df["設定完了締切日\n（記入日+N日　自動）"].dt.date < today].copy()

        # 新しいカラムを初期化
        df_today["同一店舗CAMEL連携ID"] = None

        # 本日日付の各行について、過去データとの一致をチェック
        for index_today, row_today in df_today.iterrows():
            
            # 住所と電話番号の前処理関数
            def preprocess_string(s):
                if pd.isna(s):
                    return ""
                return str(s).replace(" ", "").replace("　", "").replace("-", "").strip()

            preprocessed_address_today = preprocess_string(row_today.get("店舗住所", None))
            preprocessed_phone_today = preprocess_string(row_today.get("店舗電話番号\n（固定）", None))

            for index_past, row_past in df_past.iterrows():
                preprocessed_address_past = preprocess_string(row_past.get("店舗住所", None))
                preprocessed_phone_past = preprocess_string(row_past.get("店舗電話番号\n（固定）", None))

                # 住所または電話番号が一致するかどうかをチェック
                address_match = (preprocessed_address_today != "" and preprocessed_address_today == preprocessed_address_past)
                phone_match = (preprocessed_phone_today != "" and preprocessed_phone_today == preprocessed_phone_past)

                if address_match or phone_match:
                    df_today.loc[index_today, "同一店舗CAMEL連携ID"] = row_past.get("CAMEL連携ID\n=店舗コード（自動）", None)
                    break # 一致する過去データが見つかったら、この行の処理を終了

        # 出力するカラムを選択 (今回追加: "設定完了締切日\n（記入日+N日　自動）")
        output_columns = [
            "no.",
            "店舗名",
            "CAMEL連携ID\n=店舗コード（自動）",
            "アクセストークン",
            "設定完了締切日\n（記入日+N日　自動）", # 追加
            "同一店舗CAMEL連携ID"
        ]
        
        # 存在しないカラムを除外して出力カラムを調整
        actual_output_columns = [col for col in output_columns if col in df_today.columns]
        
        # 必須カラムが不足している場合はエラーとする
        required_columns = ["no.", "店舗名", "CAMEL連携ID\n=店舗コード（自動）", "アクセストークン", "設定完了締切日\n（記入日+N日　自動）"]
        for col in required_columns:
            if col not in df_today.columns:
                st.error(f"エラー: 必須カラム '{col}' が入力データに存在しません。")
                return None

        df_output = df_today[actual_output_columns]
        
        # 日付カラムのフォーマットを調整 (必要であれば)
        if "設定完了締切日\n（記入日+N日　自動）" in df_output.columns:
            df_output["設定完了締切日\n（記入日+N日　自動）"] = df_output["設定完了締切日\n（記入日+N日　自動）"].dt.strftime('%Y-%m-%d')

        return df_output

    except Exception as e:
        st.error(f"データ処理中にエラーが発生しました: {e}")
        return None

# Streamlit UI部分
st.set_page_config(layout="wide") # レイアウトを広めに設定
st.title("CSVデータ処理アプリケーション")
st.write("CSVファイルをアップロードし、データ処理を実行します。")

uploaded_file = st.file_uploader("CSVファイルをアップロードしてください", type=["csv"])

if uploaded_file is not None:
    st.success("ファイルがアップロードされました。")
    
    # ファイルをPandas DataFrameとして読み込む
    try:
        file_content = uploaded_file.getvalue()
        try:
            df_input = pd.read_csv(io.BytesIO(file_content), encoding='utf-8')
        except UnicodeDecodeError:
            try:
                df_input = pd.read_csv(io.BytesIO(file_content), encoding='shift_jis')
            except UnicodeDecodeError:
                st.error("ファイルのエンコーディングを自動判別できませんでした。UTF-8またはShift-JISでファイルを保存し直してください。")
                df_input = None # df_inputをNoneに設定し、後続処理をスキップ
                
        if df_input is not None:
            st.subheader("アップロードされたデータのプレビュー")
            st.dataframe(df_input.head())

            # 処理開始ボタン
            if st.button("データ処理を開始"):
                with st.spinner("データ処理中..."):
                    processed_df = process_csv_data(df_input.copy()) # 元のDataFrameを保護するためにcopy()を使用
                    
                    if processed_df is not None:
                        st.subheader("処理結果")
                        st.dataframe(processed_df)

                        st.write("---") # 区切り線
                        st.subheader("処理結果のダウンロード")
                        
                        # Windows向け (Shift-JIS) - to_csvがbytesを返すためio.BytesIOは不要
                        # 正しくShift-JISでエンコードされることを確認
                        csv_windows = processed_df.to_csv(index=False, encoding='shift_jis').encode('shift_jis')
                        st.download_button(
                            label="ダウンロード (Windows向け - Shift-JIS)",
                            data=csv_windows,
                            file_name="processed_data_windows.csv",
                            mime="text/csv",
                            key='download_windows'
                        )
                        
                        # Mac向け (UTF-8 with BOM)
                        # UTF-8 with BOMはto_csvが直接生成できる
                        csv_mac = processed_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                        st.download_button(
                            label="ダウンロード (Mac向け - UTF-8)",
                            data=csv_mac,
                            file_name="processed_data_mac.csv",
                            mime="text/csv",
                            key='download_mac'
                        )
                        st.success("データ処理が完了しました。")
                    else:
                        st.error("データ処理に失敗しました。上記のエラーメッセージを確認してください。")

    except Exception as e:
        st.error(f"CSVファイルの読み込み中に予期せぬエラーが発生しました: {e}")
        st.info("CSVファイルの形式が不正である可能性があります。")
else:
    st.info("CSVファイルをアップロードしてください。")