import datetime
import os.path
import json # JSONを扱うために追加

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def main():
    creds = None
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

    try:
        service = build('calendar', 'v3', credentials=creds)

        # --- ここから変更・注目ポイント ---

        # 検索したい日付と時刻を指定します
        # 例: 2025年6月15日の19:00から21:00 (日本時間で指定)
        # まずは日本時間でdatetimeオブジェクトを作成
        start_time_jp = datetime.datetime(2025, 6, 15, 19, 0, 0) # 年, 月, 日, 時, 分, 秒
        end_time_jp = datetime.datetime(2025, 6, 15, 21, 0, 0)   # 年, 月, 日, 時, 分, 秒

        # Google Calendar APIはUTC（協定世界時）で時刻を扱うため、日本時間からUTCに変換します。
        # 日本はUTCより9時間進んでいるので、9時間引きます。
        # (より正確にはタイムゾーン対応ライブラリを使うべきですが、今回はシンプルに)
        time_offset = datetime.timedelta(hours=9)
        start_time_utc = start_time_jp - time_offset
        end_time_utc = end_time_jp - time_offset

        # APIで使える形式 (ISOフォーマット文字列) に変換
        time_min = start_time_utc.isoformat() + 'Z'
        time_max = end_time_utc.isoformat() + 'Z'

        print(f"検索期間 (UTC): {time_min} から {time_max} まで")
        print(f"検索期間 (日本時間): {start_time_jp.strftime('%Y-%m-%d %H:%M:%S')} から {end_time_jp.strftime('%Y-%m-%d %H:%M:%S')} まで")


        events_result = service.events().list(
            calendarId='primary', # メインカレンダーを指定
            timeMin=time_min,     # 検索開始時刻
            timeMax=time_max,     # 検索終了時刻
            singleEvents=True,
            orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            print('その時間帯に予定は見つかりませんでした。')
            return

        print("\n見つかった予定:")
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', '(タイトルなし)') # タイトルがない場合もあるので対策
            description_str = event.get('description', '{}') # 説明がない場合は空のJSON文字列として扱う

            print(f"\n- 開始日時: {start}")
            print(f"  タイトル: {summary}")
            print(f"  説明欄(生の文字列): {description_str}")

            # 説明欄がJSON形式で書かれていると仮定して、内容を読み取ってみる
            try:
                # JSON文字列をPythonの辞書（キーと値のペアの集まり）に変換
                reservation_details = json.loads(description_str)
                if reservation_details: # 中身が空でなければ表示
                    print("  予約詳細 (JSONから読み取り):")
                    for key, value in reservation_details.items():
                        print(f"    {key}: {value}")
                else:
                    print("  予約詳細: (説明欄にJSON形式のデータがありません)")
            except json.JSONDecodeError:
                # JSONとして読み取れなかった場合 (ただの文字列だった場合など)
                print("  予約詳細: (説明欄はJSON形式ではありませんでした)")

        # --- ここまでが変更・注目ポイント ---

    except HttpError as error:
        print(f'エラーが発生しました: {error}')

if __name__ == '__main__':
    main()