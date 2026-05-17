# 06 — SCREENS.md

Spesifikasi detail untuk 4 screen utama di Emas Berlian Insight.

---

## Screen Inventory

| ID | Screen | Route | Status |
|---|---|---|---|
| S1 | Login | `/login` | MVP |
| S2 | Dashboard | `/` | MVP |
| S3 | Chat dengan Codi | `/chat` | MVP |
| S4 | Insight | `/insight` | MVP |
| S5 | Reports | `/reports` | Phase 2 |
| S6 | Profile | `/profile` | Phase 2 |

---

## S1 — Login Screen

### Purpose
Otentikasi Bapak Leo menggunakan biometric (Face ID / Fingerprint). Tanpa username/password.

### Route
`/login` — accessible saat tidak ada valid token.

### Layout (top to bottom)

```
┌─────────────────────────────┐
│  [Status bar]               │
├─────────────────────────────┤
│                             │
│   [empty space ~50px]       │
│                             │
│   ╔═══════════════╗         │
│   ║   LOGO 96px   ║         │
│   ╚═══════════════╝         │
│                             │
│   Emas Berlian Insight      │  ← brand
│   Executive Business        │  ← tagline
│   Intelligence              │
│                             │
│   [flexible space]          │
│                             │
│   ╔═══════════╗             │
│   ║ FINGERPRINT║            │  ← biometric button
│   ║   ICON    ║             │
│   ╚═══════════╝             │
│                             │
│   Sentuh untuk masuk        │
│   Otentikasi biometrik      │
│   diperlukan                │
│                             │
│   ─────────────────         │
│   Akses Khusus Direksi      │  ← footer
│   v1.0.0 · 2026.05          │
│                             │
└─────────────────────────────┘
```

### Components

| Element | Token | Detail |
|---|---|---|
| Background | bgApp + radial gradient navy + gold | Atmospheric |
| Logo container | 96x96, radius28, bgElev gradient, gold border | Center top |
| Logo SVG | 52x52, custom (diamond + gold bar) | Inside container |
| Brand name | headlineM Fraunces 700 | "Emas Berlian *Insight*" — italic on "Insight" |
| Tagline | bodyS Inter | inkMuted |
| Biometric button | 88x88 circle, navy gradient + navy border | Pulse ring animation |
| Biometric icon | iconL fingerprint or face | navyBlue stroke |
| Label | bodyM | "Sentuh untuk masuk" |
| Hint | bodyS | inkMuted, "Otentikasi biometrik diperlukan" |
| Footer | labelS uppercase | inkFaint, centered |

### Interactions

1. **On screen load**:
   - Check biometric availability via `local_auth`
   - If unavailable → show error "Aktifkan Face ID/Fingerprint di settings device"
   - If available → render normal

2. **Tap biometric button**:
   - Trigger `LocalAuthentication.authenticate()`
   - Show iOS/Android native biometric prompt
   - On success → call `POST /auth/login` with device fingerprint
   - On API success → store token in secure storage → navigate `/`
   - On API fail → show error message + retry button

3. **Auto-trigger biometric on first load**:
   - Untuk smoother UX, auto-prompt biometric saat screen muncul (jika allowed by spec)
   - Bisa di-toggle di settings (Phase 2)

### State

```dart
enum LoginStatus {
  initial,          // screen loaded
  checking,         // checking biometric availability
  unavailable,      // biometric not available on device
  authenticating,   // biometric prompt active
  loggingIn,        // calling /auth/login
  success,          // navigating to dashboard
  failed,           // show error
  locked,           // too many attempts
}
```

### Error States

| Error | UX |
|---|---|
| Biometric cancelled | Stay on screen, no error message |
| Biometric failed (multiple times) | Lock screen 5 min, show countdown |
| API 401 (device not enrolled) | "Device belum terdaftar. Hubungi admin." |
| Network error | "Tidak ada koneksi internet. Cek WiFi/data Anda." |
| API 5xx | "Layanan sedang tidak tersedia. Coba lagi nanti." |

---

## S2 — Dashboard Screen

### Purpose
Halaman utama setelah login. Memberikan ringkasan kondisi operasional dalam < 5 detik scan.

### Route
`/` — default route after login.

### Layout (top to bottom)

```
┌─────────────────────────────┐
│  [Status bar]               │
├─────────────────────────────┤
│ Selamat pagi,         [LS]  │  ← greeting + avatar
│ Bapak Leo Sastra C.W.       │
│ DIREKTUR UTAMA              │
├─────────────────────────────┤
│ [Hari][Minggu][BulanIni][Tahun] │  ← period selector
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ ● OMZET MEI 2026 · LIVE │ │
│ │                         │ │
│ │ Rp 828,8 jt             │ │  ← hero summary
│ │                         │ │
│ │ ▲ +321% MoM · 17 hari   │ │
│ │                         │ │
│ │ [sparkline chart]       │ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ ┌──────┐┌──────┐┌──────┐    │
│ │Order ││Conv. ││Beban │    │  ← 3 stat mini
│ │ 55tx ││68,8% ││10,8jt│    │
│ │▲15   ││▼31,2 ││1,3%  │    │
│ └──────┘└──────┘└──────┘    │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ ◆ Ringkasan Hari Ini   │ │
│ │ Diperbarui 14 menit lalu│ │  ← AI Summary
│ │                         │ │
│ │ Operasional kantor      │ │
│ │ berada dalam kondisi... │ │
│ │                         │ │
│ │ 12 data point  Tap → │ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ Tren Omzet 7 Hari       │ │
│ │ [bar chart retail+rotasi]│ │  ← chart card
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ Sorotan          Lihat semua │
│ ┌─────────────────────────┐ │
│ │ ▲ Penjualan emas...    │ │  ← highlights
│ │ │ ⚠ 24 order expired...  │ │
│ │ │ ◊ Payroll Mei...       │ │
│ └─────────────────────────┘ │
│                             │
│ [bottom nav + FAB]          │
└─────────────────────────────┘
```

### Data Source
`GET /dashboard/summary?period={period}`

### Components Detail

#### Greeting

```dart
Column(
  crossAxisAlignment: CrossAxisAlignment.start,
  children: [
    Text(_greetingByTime(), style: AppTypography.bodyS),    // dynamic
    Text('Bapak ${user.name}', style: AppTypography.headlineM),
    Text(user.title.toUpperCase(), style: AppTypography.labelS),
  ],
)
```

Greeting logic:
- 04:00–10:59 → "Selamat pagi,"
- 11:00–14:59 → "Selamat siang,"
- 15:00–17:59 → "Selamat sore,"
- 18:00–03:59 → "Selamat malam,"

#### Period Selector

`Hari` / `Minggu` / `Bulan Ini` / `Tahun`

Default: `Bulan Ini`. State managed via Riverpod `selectedPeriodProvider`.

On change → trigger refresh dashboard.

#### Hero Summary Card

- Background: linear-gradient bgCard → bgElev
- Border: 1px goldLine
- Decorative: 2 radial gradients (gold corner + navy bottom)
- Title: "OMZET {PERIOD_LABEL} · LIVE" dengan live dot blink
- Big number: Fraunces 34px bold, format "Rp 828,8jt" (auto-format kalau besar)
- Trend row: ▲/▼ icon + "+321% MoM" (green/red)
- Period info: "17 hari · 55 order · proyeksi Rp 1,51 M"
- Sparkline: 50px height, gold line + gradient fill, end dot

#### Stats Row

3 cell sama lebar dengan format:
```
[LABEL]
[NUMBER] [unit]
[delta arrow] [delta text]
```

Delta color:
- Up + revenue/orders = green ✓
- Up + cost = red ✗ (kebalikan)
- Down + revenue = red
- Down + cost = green
- Flat = inkMuted

#### AI Summary Card

- Border: 1px goldLine
- Header: icon (chat bubble in gold gradient box) + title + sub
- Body: 3 paragraf dengan inline highlight (.pos / .neg / .gold span)
- Footer: meta info + "Tap untuk detail →" link

#### Chart Card (7 Hari)

- Card default style
- Title + subtitle + legend (2 color swatch)
- Bar chart via `fl_chart`:
  - Group bars by day (retail + rotasi side by side)
  - Width: container width / 7 / 2
  - Color: gold + navy
  - Animate on load 600ms

#### Highlights

Card dengan left-border colored:
- green = positive news
- red = critical/attention
- gold = info/positive financial
- navy = neutral info

Each item:
- Icon wrap 32x32 colored bg + colored icon
- Title bodyM bold
- Description bodyS muted
- Timestamp mono labelS faint

Max 3-5 items, "Lihat semua →" navigate ke `/highlights` (Phase 2).

### State

```dart
sealed class DashboardState {
  const factory DashboardState.loading() = _Loading;
  const factory DashboardState.success(DashboardSummary data) = _Success;
  const factory DashboardState.error(String message) = _Error;
  const factory DashboardState.offline(DashboardSummary cached) = _Offline;
}
```

### Interactions

- Pull to refresh → trigger reload
- Tap period chip → change period + reload
- Tap AI summary card → navigate `/insight`
- Tap chart → navigate `/insight` (or detail chart)
- Tap highlight item → expand or navigate to detail
- Tap FAB → navigate `/chat`
- Long press dashboard → show "diperbarui X menit lalu" timestamp prominently

### Refresh Strategy

- On screen mount → load
- Auto-refresh if stale > 5 min when app foreground
- Manual pull-to-refresh
- Show shimmer skeleton during loading, not spinner

---

## S3 — Chat Screen

### Purpose
Conversational interface untuk tanya ad-hoc ke Codi. Codi yang akses database & jawab dengan analisis.

### Route
`/chat`

### Layout

```
┌─────────────────────────────┐
│ [<]  [◊] Codi          [⋯]  │  ← header
│         Aktif · respon 0,8s │
├─────────────────────────────┤
│                             │
│         Hari ini · 09:42    │
│                             │
│       ┌─────────────────┐   │
│       │ User message    │   │  ← right aligned, navy
│       │            09:42│   │
│       └─────────────────┘   │
│                             │
│ ┌──────────────────┐        │
│ │ Bot message      │        │  ← left aligned, bgCard
│ │ ┌──────────────┐ │        │
│ │ │ Rich card    │ │        │
│ │ │ [table rows] │ │        │
│ │ │ [chart]      │ │        │
│ │ │ [buttons]    │ │        │
│ │ └──────────────┘ │        │
│ │           09:42·0,8s│     │
│ └──────────────────┘        │
│                             │
├─────────────────────────────┤
│ [chip][chip][chip] →        │  ← suggestion chips
├─────────────────────────────┤
│ ╔═══════════════════════╗   │
│ ║ Tanyakan... [🎤][📤] ║   │  ← input
│ ╚═══════════════════════╝   │
└─────────────────────────────┘
```

### Data Source

- `POST /chat/messages` — send message
- `GET /chat/conversations/{id}/messages` — load history
- Stream via SSE for token-by-token response

### Components Detail

#### Header

- Back button (top-left)
- Codi avatar (32x32, gold border, mini logo SVG)
- Title "Codi" + status "Aktif · respon X,Xs"
- Options menu (3-dot)

Avatar mini SVG:
```svg
<g transform="translate(12 5)">
  <path d="M0 0 L3 3 L0 7 L-3 3 Z" stroke="#e8edf5" />
</g>
<g transform="translate(12 16)">
  <path d="M-5 -1 L5 -1 L4 3 L-4 3 Z" stroke="#c9a857" />
</g>
```

#### Messages

##### User Message
- Align right
- Background: linear-gradient navy
- Border: 1px goldLine
- Radius: 18px (bottom-right 4px)
- Text: bodyM, color ink
- Time: bottom right, mono, rgba(ink 0.5)
- Max width: 86%

##### Bot Message
- Align left
- Background: bgCard
- Border: 1px line
- Radius: 18px (bottom-left 4px)
- Text: bodyM, color ink
- Time: bottom left, mono, faint
- Optional rich card inside

#### Rich Card (Inline)

```dart
class RichCard {
  String? title;
  Badge? badge;          // {label, color}
  List<RichRow> rows;    // {label, value, trend}
  InlineChart? chart;    // {type: sparkline|bar, data}
  List<RichAction> actions; // {label, deepLink, action}
}
```

Render:
- Header: title (labelM uppercase muted) + badge (pill green/red/gold)
- Rows: dashed divider, label left + value right (trend colored)
- Optional chart inline
- Action buttons row (gold primary + secondary outline)

#### Suggestion Chips

- Horizontal scroll, no scrollbar
- Pill style
- bgCard with line border
- bodyS inkDim
- Tap → fill chat input

3-4 chips, generated based on context (server-driven via `suggestions` field).

#### Chat Input

```
┌────────────────────────────────┐
│  Tanyakan kondisi kantor...    │
│                       [🎤][📤] │
└────────────────────────────────┘
```

- Background: bgInput, radius pill
- Border: 1px lineStrong
- Input: bodyM, padding 8px vertical
- Mic button: ghost (inactive Phase 1)
- Send button: gold gradient circle 36x36

#### Day Marker

Center divider: "Hari ini · 09:42" or "Kemarin" or "17 Mei 2026"

### State

```dart
class ChatState {
  String conversationId;
  List<ChatMessage> messages;
  bool isLoading;          // sending
  bool isStreaming;        // receiving
  String? error;
  List<String> suggestions;
}
```

### Interactions

- Tap suggestion chip → set as input text
- Tap send → send message → stream response
- Tap rich card action → navigate or trigger action
- Long press message → copy/share (Phase 2)
- Pull down → load older messages

### Streaming Implementation

```dart
// Application layer
final stream = repo.sendMessage(message, conversationId);
stream.listen((event) {
  switch (event.type) {
    case 'token':
      // append to current message
      state = state.copyWith(
        messages: [...state.messages.dropLast(), state.messages.last.appendText(event.text)],
      );
    case 'card':
      // attach card
    case 'done':
      state = state.copyWith(isStreaming: false);
  }
});
```

---

## S4 — Insight Screen

### Purpose
Analisis mendalam dengan KPI, donut chart, dan AI analysis 3-section.

### Route
`/insight?period={period}`

### Layout

```
┌─────────────────────────────┐
│  [<]                  [⬇]   │  ← back + share
├─────────────────────────────┤
│ Insight Operasional         │  ← hero
│ Periode: 1 – 17 Mei 2026    │
│ · Live                      │
├─────────────────────────────┤
│ ┌───────────┐┌───────────┐  │
│ │Omzet Total││Order      │  │
│ │Rp 828,8jt ││55 tx      │  │  ← KPI grid 2x2
│ │▲ +321%    ││▲ 15+40    │  │
│ └───────────┘└───────────┘  │
│ ┌───────────┐┌───────────┐  │
│ │Avg Ticket ││Potensi    │  │
│ │Rp 15,1jt  ││Hilang     │  │
│ │▲ +21,8%   ││Rp 127jt   │  │
│ └───────────┘└───────────┘  │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ [donut]  Komposisi      │ │
│ │  828,8jt  ◆ Penjualan   │ │
│ │  Total    79,2%         │ │
│ │           ◆ Rotasi 20,8%│ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ ◆ Analisis Mendalam    │ │
│ │ Disusun Codi 14 menit   │ │
│ │                         │ │
│ │ Yang Sehat              │ │
│ │ Omzet Mei naik tajam... │ │
│ │                         │ │
│ │ Yang Perlu Perhatian    │ │
│ │ Conversion rate...      │ │
│ │                         │ │
│ │ Catatan                 │ │
│ │ Data sistem baru...     │ │
│ │                         │ │
│ │ 12 data point  Tanya → │ │
│ └─────────────────────────┘ │
└─────────────────────────────┘
```

### Data Source

`GET /dashboard/insight?period={period}`

### Components

#### Hero

- Background: linear-gradient (navy subtle) → transparent
- Back button + share/export button
- Title: headlineL Fraunces
- Sub: bodyS muted with "Live" green badge

#### KPI Grid

2x2 grid, gap 8px:

Each cell:
- Background: bgCard
- Border: 1px line, radius14
- Padding: 14px
- Label: labelS muted
- Value: numMedium Fraunces (auto-format Rp/tx/etc)
- Unit: ku small muted
- Delta: bodyS with arrow icon + delta text

#### Donut Card

- Card default, padding 18px
- Horizontal layout: donut (100x100) + legend
- Donut center: total number + "Total" label
- Legend: section title + 2 rows (color swatch + label + percentage)

#### AI Analysis

- Card elevated (goldLine border)
- Header: gold icon + title + sub (Codi attribution)
- 3 sections:
  - "Yang Sehat" — positive findings
  - "Yang Perlu Perhatian" — attention needed
  - "Catatan" — notes & caveats
- Each section: subtitle bold + body paragraph
- Inline highlights: `.pos` green, `.neg` red, `.gold` brand

### State & Interactions

Same pattern as Dashboard — sync period selector via shared provider.

- Tap "Tanya Codi →" → navigate `/chat?context=insight&period={current}`
- Tap share icon → generate PDF (Phase 2) or copy to clipboard
- Pull to refresh

---

## Shell Layout (Bottom Nav)

### Purpose
Persistent bottom navigation across screens (Dashboard, Insight, Chat, Reports, Profile).

### Behavior

- FAB Codi at center, always visible
- Active tab: gold color
- Inactive: inkFaint
- Tap FAB → navigate `/chat` (replace if already in shell)
- Animate transitions 200ms easeInOut

### Layout

```
┌─────┬─────┬─────┬─────┬─────┐
│  🏠  │  📈  │ [◊] │  📄  │  👤  │
│Berand│Insig │FAB  │Lapor │Profi │
└─────┴─────┴─────┴─────┴─────┘
```

---

## Loading States

Semua screen wajib pakai shimmer skeleton matching layout final, bukan generic spinner:

```dart
// Example: Dashboard summary card loading
EmasShimmer(
  child: Container(
    height: 140,
    decoration: BoxDecoration(
      color: AppColors.bgCard,
      borderRadius: BorderRadius.circular(AppRadius.r20),
    ),
  ),
)
```

Pakai package `shimmer: ^3.0.0`.

---

## Empty States

| Screen | Empty Condition | UX |
|---|---|---|
| Dashboard | Belum ada data periode | "Belum ada data untuk {period}. Coba periode lain." |
| Chat | Conversation kosong | Welcome message dari Codi + 4 suggestion |
| Insight | Data minimal | "Data belum cukup untuk analisis. Tunggu beberapa hari." |
| Reports | Belum ada laporan | "Belum ada laporan. Tap [+] untuk generate." (Phase 2) |

---

## Error States

Konsisten across screens:

```
┌─────────────────────────────┐
│         [⚠ icon]            │
│                             │
│   Tidak dapat memuat data   │
│   {error message}           │
│                             │
│   ╔══════════════╗          │
│   ║ Coba lagi    ║          │
│   ╚══════════════╝          │
└─────────────────────────────┘
```

Component: `EmasErrorView(message, onRetry)` reusable.
