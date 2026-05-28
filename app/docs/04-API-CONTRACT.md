# 04 — API-CONTRACT.md

Kontrak API antara Flutter app (Emas Berlian Insight) dan backend Codi (`hansrayb/codi`).

> **Catatan**: Endpoint di bawah ini adalah **target contract**. Sebelum implementasi Flutter, pastikan endpoint sudah tersedia di Codi backend. Jika belum ada, prioritaskan menambahkan endpoint dulu di Codi.

---

## Base URL

| Environment | URL |
|---|---|
| Local dev | `http://localhost:8787/api/v1` |
| Staging | `https://staging.codi.lumbungemas.internal/api/v1` |
| Production | `https://codi.lumbungemas.internal/api/v1` |

URL config disimpan di `lib/config/env.dart` dan switch via `--dart-define`.

---

## Authentication

### Mekanisme

- JWT Bearer Token (HS256), payload bawa `sub`, `email`, `role`, `scopes`.
- Login pertama: email + password → JWT access + refresh.
- Login berikutnya: biometric local + `device_id + device_fingerprint`
  yang sudah di-enroll → JWT.
- Token disimpan di `flutter_secure_storage`.
- Access TTL default 7 hari, refresh TTL 30 hari (configurable di server).

### Header

Setiap request (kecuali endpoint public auth) wajib include:

```
Authorization: Bearer <jwt-token>
Content-Type: application/json
Accept: application/json
X-Client: emas-berlian-insight
X-Client-Version: 1.0.0
```

### Roles & Scopes

| Role | Slug | Scopes |
|---|---|---|
| Super Admin | `superadmin` | `accounts:*`, `dashboard:read`, `reports:*`, `chat:use`, `insight:read` |
| Admin | `admin` | `accounts:read`, `accounts:update_role`, `dashboard:read`, `reports:*`, `chat:use`, `insight:read` |
| Direksi | `director` | `dashboard:read`, `reports:read`, `chat:use`, `insight:read` |
| Viewer | `viewer` | `dashboard:read`, `insight:read` |

RBAC dicek server-side via `scopes` di JWT. Client juga store `scopes` untuk
hide/show menu (mis. row "Kelola Akun" hanya muncul jika `accounts:read`).

Superadmin diseed di server lewat `python -m scripts.seed_auth` dengan env
`SUPERADMIN_EMAIL` dan `SUPERADMIN_PASSWORD`. Superadmin tak bisa dihapus
atau di-suspend dari mobile.

### Bootstrap token (legacy)

Kalau server di-set `ALLOW_BOOTSTRAP_TOKEN=true` dan `DEVICE_API_SHARED_TOKEN`
ada, request dengan Bearer = shared-token tetap diterima dengan scope minimal
(`dashboard:read`, `insight:read`, `chat:use`) untuk kompatibilitas Fase A1.
Tidak bisa akses `/accounts/*` atau `/auth/enroll-biometric`.

---

## Endpoints

### 1. Authentication

Fase B — auth real berbasis akun (email + password) di server Codi. Login
pertama: email + password → JWT. Setelah login, app enroll device fingerprint
agar login berikutnya cukup tap biometric. JWT membawa `scopes[]` untuk RBAC.

#### `POST /auth/login`

Login email + password (mode bootstrap & untuk akun baru).

**Request**:
```json
{
  "email": "hans@emasberlian.com",
  "password": "<password>"
}
```

**Response 200**:
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "expires_in": 604800,
  "scopes": [
    "accounts:read", "accounts:create", "accounts:update", "accounts:delete",
    "dashboard:read", "reports:read", "reports:write", "chat:use", "insight:read"
  ],
  "user": {
    "id": "acc_a1b2c3d4",
    "email": "hans@emasberlian.com",
    "name": "Hans",
    "title": "Super Admin",
    "role": "superadmin",
    "status": "active",
    "created_at": "2026-05-28T10:00:00+00:00",
    "last_login_at": "2026-05-28T10:05:00+00:00"
  }
}
```

**Response 401**:
- `invalid_credentials` — email/password salah
- `account_suspended` — akun di-suspend superadmin

**Response 429** — too many failed attempts:
```json
{
  "error": { "code": "too_many_attempts",
             "message": "Terlalu banyak percobaan gagal. Coba lagi dalam 5 menit." }
}
```

#### `POST /auth/login-biometric`

Login pakai device yang sudah di-enroll. App lokal hanya validasi biometric;
server cocokkan `device_id + device_fingerprint` ke binding tabel.

**Request**:
```json
{
  "device_id": "pixel-9-hans-2026",
  "device_fingerprint": "sha256:abc123..."
}
```

**Response 200**: sama bentuk dengan `/auth/login`.

**Response 401** — `device_not_enrolled`: device belum di-bind ke akun. App
arahkan ke flow email+password lagi.

#### `POST /auth/enroll-biometric` (authed)

Bind device fingerprint ke akun yang sedang login (token Bearer wajib).
Bootstrap token (legacy) tidak diizinkan memanggil endpoint ini.

**Request**:
```json
{
  "device_id": "pixel-9-hans-2026",
  "device_fingerprint": "sha256:abc123...",
  "platform": "android"
}
```

**Response 200**:
```json
{
  "binding_id": "dvc_a1b2c3d4",
  "device_id": "pixel-9-hans-2026",
  "platform": "android",
  "enrolled_at": "2026-05-28T10:08:00+00:00"
}
```

#### `POST /auth/refresh`

Refresh access token.

**Request**:
```json
{ "refresh_token": "eyJhbGc..." }
```

**Response 200**: same shape as `/auth/login` (token + scopes + user).

#### `POST /auth/logout`

Invalidate token client-side (server stateless untuk Fase B; logout = drop
token di app).

**Response 200**: `{ "ok": true }`

---

### 1b. Account Management (RBAC: `accounts:*`)

Visible di mobile lewat sub-page Profile → "Kelola Akun" (S7). Superadmin
punya semua scope; admin punya `accounts:read` + `accounts:update_role`.

#### `GET /accounts` — list semua akun

Scope: `accounts:read`.

**Response 200**:
```json
{
  "accounts": [
    {
      "id": "acc_a1b2c3d4", "email": "hans@emasberlian.com", "name": "Hans",
      "title": "Super Admin", "role": "superadmin", "status": "active",
      "created_at": "2026-05-28T10:00:00+00:00",
      "last_login_at": "2026-05-28T10:05:00+00:00"
    }
  ]
}
```

#### `GET /accounts/roles`

Scope: `accounts:read`. List role + scope yang tersedia.

**Response 200**:
```json
{
  "roles": [
    { "slug": "superadmin", "name": "Super Admin",
      "scopes": ["accounts:read", "accounts:create", "accounts:update",
                 "accounts:delete", "dashboard:read", "reports:read",
                 "reports:write", "chat:use", "insight:read"] },
    { "slug": "admin",   "name": "Admin",   "scopes": [...] },
    { "slug": "director","name": "Direksi", "scopes": [...] },
    { "slug": "viewer",  "name": "Viewer",  "scopes": [...] }
  ]
}
```

#### `POST /accounts` — buat akun baru

Scope: `accounts:create`.

**Request**:
```json
{
  "email": "leo@lumbungemas.co.id",
  "password": "<min 8 char>",
  "name": "Leo Sastra C.W.",
  "title": "Direktur Utama",
  "role": "director"
}
```

**Response 201**: bentuk akun (sama dengan item di GET /accounts).
**Response 409** — `email_exists`.

#### `PATCH /accounts/{id}/role`

Scope: `accounts:update` atau `accounts:update_role`. Superadmin lain tak
bisa diubah (server reject 403 `forbidden`).

**Request**: `{ "role": "viewer" }` → Response 200 (akun updated).

#### `PATCH /accounts/{id}/status`

Scope: `accounts:update`. Status: `active` | `suspended`.

#### `PATCH /accounts/{id}/password`

Scope: `accounts:update`. Reset password (min 8 char).

**Request**: `{ "password": "<new password>" }` → Response 200 `{ "ok": true }`.

#### `DELETE /accounts/{id}`

Scope: `accounts:delete`. Superadmin tak bisa dihapus. Tidak bisa hapus akun
sendiri.

**Response 204** (no content).

#### `GET /accounts/{id}/devices`

Scope: `accounts:read`. List device binding milik akun.

#### `DELETE /accounts/{id}/devices/{binding_id}`

Scope: `accounts:update`. Revoke binding (mark `revoked_at`). Device tak
bisa login biometric lagi sampai re-enroll.

---

### 2. Dashboard

#### `GET /dashboard/summary`

Ringkasan untuk Dashboard screen.

**Query params**:
- `period`: `today` | `week` | `month` | `year` (default: `month`)
- `tz`: timezone (default: `Asia/Jakarta`)

**Response 200**:
```json
{
  "period": "month",
  "period_label": "Mei 2026",
  "period_range": {
    "start": "2026-05-01",
    "end": "2026-05-17"
  },
  "is_partial": true,
  "days_elapsed": 17,
  "days_in_period": 31,
  "updated_at": "2026-05-17T09:28:00+07:00",
  
  "revenue": {
    "total": 828882000,
    "currency": "IDR",
    "growth_mom_pct": 321.0,
    "projection_full_period": 1510000000,
    "sparkline": [
      {"date": "2026-05-11", "value": 35000000},
      {"date": "2026-05-12", "value": 58000000},
      {"date": "2026-05-13", "value": 33000000},
      {"date": "2026-05-14", "value": 70000000},
      {"date": "2026-05-15", "value": 82000000},
      {"date": "2026-05-16", "value": 66000000},
      {"date": "2026-05-17", "value": 93000000}
    ],
    "breakdown": {
      "retail": {"value": 656115000, "orders": 15, "weight_gram": 240.6},
      "rotasi": {"value": 172767000, "orders": 40, "weight_gram": 63.5}
    }
  },
  
  "quick_stats": {
    "orders_total": 55,
    "orders_retail": 15,
    "orders_rotasi": 40,
    "conversion_rate_pct": 68.8,
    "conversion_rate_delta_pct": -31.2,
    "expense_total": 10857500,
    "expense_pct_of_revenue": 1.3
  },
  
  "ai_summary": {
    "id": "summary_2026051709",
    "generated_at": "2026-05-17T09:14:00+07:00",
    "model": "claude-sonnet-4-6",
    "tone": "executive_formal",
    "status": "healthy",
    "paragraphs": [
      {
        "type": "positive",
        "text": "Operasional kantor berada dalam kondisi sehat. Omzet Mei sudah melampaui April..."
      },
      {
        "type": "warning",
        "text": "Yang memerlukan perhatian: conversion rate turun ke 68,8%..."
      },
      {
        "type": "note",
        "text": "Beban komisi tetap rendah di 1,3% dari omzet — rasio yang sangat sehat."
      }
    ],
    "data_points_count": 12,
    "sources": ["payment_orders", "user_levels", "finance_ledger"]
  },
  
  "highlights": [
    {
      "id": "hl_001",
      "severity": "green",
      "title": "Penjualan emas retail kembali aktif",
      "description": "Rp 656 jt dari 15 order (240,6g) — bulan April nol penjualan retail.",
      "timestamp": "2026-05-14T14:30:00+07:00",
      "category": "revenue"
    },
    {
      "id": "hl_002",
      "severity": "red",
      "title": "24 order expired bulan ini",
      "description": "Total nilai Rp 127 jt tidak terbayar — conversion rate turun dari 100% ke 68,8%.",
      "timestamp": "2026-05-17T09:20:00+07:00",
      "category": "conversion"
    },
    {
      "id": "hl_003",
      "severity": "info",
      "title": "Payroll Mei sudah ter-generate",
      "description": "22 karyawan · total Rp 159 jt · sedang menunggu finalisasi oleh HRGA.",
      "timestamp": "2026-05-15T16:45:00+07:00",
      "category": "hr"
    }
  ],
  
  "chart_daily": {
    "label": "Tren Omzet 7 Hari Terakhir",
    "subtitle": "Penjualan emas vs Rotasi",
    "data": [
      {
        "date": "2026-05-11",
        "label": "11",
        "retail": 32000000,
        "rotasi": 18000000
      }
      // ... 7 hari
    ]
  }
}
```

---

#### `GET /dashboard/insight`

Analisis mendalam untuk Insight screen.

**Query params**: sama dengan summary

**Response 200**:
```json
{
  "period": "month",
  "period_label": "1 – 17 Mei 2026",
  "updated_at": "2026-05-17T09:28:00+07:00",
  
  "kpis": [
    {
      "key": "revenue_total",
      "label": "Omzet Total",
      "value": 828882000,
      "unit": "IDR",
      "delta_pct": 321.0,
      "delta_label": "+321% MoM",
      "trend": "up"
    },
    {
      "key": "orders_settled",
      "label": "Order Settled",
      "value": 55,
      "unit": "tx",
      "delta_label": "15 retail · 40 rotasi",
      "trend": "up"
    },
    {
      "key": "avg_ticket",
      "label": "Avg. Ticket",
      "value": 15070000,
      "unit": "IDR",
      "delta_pct": 21.8,
      "delta_label": "+21,8%",
      "trend": "up"
    },
    {
      "key": "potential_lost",
      "label": "Potensi Hilang",
      "value": 127151000,
      "unit": "IDR",
      "delta_label": "24 order expired",
      "trend": "down"
    }
  ],
  
  "composition": {
    "label": "Komposisi Omzet",
    "total": 828882000,
    "segments": [
      {"label": "Penjualan Emas", "value": 656115000, "pct": 79.2, "color": "gold"},
      {"label": "Rotasi Masuk", "value": 172767000, "pct": 20.8, "color": "navy"}
    ]
  },
  
  "ai_analysis": {
    "id": "analysis_2026051709",
    "generated_at": "2026-05-17T09:14:00+07:00",
    "sections": [
      {
        "type": "healthy",
        "title": "Yang Sehat",
        "content": "Omzet Mei naik tajam ke Rp 828,8 jt..."
      },
      {
        "type": "attention",
        "title": "Yang Perlu Perhatian",
        "content": "Conversion rate turun dari 100% di April ke 68,8%..."
      },
      {
        "type": "note",
        "title": "Catatan",
        "content": "Data sistem baru sejak April 2026..."
      }
    ],
    "metadata": {
      "data_points": 12,
      "sources_count": 4,
      "confidence": "high"
    }
  }
}
```

---

### 3. Chat (Codi)

#### `POST /chat/messages`

Kirim pesan ke Codi.

**Request**:
```json
{
  "conversation_id": "conv_001" | null,
  "message": "Bagaimana kondisi operasional hari ini, Codi?",
  "context": {
    "screen": "dashboard",
    "period": "month"
  }
}
```

**Response 200** (non-streaming):
```json
{
  "conversation_id": "conv_001",
  "message_id": "msg_xyz",
  "role": "assistant",
  "content": {
    "type": "rich",
    "text": "Selamat pagi Bapak Leo. Berikut ringkasan kondisi kantor hari ini:",
    "card": {
      "title": "Status Mei 2026",
      "badge": {"label": "SEHAT", "color": "green"},
      "rows": [
        {"label": "Omzet", "value": "Rp 828,8 jt", "trend": "up"},
        {"label": "Pertumbuhan MoM", "value": "+321%", "trend": "up"},
        {"label": "Conv. Rate", "value": "68,8%", "trend": "down"},
        {"label": "Beban Komisi", "value": "1,3% omzet"}
      ],
      "inline_chart": {
        "type": "sparkline",
        "data": [48, 45, 50, 38, 30, 24, 18, 10]
      },
      "actions": [
        {"label": "Lihat Ringkasan", "deep_link": "/insight?period=month"},
        {"label": "Export PDF", "action": "export_pdf"}
      ]
    }
  },
  "suggestions": [
    "Perbandingan dengan April",
    "Proyeksi akhir bulan",
    "Status karyawan"
  ],
  "metadata": {
    "response_time_ms": 820,
    "model": "claude-sonnet-4-6",
    "tokens_used": 1240
  }
}
```

**Response 200** (streaming via SSE):

Endpoint sama dengan `Accept: text/event-stream` header.

```
event: token
data: {"text": "Selamat"}

event: token
data: {"text": " pagi"}

event: token
data: {"text": " Bapak"}

event: card
data: {"card": {...}}

event: done
data: {"message_id": "msg_xyz", "metadata": {...}}
```

---

#### `GET /chat/conversations`

List recent conversations.

**Query params**:
- `limit`: int, default 20
- `cursor`: string (pagination)

**Response 200**:
```json
{
  "conversations": [
    {
      "id": "conv_001",
      "title": "Kondisi operasional bulan Mei",
      "last_message_at": "2026-05-17T09:44:00+07:00",
      "message_count": 4,
      "preview": "Tiga hal yang sebaiknya Bapak ketahui..."
    }
  ],
  "next_cursor": null
}
```

---

#### `GET /chat/conversations/{id}/messages`

Get messages dalam satu conversation.

**Response 200**:
```json
{
  "conversation_id": "conv_001",
  "messages": [
    {
      "id": "msg_001",
      "role": "user",
      "content": {"type": "text", "text": "Bagaimana..."},
      "timestamp": "2026-05-17T09:42:00+07:00"
    },
    {
      "id": "msg_002",
      "role": "assistant",
      "content": {"type": "rich", "text": "...", "card": {...}},
      "timestamp": "2026-05-17T09:42:01+07:00"
    }
  ]
}
```

---

### 4. User & Profile

#### `GET /me`

Get current user info.

**Response 200**:
```json
{
  "id": "user_leo_001",
  "name": "Leo Sastra C.W.",
  "title": "Direktur Utama",
  "initials": "LS",
  "email": "leo@lumbungemas.co.id",
  "role": "director",
  "preferences": {
    "language": "id",
    "notification": {
      "daily_summary": true,
      "anomaly_alerts": true,
      "quiet_hours": {"start": "22:00", "end": "06:00"}
    }
  },
  "session": {
    "last_login_at": "2026-05-17T07:30:00+07:00",
    "device": "iPhone 15 Pro"
  }
}
```

#### `PATCH /me/preferences`

Update preferences.

**Request**:
```json
{
  "notification": {
    "daily_summary": false
  }
}
```

**Response 200**: same as `/me`

---

## Error Response Format

Semua error response konsisten:

```json
{
  "error": "error_code_snake_case",
  "message": "User-friendly message dalam Bahasa Indonesia",
  "details": {
    "field": "additional context jika ada"
  },
  "request_id": "req_abc123",
  "timestamp": "2026-05-17T09:30:00+07:00"
}
```

### Standard Error Codes

| Code | HTTP | Meaning |
|---|---|---|
| `unauthenticated` | 401 | Token invalid/expired |
| `forbidden` | 403 | Role tidak punya akses |
| `not_found` | 404 | Resource tidak ada |
| `validation_failed` | 422 | Request invalid |
| `rate_limited` | 429 | Too many requests |
| `internal_error` | 500 | Server error |
| `service_unavailable` | 503 | Maintenance/downtime |

---

## Rate Limiting

| Endpoint | Limit |
|---|---|
| `/auth/*` | 5 req/min per device |
| `/dashboard/*` | 60 req/min per user |
| `/chat/messages` | 30 req/min per user |
| Lainnya | 120 req/min per user |

Response header:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1684300800
```

---

## Caching Strategy

### Client-side

| Endpoint | Cache TTL | Strategy |
|---|---|---|
| `/dashboard/summary` | 5 menit | Stale-while-revalidate |
| `/dashboard/insight` | 5 menit | Stale-while-revalidate |
| `/me` | 1 jam | Stale-while-revalidate |
| `/chat/messages` | No cache | Always fresh |

### Cache implementation

Pakai `dio_cache_interceptor` atau custom layer. Storage: `hive_flutter`.

---

## Implementation in Flutter

### Folder Structure (recommended)

```
lib/
├── api/
│   ├── api_client.dart           # Dio instance + interceptors
│   ├── api_endpoints.dart        # Endpoint constants
│   ├── api_exception.dart        # Custom exception
│   ├── interceptors/
│   │   ├── auth_interceptor.dart
│   │   ├── logging_interceptor.dart
│   │   └── retry_interceptor.dart
│   └── repositories/
│       ├── auth_repository.dart
│       ├── dashboard_repository.dart
│       ├── chat_repository.dart
│       └── user_repository.dart
└── models/
    ├── dashboard_summary.dart
    ├── chat_message.dart
    └── ... dst (semua dengan json_serializable atau freezed)
```

### Convention

- Setiap model pakai `freezed` + `json_serializable`
- Repository return `Either<Failure, Data>` (pakai `fpdart`) atau throw custom exception
- Riverpod provider wrap repository
- Hindari Dio raw call di widget — selalu via repository
