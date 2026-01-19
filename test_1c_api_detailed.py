import requests
from requests.auth import HTTPBasicAuth
import json

basic = HTTPBasicAuth('Admin', '789654')
base_url = "http://172.16.77.34/stroyast_test/hs/Ai"

print("=" * 80)
print("1. GET /GetGroups - Получение всех групп номенклатуры")
print("=" * 80)
res = requests.get(f"{base_url}/GetGroups", auth=basic, headers={
    'Content-Type': 'application/json',
    'Accept': 'application/json'
})
groups_data = res.json()
print(f"Статус: {res.status_code}")
print(f"Количество групп: {len(groups_data.get('groups', []))}")
print("\nПример первой группы:")
if groups_data.get('groups'):
    first_group = groups_data['groups'][0]
    print(json.dumps(first_group, ensure_ascii=False, indent=2))
    print(f"\nВ первой группе '{first_group['название']}' товаров: {len(first_group.get('items', []))}")
    if first_group.get('items'):
        print("Пример товара из группы:")
        print(json.dumps(first_group['items'][0], ensure_ascii=False, indent=2))

        # Сохраним код группы и код номенклатуры для дальнейших тестов
        group_code = first_group['номенклатура']
        item_code = first_group['items'][0]['номенклатура']

print("\n" + "=" * 80)
print("2. POST /GetItems - Получение товаров группы с остатками и ценами")
print("=" * 80)
print(f"Запрашиваем группу: {group_code}")
res = requests.post(f"{base_url}/GetItems",
    json={"items": [group_code]},
    auth=basic,
    headers={'Content-Type': 'application/json; charset=utf-8'}
)
res.encoding = res.apparent_encoding
items_data = res.json()
print(f"Статус: {res.status_code}")
print(f"Количество товаров в ответе: {len(items_data.get('items', []))}")
print("\nПример первого товара:")
if items_data.get('items'):
    print(json.dumps(items_data['items'][0], ensure_ascii=False, indent=2))

print("\n" + "=" * 80)
print("3. POST /GetDetailedItems - Детальная информация по конкретной номенклатуре")
print("=" * 80)
print(f"Запрашиваем номенклатуру: {item_code}")
res = requests.post(f"{base_url}/GetDetailedItems",
    json={"items": [item_code]},
    auth=basic,
    headers={'Content-Type': 'application/json; charset=utf-8'}
)
res.encoding = res.apparent_encoding
detailed_data = res.json()
print(f"Статус: {res.status_code}")
print(f"Количество товаров в ответе: {len(detailed_data.get('items', []))}")
print("\nПолная информация по товару:")
if detailed_data.get('items'):
    print(json.dumps(detailed_data['items'][0], ensure_ascii=False, indent=2))

print("\n" + "=" * 80)
print("SUMMARY: Структура данных")
print("=" * 80)
print("""
1. GetGroups (GET):
   Response: { groups: [{ название, номенклатура (код группы), items: [{ номенклатура, название }] }] }

2. GetItems (POST) - для кодов ГРУПП:
   Request: { items: ["код_группы1", "код_группы2", ...] }
   Response: { items: [{ номенклатура, название, остатки, цены, ... }] }

3. GetDetailedItems (POST) - для кодов НОМЕНКЛАТУРЫ:
   Request: { items: ["код_номенклатуры1", "код_номенклатуры2", ...] }
   Response: { items: [{ номенклатура, название, детальные_остатки, цены, характеристики, ... }] }
""")
