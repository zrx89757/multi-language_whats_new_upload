from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
import requests, time, json
from authlib.jose import jwt


KEY_ID = "123qaz"
ISSUER_ID = "12345678-8cc4-47e3-e053-22345678"
EXPIRATION_TIME = int(round(time.time() + (20.0 * 60.0))) # 20 minutes timestamp
PATH_TO_KEY = '/zzz/xxx/ccc/AuthKey_123qaz.p8'

with open(PATH_TO_KEY, 'r') as f:
    PRIVATE_KEY = f.read()

header = {
    "alg": "ES256",
    "kid": KEY_ID,
    "typ": "JWT"
}

payload = {
    "iss": ISSUER_ID,
    "exp": EXPIRATION_TIME,
    "aud": "appstoreconnect-v1"
}

# Create the JWT
token = jwt.encode(header, payload, PRIVATE_KEY)

# API Request
JWT = 'Bearer ' + token.decode()
HEAD = {'Authorization': JWT}

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
READ_TOKEN_PATH = "config/read_token.pickle"
# 文档id
SPREADSHEET_ID = '284hjhkdsf-Qki0'
# 工作表名称
SHEET_NAME = "2.16.0"
VERSION_NUMBER = "2.17.0"


APP_ID = "appid"

def read_whats_new():
    """获取 what's new 中 iOS 部分的内容
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(READ_TOKEN_PATH):
        with open(READ_TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('config/credentials.json', SCOPES)
        flow.authorization_url(prompt='select_account', include_granted_scopes='true')
        creds = flow.run_local_server(port=5000)

        # Save the credentials for the next run
        with open(READ_TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)

    service = build('sheets', 'v4', credentials=creds)
    # Call the Sheets API
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=SHEET_NAME).execute()

    values = result.get("values", [])
    if not values:
        print('google sheets 数据加载失败, 没有找到任何数据')
        return []
    for index, contents in enumerate(values):
        if not contents:
            # 为空就截断
            print("first empty index: ", index)
            break
    return values[:index]


def arrange_whats_new(text_array):
    """
    整理 whats new
    :param text_array: 从谷歌在线文档读取到的信息，是一个二维数组，数组中的每一行对应文档一行的内容
    :return: 整理好后的 whats new，形如 {'en': '1.xxxxx\n2.lllll\n', 'it': 'xxxx'}
    """
    matrix = []
    languanges = text_array[0]
    print("what's new languanges: ", languanges)
    count = len(languanges)
    for index, line in enumerate(text_array):
        if index != 0:
            if len(line) == count:
                matrix.append(line)
    whats_new = {}
    for i, lan in enumerate(languanges):
        text = ''
        for line in matrix:
            copywriting = line[i]
            if copywriting == 'n':
                text += '\n'
            else:
                text += (copywriting + '\n')
        whats_new[lan] = text
    return whats_new


def target_app_store_version_id(app_id):
    url = f'https://api.appstoreconnect.apple.com/v1/apps/{app_id}/appStoreVersions'
    r = requests.get(url, headers=HEAD)
    response_json = json.dumps(r.json(), indent=4)
    dict = json.loads(response_json)
    for v in dict["data"]:
        if v["attributes"]["versionString"] == VERSION_NUMBER:
            break
    return v["id"]


def app_store_version_localizations(version_id):
    url = f'https://api.appstoreconnect.apple.com/v1/appStoreVersions/{version_id}/appStoreVersionLocalizations'
    r = requests.get(url, headers=HEAD)
    response_json = json.dumps(r.json(), indent=4)
    dict = json.loads(response_json)
    return dict["data"]


def patch_localization_whats_new(id, whats_new):
    url = f'https://api.appstoreconnect.apple.com/v1/appStoreVersionLocalizations/{id}'
    payload = {'data': {
        'type': 'appStoreVersionLocalizations',
        'id': id,
        'attributes': {
            'whatsNew': whats_new
        }
    }}
    data = json.dumps(payload)
    head = {'Authorization': JWT,
            'Content-Type': 'application/json'}
    r = requests.patch(url, data=data, headers=head)
    response_json = json.dumps(r.json(), indent=4)
    print(response_json)


def main():
    ios_content = read_whats_new()
    if not ios_content:
        print("what's new is not found!")
        exit(-1)

    whats_new_dict = arrange_whats_new(ios_content)
    print(whats_new_dict)

    version_id = target_app_store_version_id(APP_ID)
    localizations = app_store_version_localizations(version_id)

    all_keys = whats_new_dict.keys()
    for l in localizations:
        for key in all_keys:
            # 为什么用 find 不用 ==，因为 api 中的 locale 会带上国别码，如 fr-FR， pt-PT
            if l["attributes"]["locale"].find(key) != -1:
                patch_localization_whats_new(l["id"], whats_new_dict[key])


if __name__ == '__main__':
    main()
