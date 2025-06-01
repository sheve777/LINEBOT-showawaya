import datetime
import os.path
import json # JSONを扱うために追加

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- お店の基本情報 ---
TOTAL_COUNTER_SEATS = 11  # カウンターの総席数
TOTAL_TABLE_UNITS = 2     # テーブルの総卓数 (4人掛けが2つなので2卓)
# --------------------

def calculate_vacancy(target_datetime_start_jp, target_datetime_end_jp, calendar_service):
    """
    指定された日時の既存予約から、カウンターとテーブルの空き状況を計算する関数。
    """
    print(f"\n--- 空き状況計算開始 ({target_datetime_start_jp.strftime('%Y-%m-%d %H:%M')} JST) ---")

    # 1. 指定された日時範囲をUTCに変換 (前回と同じロジック)
    time_offset = datetime.timedelta(hours=9)
    start_time_utc = target_datetime_start_jp - time_offset
    end_time_utc = target_datetime_end_jp - time_offset
    time_min_utc_iso = start_time_utc.isoformat() + 'Z'
    time_max_utc_iso = end_time_utc.isoformat() + 'Z'

    print(f"検索期間 (UTC): {time_min_utc_iso} から {time_max_utc_iso}")

    # 2. Google Calendar APIで指定期間の予定を取得 (前回と同じロジック)
    try:
        events_result = calendar_service.events().list(
            calendarId='primary',
            timeMin=time_min_utc_iso,
            timeMax=time_max_utc_iso,
            singleEvents=True,
            orderBy='startTime').execute()
        events = events_result.get('items', [])
    except HttpError as error:
        print(f'カレンダーからの予定取得中にエラー: {error}')
        return -1, -1 # エラー時は空きなしとして扱う (例)

    # 3. 【新しい処理】既存予約から使用中のカウンター席数とテーブル卓数を集計
    current_used_counter_seats = 0
    current_used_table_units = 0

    if not events:
        print("指定期間に既存の予約はありませんでした。")
    else:
        print(f"{len(events)}件の既存予約が見つかりました。詳細を確認します...")
        for event in events:
            description_str = event.get('description', '{}')
            try:
                reservation_details = json.loads(description_str)
                if reservation_details: # JSONが空でないことを確認
                    seat_type = reservation_details.get('seat_type')
                    if seat_type == 'カウンター':
                        seats_this_booking = reservation_details.get('seats_used', 0)
                        current_used_counter_seats += seats_this_booking
                        print(f"  カウンター予約発見: {seats_this_booking}席使用")
                    elif seat_type == 'テーブル':
                        tables_this_booking = reservation_details.get('tables_used', 0)
                        current_used_table_units += tables_this_booking
                        print(f"  テーブル予約発見: {tables_this_booking}卓使用")
            except json.JSONDecodeError:
                # JSONパースエラーの場合は、予約詳細不明なので無視するかログに出す
                print(f"  注意: 予定「{event.get('summary', '(タイトルなし)')}」の説明欄はJSON形式ではありませんでした。")
            except TypeError:
                # reservation_detailsがNoneなどで.getできない場合など
                print(f"  注意: 予定「{event.get('summary', '(タイトルなし)')}」の説明欄の形式に問題がありました。")


    print(f"集計結果: 現在使用中のカウンター {current_used_counter_seats}席, テーブル {current_used_table_units}卓")

    # 4. 空き状況を計算
    available_counter_seats = TOTAL_COUNTER_SEATS - current_used_counter_seats
    available_table_units = TOTAL_TABLE_UNITS - current_used_table_units

    print(f"計算結果: 空きカウンター {available_counter_seats}席, 空きテーブル {available_table_units}卓")
    print("--- 空き状況計算終了 ---")

    return available_counter_seats, available_table_units

SCOPES = ['https://www.googleapis.com/auth/calendar']

def main():
    creds = None
    # ... (認証処理は前回と同じなので省略) ...
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    # ... (ここまで認証処理) ...

    try:
        service = build('calendar', 'v3', credentials=creds) # 認証済みのサービスオブジェクト

        # 【1】テスト用の予約リクエストを設定 (ここを色々変えてテストします)
        requested_guests = 3        # 例: 3名様
        requested_seat_type = "カウンター"  # 例: "カウンター" または "テーブル"

        # 【2】テスト用の日時を設定 (これもテストに応じて変更)
        test_start_time_jp = datetime.datetime(2025, 7, 2, 19, 0, 0)
        test_end_time_jp   = datetime.datetime(2025, 7, 2, 21, 0, 0)

        print(f"予約リクエスト: {requested_guests}名様、{requested_seat_type}希望")
        print(f"希望日時: {test_start_time_jp.strftime('%Y-%m-%d %H:%M')} - {test_end_time_jp.strftime('%H:%M')} JST")

        # 【3】空き状況を計算 (これは前回作った関数を呼び出す)
        available_counters, available_tables = calculate_vacancy(
            test_start_time_jp,
            test_end_time_jp,
            service
        )

        if available_counters == -1: # カレンダーアクセスエラーの場合
            print("エラー: 空き状況の計算中に問題が発生しました。")
            return # ここで処理を終了

        # 【4】予約可否判断ロジック
        print(f"\n--- 予約可否判断開始 ---")
        print(f"現在の空き: カウンター {available_counters}席, テーブル {available_tables}卓")

        reservation_possible = False  # 予約可能かどうかの旗 (最初は「不可」にしておく)
        message = ""                  # お客様へのメッセージ

        if requested_seat_type == "カウンター":
            if 1 <= requested_guests <= 4:  # カウンター希望で1～4名様の場合
                    if available_counters >= requested_guests: # まず、席が足りているか？
                        if (available_counters - requested_guests) >= 5: # 次に、予約後に5席以上空きが残るか？
                            reservation_possible = True
                            message = f"カウンター席 {requested_guests}名様でご予約可能です。(予約後も5席以上空きが残ります)"
                        else:
                            message = f"申し訳ありません。カウンター席のご予約後、十分な空き席(最低5席)を確保できないためお受けできません。(現在の空き: {available_counters}席。{requested_guests}名様のご予約で残り{available_counters - requested_guests}席となります)"
                    else:
                        message = f"申し訳ありません。カウンター席がご希望の人数({requested_guests}名様)分空いていません。(現在の空き: {available_counters}席)"
            else:  # カウンター希望で0名以下または5名様以上の場合
                    message = "申し訳ありません。カウンター席は1～4名様でのご案内となります。"

        elif requested_seat_type == "テーブル":
            if 1 <= requested_guests <= 2:  # テーブル希望で1～2名様の場合
                message = "申し訳ありません。テーブル席は3名様からのご案内となります。"
            elif 3 <= requested_guests <= 4:  # テーブル希望で3～4名様の場合 (1卓使用)
                if available_tables >= 1:
                    reservation_possible = True
                    message = f"テーブル席 {requested_guests}名様 (1卓利用)でご予約可能です。"
                else:
                    message = f"申し訳ありません。テーブル席が空いていません。(現在の空き: {available_tables}卓)"
            elif 5 <= requested_guests <= 8:  # テーブル希望で5～8名様の場合 (2卓使用)
                if available_tables >= 2:
                    reservation_possible = True
                    message = f"テーブル席 {requested_guests}名様 (2卓利用)でご予約可能です。"
                else:
                    message = f"申し訳ありません。ご希望の人数({requested_guests}名様)ですとテーブル2卓必要ですが、現在{available_tables}卓しか空いていません。"
            else:  # テーブル希望で0名以下または9名様以上の場合
                message = "申し訳ありません。テーブル席では8名様を超えるご予約、または1名様未満のご予約はお受けできません。9名様以上はお電話にてご相談ください。"
        else:
            message = "申し訳ありません。ご希望の席タイプが正しくありません。（「カウンター」または「テーブル」と入力してください）"

        # 【5】最終的な結果を表示
        if reservation_possible:
                print(f"【予約結果】: ★★★ ご予約可能です！ ★★★")
                print(f"   詳細: {message}")
                print("\n--- Googleカレンダーへの予約登録開始 ---")
                
                # 1. イベントのタイトルを作成
                event_summary = f"予約: {requested_guests}名様 ({requested_seat_type})"
                # 例: 「予約: 3名様 (カウンター)」のようなタイトルになります。

                # 2. イベントの説明欄に入れる予約詳細情報 (JSON形式) を作成
                event_description_details = {
                    "reservist_name": "（お客様名テスト）", # 将来的には入力してもらう
                    "number_of_guests": requested_guests,
                    "seat_type": requested_seat_type,
                    # "notes": "（何か備考があれば）" # 必要に応じて
                }
                # 予約された席の情報を追加
                if requested_seat_type == "カウンター":
                    event_description_details["seats_used"] = requested_guests 
                elif requested_seat_type == "テーブル":
                    if 1 <= requested_guests <= 4:
                        event_description_details["tables_used"] = 1
                    elif 5 <= requested_guests <= 8:
                        event_description_details["tables_used"] = 2
                
                # Pythonの辞書データをJSON形式の文字列に変換
                event_description_json = json.dumps(event_description_details, ensure_ascii=False, indent=2)
                # ensure_ascii=False で日本語がそのままJSONに入るようにし、indent=2 で見やすく整形

                # 3. APIで使う開始日時と終了日時の形式を準備 (日本時間を指定)
                # test_start_time_jp と test_end_time_jp は既にdatetimeオブジェクトのはず
                event_start = {
                    'dateTime': test_start_time_jp.isoformat(), # datetimeオブジェクトをISO形式文字列に
                    'timeZone': 'Asia/Tokyo', # 日本のタイムゾーンを指定
                }
                event_end = {
                    'dateTime': test_end_time_jp.isoformat(),   # datetimeオブジェクトをISO形式文字列に
                    'timeZone': 'Asia/Tokyo', # 日本のタイムゾーンを指定
                }

                # 4. カレンダーに登録するイベント本体を作成
                event_body = {
                    'summary': event_summary,             # 予定のタイトル
                    'description': event_description_json, # 予定の説明（JSON文字列）
                    'start': event_start,                 # 開始日時とタイムゾーン
                    'end': event_end,                     # 終了日時とタイムゾーン
                    # 他にも attendees (参加者) や reminders (通知) なども設定できます
                }

                # 5. Google Calendar APIを使ってイベントを登録！
                try:
                    print("カレンダーに新しい予定を作成しています...")
                    created_event = service.events().insert(
                        calendarId='primary', # メインカレンダーに登録
                        body=event_body       # 作成するイベントの内容
                    ).execute()
                    
                    print(f"\n★★★ Googleカレンダーに予約を登録しました！ ★★★")
                    print(f"  タイトル: {created_event.get('summary')}")
                    print(f"  開始日時: {created_event.get('start', {}).get('dateTime')}")
                    print(f"  イベントID: {created_event.get('id')}")
                    print(f"  確認用リンク: {created_event.get('htmlLink')}")

                except HttpError as error:
                    print(f"\n◆◆◆ カレンダーへの登録中にエラーが発生しました: {error} ◆◆◆")
                
                print("--- Googleカレンダーへの予約登録終了 ---")
        else:
            print(f"【予約結果】: ◆◆◆ 申し訳ありません、ご予約いただけません ◆◆◆")
            print(f"   理由: {message}")

        print("--- 予約可否判断終了 ---")

    except HttpError as error:
        print(f'main関数でエラーが発生しました: {error}')

if __name__ == '__main__':
    main()