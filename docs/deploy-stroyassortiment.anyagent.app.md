## Деплой фронтенда на `stroyassortiment.anyagent.app` через Nginx + Let’s Encrypt

Ниже инструкция для сервера, куда уже смотрит DNS.

### Что будет в итоге

- **Публичный вход**: `https://stroyassortiment.anyagent.app`
- **TLS/HTTPS**: Let’s Encrypt (certbot), авто-обновление
- **Nginx**: reverse proxy
  - `/` → Next.js фронтенд (`127.0.0.1:3000`)
  - `/api/` → backend `ai_service` (`127.0.0.1:15537` → container:5537)
- **Docker**: сервисы не торчат наружу, порты проброшены только на `127.0.0.1` (см. `docker-compose.yml`)

---

### 1) Поднять сервисы Docker (frontend + ai_service)

В корне проекта:

```bash
docker compose up -d --build
```

Проверка, что локально на сервере всё живое:

```bash
curl -I http://127.0.0.1:3000
curl -I http://127.0.0.1:15537/health || true
curl -I http://127.0.0.1:15537/docs || true
```

---

### 2) Установить Nginx

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y nginx
```

---

### 3) Добавить конфиг Nginx для домена

Создать webroot для ACME challenge:

```bash
sudo mkdir -p /var/www/letsencrypt
sudo chown -R www-data:www-data /var/www/letsencrypt
```

Первый запуск (пока **нет** сертификата): включаем **HTTP-only** конфиг из репозитория:

```bash
sudo mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
sudo cp ./deploy/nginx/stroyassortiment.anyagent.app.http.conf /etc/nginx/sites-available/stroyassortiment.anyagent.app.conf
sudo ln -sf /etc/nginx/sites-available/stroyassortiment.anyagent.app.conf /etc/nginx/sites-enabled/stroyassortiment.anyagent.app.conf
sudo nginx -t
sudo systemctl reload nginx
```

---

### 4) Выпустить сертификат Let’s Encrypt (certbot)

```bash
sudo apt install -y certbot
sudo certbot certonly --webroot \
  -w /var/www/letsencrypt \
  -d stroyassortiment.anyagent.app
```

---

### 5) Переключиться на HTTPS-конфиг и перезагрузить nginx

```bash
sudo cp ./deploy/nginx/stroyassortiment.anyagent.app.conf /etc/nginx/sites-available/stroyassortiment.anyagent.app.conf
sudo nginx -t
sudo systemctl reload nginx
```

---

### 6) Проверка

- Откройте в браузере: `https://stroyassortiment.anyagent.app`


