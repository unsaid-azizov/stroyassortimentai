# WireGuard VPN Setup для доступа к 1С API

## Проблема

1С API находится во внутренней сети клиента по адресу `172.16.77.34:80` и недоступен напрямую из Docker контейнеров.

## Решение

Используем WireGuard VPN для проброса **только** 1С API сервера, без подключения ко всей внутренней сети.

## Конфигурация

### WireGuard Config ([backend/data/prg1c.conf](../backend/data/prg1c.conf))

```ini
[Interface]
PrivateKey = ODpLsu5x7pxoyYliEwY/rgZFFmGRAtVDNLdWIHGJKGw=
Address = 10.66.33.59/32,fd42:42:42::59/128
# DNS закомментирован чтобы не перезаписывать Docker DNS (127.0.0.11)
# DNS = 1.1.1.1,1.0.0.1

[Peer]
PublicKey = XP3hpB6s7mxX1lsU3+565gjHnGi8nWy11LVxC/c3D1I=
PresharedKey = yNRMc7TXoO+H7Qpx6xELRXpPWXjWpQ6qCHOfxdLIeQo=
Endpoint = 176.106.242.231:64666
# Пробрасываем только 1С API сервер, без всей внутренней сети
AllowedIPs = 172.16.77.34/32
```

**Ключевые моменты:**
- `AllowedIPs = 172.16.77.34/32` - маршрутизируем ТОЛЬКО 1С сервер
- `DNS` закомментирован - сохраняем Docker DNS (127.0.0.11) для резолвинга postgres/redis

### Docker Compose ([docker-compose.yml](../docker-compose.yml))

```yaml
api:
  cap_add:
    - NET_ADMIN      # Для настройки сетевых интерфейсов
    - SYS_MODULE     # Для загрузки kernel модулей
  sysctls:
    - net.ipv4.conf.all.src_valid_mark=1
    - net.ipv6.conf.all.disable_ipv6=0
  devices:
    - /dev/net/tun:/dev/net/tun  # TUN device для WireGuard
```

### Dockerfile ([backend/Dockerfile.api](../backend/Dockerfile.api))

```dockerfile
# Установка WireGuard и необходимых утилит
RUN apt-get update && apt-get install -y \
    wireguard-tools \
    iproute2 \
    iptables \
    openresolv \
    && rm -rf /var/lib/apt/lists/*
```

### Entrypoint Script ([backend/docker-entrypoint.sh](../backend/docker-entrypoint.sh))

```bash
# Настройка WireGuard для доступа к 1С API
if [ -f "/app/data/prg1c.conf" ]; then
  echo "Настройка WireGuard VPN для доступа к 1С..."
  wg-quick up /app/data/prg1c.conf || echo "WireGuard уже запущен или ошибка подключения"
fi
```

## Проверка работоспособности

### 1. Проверить WireGuard интерфейс

```bash
docker exec api wg show
```

Ожидаемый вывод:
```
interface: prg1c
  public key: ZW0c6QF/ghawyFyq/gOR6YxtXvNl2e7qTk3ODrVlZDE=
  private key: (hidden)
  listening port: XXXXX

peer: XP3hpB6s7mxX1lsU3+565gjHnGi8nWy11LVxC/c3D1I=
  preshared key: (hidden)
  endpoint: 176.106.242.231:64666
  allowed ips: 172.16.77.34/32
```

### 2. Проверить DNS (должен быть Docker DNS)

```bash
docker exec api cat /etc/resolv.conf
```

Ожидаемый вывод:
```
nameserver 127.0.0.11
```

### 3. Проверить доступ к 1С API

```bash
docker exec api python -c "
from tools.get_product_live_details import fetch_live_product_details
result = fetch_live_product_details(['00-00010232'])
print('✅ Success:', len(result), 'items')
"
```

### 4. Проверить доступ к PostgreSQL

```bash
docker exec api python check_db.py
```

Ожидаемый вывод: `PostgreSQL готов!`

## Troubleshooting

### Проблема: "Name or service not known" при подключении к postgres

**Причина:** WireGuard перезаписал `/etc/resolv.conf` своими DNS серверами

**Решение:** Убрать строку `DNS = ...` из `prg1c.conf`

### Проблема: Timeout при запросе к 1С API

**Причина:** WireGuard туннель не установлен или AllowedIPs не включает 172.16.77.34

**Решение:**
1. Проверить `wg show` - должен быть peer с endpoint
2. Проверить `AllowedIPs = 172.16.77.34/32` в конфиге

### Проблема: "Permission denied" при создании TUN device

**Причина:** Недостаточно capabilities у контейнера

**Решение:** Проверить что в docker-compose.yml есть:
- `cap_add: NET_ADMIN, SYS_MODULE`
- `devices: /dev/net/tun`

## Альтернативные решения

### SSH Port Forwarding

Если есть SSH доступ к jump-host в их сети:

```bash
ssh -N -L 8080:172.16.77.34:80 user@jump-host
```

Затем изменить в .env:
```
C1_DETAILED_API_URL=http://localhost:8080/stroyast_test/hs/Ai/GetDetailedItems
```

### TCP Proxy (socat)

Если нужен простой TCP проброс без VPN:

```bash
socat TCP-LISTEN:8080,fork TCP:172.16.77.34:80
```

## Безопасность

- ⚠️ WireGuard конфиг содержит приватные ключи - НЕ коммитить в git
- ⚠️ Файл `prg1c.conf` должен быть только для чтения владельца: `chmod 600`
- ✅ Пробрасываем только конкретный IP (172.16.77.34/32), не всю сеть
- ✅ Используем Pre-shared Key для дополнительной защиты

## Полезные команды

```bash
# Перезапустить WireGuard в контейнере
docker exec api wg-quick down prg1c
docker exec api wg-quick up /app/data/prg1c.conf

# Посмотреть маршруты
docker exec api ip route

# Проверить какие порты слушает контейнер
docker exec api netstat -tuln
```
