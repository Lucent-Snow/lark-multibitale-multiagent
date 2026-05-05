import requests
import json
from urllib.parse import quote

APP_ID = 'cli_a97227cdd5f8dcef'
APP_SECRET = 'mdA8sTOIh3LImUNmwevcCfgys8VBomCd'
APP_TOKEN = 'Azf8bfMXRa5TQTsbPawckgyhnMh'
TABLE_ID = 'tbldiwNce1LYRnl1'

token_url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
resp = requests.post(token_url, json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = resp.json()['tenant_access_token']
headers = {'Authorization': 'Bearer ' + token}
url = 'https://open.feishu.cn/open-apis/bitable/v1/apps/' + APP_TOKEN + '/tables/' + TABLE_ID + '/records'

tests = [
    ('no quotes', 'AND(工单状态=待分派)'),
    ('encoded', quote('AND(工单状态="待分派")')),
    ('field format', '工单状态="待分派"'),
]

for name, f in tests:
    print('Test:', name, '->', f)
    r = requests.get(url, headers=headers, params={'filter': f})
    result = r.json()
    code = result.get('code')
    count = len(result.get('data', {}).get('items', []))
    print('  Code:', code, 'Count:', count)
    if code != 0 and code != 1254018:
        print('  Error:', result.get('msg'))
    print()