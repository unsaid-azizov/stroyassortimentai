import requests
from requests.auth import HTTPBasicAuth
basic = HTTPBasicAuth('Admin', '789654')

import json

# Получаем данные групп из 1С
res = requests.get(
    "http://172.16.77.34/stroyast_test/hs/Ai/GetGroups",
    auth=basic,
    headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
)
data = res.json()

print(type(data))
data = data['groups'][0]['items']

print(json.dumps(data, ensure_ascii=False, indent=2))
# res = requests.post("http://172.16.77.34/stroyast_test/hs/Ai/GetItems", json={"items": ["00-00023569"]}, auth=basic, headers={'Content-Type': 'application/json;  charset=utf-8"'})
# res.encoding = res.apparent_encoding
# print(res.text)

# res = requests.post("http://172.16.77.34/stroyast_test/hs/Ai/GetDetailedItems", json={"items": ["00-00009818"]}, auth=basic, headers={'Content-Type': 'application/json;  charset=utf-8"'})
# res.encoding = res.apparent_encoding
# print(res.text)