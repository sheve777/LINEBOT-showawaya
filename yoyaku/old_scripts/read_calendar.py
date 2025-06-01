import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# このプログラムがアクセスできるGoogleカレンダーの操作範囲を決めます。
# 今回は「読み取り専用」の権限を設定します。
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def main():
    """Googleカレンダーから直近10件の予定を取得して表示します。
    """
    creds = None
    # 'token.json' というファイルに、ユーザーのアクセストークンとリフレッシュトークンが保存されます。
    # これは、一度認証に成功すれば、次回から自動的に認証するために使われます。
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # 有効な認証情報がない場合は、ユーザーにログイン（認証）してもらいます。
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # credentials.json を読み込んで、認証フローを開始します。
            # 【重要】このプログラムと同じフォルダに credentials.json が必要です！
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0) # ブラウザが起動して認証画面が出ます

        # 次回のために、認証情報を 'token.json' に保存します。
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        # Google Calendar APIと通信するための「サービス」オブジェクトを作成します。
        service = build('calendar', 'v3', credentials=creds)

        # 現在時刻を取得します。
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' はUTC時刻であることを示します。

        print('直近10件の予定を取得します...')
        # カレンダーのイベント(予定)を取得します。
        # 'primary' は、メインのカレンダーを指定します。
        # timeMin=now で現在時刻以降の予定を取得します。
        # maxResults=10 で最大10件取得します。
        # singleEvents=True は、定期的な予定を個別の予定として扱います。
        # orderBy='startTime' は、開始時刻順に並べます。
        events_result = service.events().list(
            calendarId='primary', timeMin=now,
            maxResults=10, singleEvents=True,
            orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            print('予定は見つかりませんでした。')
            return

        # 取得した予定を表示します。
        print("取得した予定:")
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(f"- {start} : {event['summary']}") # 予定の開始日時と概要を表示

    except HttpError as error:
        print(f'エラーが発生しました: {error}')

if __name__ == '__main__':
    main()