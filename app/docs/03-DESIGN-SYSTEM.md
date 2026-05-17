# 03 — DESIGN-SYSTEM.md

Single source of truth untuk semua design decision di Emas Berlian Insight.

> **Aturan**: Setiap warna, font size, atau spacing yang digunakan di code **harus** dari token di dokumen ini. Tidak ada magic number.

---

## Brand Identity

- **Nama produk**: Emas Berlian Insight
- **Tagline**: Executive Business Intelligence
- **Persona AI**: Codi (asisten percakapan)
- **Vibe**: Eksekutif, premium, formal, terpercaya, ringkas
- **Bukan**: Playful, tech-y, casual, flashy

---

## Color Palette

### Background (Navy)

| Token | Hex | Usage |
|---|---|---|
| `bgPage` | `#060A14` | Outermost background, splash, body |
| `bgApp` | `#0A1124` | App-level background, scaffold |
| `bgCard` | `#111A31` | Card surface, default |
| `bgElev` | `#18233F` | Elevated card, dialog, modal |
| `bgInput` | `#0F1830` | Input field background |
| `bgHighlight` | `#1A2547` | Hover/pressed state |

### Ink (Text)

| Token | Hex | Usage |
|---|---|---|
| `ink` | `#F4F6FB` | Primary text, headlines |
| `inkDim` | `#A8B0C4` | Body text, descriptions |
| `inkMuted` | `#6B7390` | Secondary text, labels |
| `inkFaint` | `#404863` | Tertiary text, timestamps |

### Gold Accent (Brand)

| Token | Hex | Usage |
|---|---|---|
| `gold` | `#C9A857` | Primary brand color, important numbers, CTAs |
| `goldBright` | `#E6C47A` | Hover state, gradient end |
| `goldDim` | `#8E7634` | Pressed state, gradient start |
| `goldSoft` | `rgba(201,168,87,0.12)` | Subtle background tint |
| `goldLine` | `rgba(201,168,87,0.30)` | Border for highlighted elements |

### Diamond (Secondary Accent)

| Token | Hex | Usage |
|---|---|---|
| `diamond` | `#E8EDF5` | Logo facet, special highlights (RARELY) |
| `diamondSoft` | `rgba(232,237,245,0.10)` | Very subtle accent |

> ⚠️ Diamond dipakai HANYA di logo & moments kecil. Jangan digunakan untuk UI utama.

### Navy Blue (Secondary)

| Token | Hex | Usage |
|---|---|---|
| `navyBlue` | `#4A7BC8` | Data viz secondary, chat user bubble |
| `navySoft` | `rgba(74,123,200,0.15)` | Tint background |

### Semantic Colors

| Token | Hex | Usage |
|---|---|---|
| `green` | `#5EC99A` | Success, positive trend, healthy status |
| `greenSoft` | `rgba(94,201,154,0.12)` | Background tint |
| `red` | `#E07A7A` | Error, negative trend, alert |
| `redSoft` | `rgba(224,122,122,0.12)` | Background tint |
| `amber` | `#D4A544` | Warning, requires attention |
| `amberSoft` | `rgba(212,165,68,0.12)` | Background tint |

### Lines & Dividers

| Token | Hex | Usage |
|---|---|---|
| `line` | `rgba(255,255,255,0.05)` | Subtle divider |
| `lineStrong` | `rgba(255,255,255,0.09)` | Active border, input border |

---

## Typography

### Font Families

| Font | Source | Usage |
|---|---|---|
| **Inter** | Google Fonts | UI text default (body, labels, buttons) |
| **Fraunces** | Google Fonts | Headlines, numbers, brand moments |
| **JetBrains Mono** | Google Fonts | Timestamps, technical data, code |

Setup via `google_fonts` package atau bundle ke `assets/fonts/`.

### Type Scale

| Token | Family | Weight | Size | Line Height | Usage |
|---|---|---|---|---|---|
| `displayXL` | Fraunces | 900 | 44px | 1.05 | Brand display |
| `displayL` | Fraunces | 800 | 32px | 1.1 | Page hero |
| `headlineL` | Fraunces | 700 | 22px | 1.2 | Section title detail |
| `headlineM` | Fraunces | 700 | 18px | 1.2 | Card title, brand |
| `headlineS` | Fraunces | 700 | 16px | 1.3 | Subsection title |
| `numLarge` | Fraunces | 700 | 34px | 1.0 | Hero number (omzet) |
| `numMedium` | Fraunces | 700 | 22px | 1.0 | KPI cell value |
| `numSmall` | Fraunces | 700 | 18px | 1.0 | Stat mini |
| `bodyL` | Inter | 500 | 14px | 1.5 | Body default |
| `bodyM` | Inter | 400 | 13px | 1.55 | Body small, chat msg |
| `bodyS` | Inter | 400 | 12px | 1.5 | Caption, sub-text |
| `labelM` | Inter | 600 | 11px | 1.3 | Button, badge |
| `labelS` | Inter | 600 | 10px | 1.3 | Label uppercase |
| `mono` | JetBrains Mono | 400 | 10px | 1.3 | Timestamp |

### Letter Spacing

- Display & Headline: `-0.01em` to `-0.02em` (tighter)
- Body: `0` (normal)
- Labels (UPPERCASE): `0.1em` to `0.15em` (wider)
- Eyebrow text: `0.3em` (very wide)

---

## Spacing Scale

Pakai sistem 4px base:

| Token | Value | Usage |
|---|---|---|
| `s2` | 2px | Hairline gap |
| `s4` | 4px | Tight gap |
| `s6` | 6px | Small gap inline |
| `s8` | 8px | Default gap small |
| `s12` | 12px | Default gap |
| `s14` | 14px | Card padding |
| `s16` | 16px | Section padding |
| `s20` | 20px | Screen padding horizontal |
| `s24` | 24px | Large gap |
| `s32` | 32px | Section separator |
| `s40` | 40px | Hero spacing |
| `s48` | 48px | Page separator |

---

## Border Radius

| Token | Value | Usage |
|---|---|---|
| `radius4` | 4px | Tag, small badge |
| `radius8` | 8px | Inline element |
| `radius10` | 10px | Chip, suggestion |
| `radius12` | 12px | Default button, period selector |
| `radius14` | 14px | Card item |
| `radius16` | 16px | Chart card |
| `radius18` | 18px | Chat message |
| `radius20` | 20px | Hero summary card |
| `radius28` | 28px | Logo container |
| `radiusPill` | 999px | Pill button, chip |

---

## Elevation (Shadow)

| Token | Value | Usage |
|---|---|---|
| `elev0` | none | Flat |
| `elev1` | `0 4px 12px rgba(0,0,0,0.3)` | Card subtle |
| `elev2` | `0 10px 24px -4px rgba(201,168,87,0.4)` | FAB Codi |
| `elev3` | `0 20px 50px rgba(74,123,200,0.2)` | Logo, hero card |

---

## Component Library

### Buttons

#### Primary Button (Gold)

```
- Background: linear-gradient(135deg, goldBright, gold)
- Text color: bgApp (dark on gold)
- Padding: 14px horizontal, 12px vertical (large)
- Radius: radius14
- Font: labelM, weight 700
- Shadow: elev2
- Pressed: scale 0.97, opacity 0.9
```

#### Secondary Button (Outline)

```
- Background: transparent
- Border: 1px solid lineStrong
- Text color: ink
- Same padding & radius as primary
- Pressed: bg bgHighlight
```

#### Ghost Button (Text only)

```
- Background: transparent
- Text color: gold
- No border
- Padding: 8px horizontal, 6px vertical
- Font: labelM
```

### Cards

#### Default Card

```
- Background: bgCard
- Border: 1px solid line
- Radius: radius14
- Padding: s14
```

#### Elevated Card (Hero, AI Summary)

```
- Background: linear-gradient(135deg, bgCard, bgElev)
- Border: 1px solid goldLine
- Radius: radius20
- Padding: s20-s22
- Optional: decorative radial gradient
```

#### Highlight Card (Alert)

```
- Background: bgCard
- Border: 1px solid line + 3px left border (semantic color)
- Radius: radius14
- Padding: s14
- Icon wrap: 32x32 rounded, colored bg
```

### Input

#### Text Input

```
- Background: bgInput
- Border: 1px solid lineStrong
- Radius: radiusPill (for chat) or radius12 (for form)
- Padding: 8px vertical, 16px horizontal
- Text: bodyM, color ink
- Placeholder: bodyM, color inkFaint
- Focus: border-color gold
```

### Avatar

```
- Size: 38-42px
- Border-radius: 50%
- Background: linear-gradient(135deg, navyBlue, #2a4a7f)
- Border: 1px solid goldLine
- Text: labelM, weight 700, color ink
- Initials: max 2 char
```

### Bottom Navigation

```
- Height: 80px (incl safe area)
- Background: rgba(10,17,36,0.92) + backdrop-blur(20px)
- Border-top: 1px solid line
- Item: icon + label, 4px gap
- Active color: gold
- Inactive color: inkFaint
- FAB center: 56x56 circle, gold gradient, elev2
- FAB position: translateY(-12px) — overflow
```

### Chart Style

#### Bar Chart

```
- Bar color primary: gold (#C9A857)
- Bar color secondary: navyBlue (#4A7BC8)
- Bar radius: 2px top
- Grid line: rgba(255,255,255,0.04), dashed
- Label: labelS, color inkMuted
- Animate on load: 600ms ease-out
```

#### Donut Chart

```
- Stroke width: 12px
- Track: rgba(255,255,255,0.05)
- Segment 1: gold, rounded line cap
- Segment 2: navyBlue, rounded line cap
- Center: number (numMedium) + label (labelS)
- Animate: rotate from 0 to final, 800ms ease-in-out
```

#### Sparkline

```
- Line color: gold
- Line width: 1.8px
- Fill: linear-gradient gold 0.4 → 0 (top to bottom)
- End point: circle radius 3.5px gold + outer halo
```

---

## Iconography

### Source

- **Primary**: Heroicons (outline, 24x24, stroke-width 2)
- **Fallback**: Phosphor Icons untuk yang tidak ada di Heroicons
- **Style**: Outline, stroke-linejoin: round, stroke-linecap: round
- **No fill icons** kecuali untuk status indicator (dot, badge)

### Custom Icons

Logo & Codi mascot adalah custom SVG, simpan di `assets/svg/`.

### Sizes

| Token | Value | Usage |
|---|---|---|
| `iconXS` | 12px | Inline with text |
| `iconS` | 14px | Status indicators |
| `iconM` | 18px | Default UI icons |
| `iconL` | 24px | Section icons |
| `iconXL` | 40px | Featured icons |

---

## Animation & Motion

### Duration

- Micro: 150ms (button press, focus state)
- Standard: 250ms (transitions)
- Emphasis: 400ms (page transitions, modal)
- Hero: 600-800ms (chart load, splash)

### Easing

- Default: `Curves.easeOutCubic`
- Spring: `Curves.elasticOut` (rarely, for delight moments)
- Sharp: `Curves.easeOutQuart` (modal dismiss)

### Common Patterns

| Pattern | Duration | Easing |
|---|---|---|
| Button press | 150ms | easeOutCubic |
| Card tap → screen | 300ms | easeOutCubic |
| Modal open | 400ms | easeOutQuart |
| Tab switch | 200ms | easeInOut |
| Pull-to-refresh | 800ms | easeOutCubic |
| Chart appearance | 600-800ms | easeOutCubic |
| Live dot blink | 2s infinite | linear |
| Pulse ring | 2.4s infinite | linear |

---

## Dark Mode

App ini **dark-only**. Tidak ada light mode untuk Phase 1.

Alasan:
- Premium executive feel
- OLED-friendly (hemat baterai)
- Konsisten brand identity
- User feedback positif dari Telegram bot dark theme

Light mode bisa dipertimbangkan di Phase 2 jika user request.

---

## Implementation in Flutter

### Theme Setup

Buat file `lib/theme/app_theme.dart`:

```dart
class AppColors {
  static const bgPage = Color(0xFF060A14);
  static const bgApp = Color(0xFF0A1124);
  static const bgCard = Color(0xFF111A31);
  // ... dst sesuai token
}

class AppSpacing {
  static const s4 = 4.0;
  static const s8 = 8.0;
  // ... dst
}

class AppRadius {
  static const r14 = 14.0;
  static const r20 = 20.0;
  // ... dst
}

class AppTypography {
  static TextStyle get numLarge => GoogleFonts.fraunces(
    fontSize: 34,
    fontWeight: FontWeight.w700,
    height: 1.0,
    letterSpacing: -0.68, // -0.02em of 34
  );
  // ... dst
}
```

Sediakan `AppTheme.darkTheme` yang inject semua di atas ke `ThemeData`.

### Penggunaan di Widget

✅ **Benar**:
```dart
Container(
  padding: EdgeInsets.all(AppSpacing.s14),
  decoration: BoxDecoration(
    color: AppColors.bgCard,
    borderRadius: BorderRadius.circular(AppRadius.r14),
  ),
  child: Text('Hello', style: AppTypography.bodyM),
)
```

❌ **Salah**:
```dart
Container(
  padding: EdgeInsets.all(14),
  decoration: BoxDecoration(
    color: Color(0xFF111A31),
    borderRadius: BorderRadius.circular(14),
  ),
  child: Text('Hello', style: TextStyle(fontSize: 13)),
)
```

### Reusable Widgets

Buat di `lib/widgets/`:

- `EmasCard` — default card
- `EmasElevatedCard` — hero/AI summary card
- `EmasButton` — primary/secondary/ghost variants
- `EmasInput` — text input dengan style konsisten
- `EmasAvatar` — avatar dengan initial
- `EmasBottomNav` — bottom navigation
- `EmasFab` — Codi FAB
- `EmasAlert` — highlight card dengan severity
- `EmasKpiCell` — KPI grid cell
- `EmasSparkline` — sparkline chart
- `EmasDonut` — donut chart
- `EmasBarChart` — bar chart

Setiap widget custom **harus** memiliki:
- Dartdoc comment
- Widget test minimum
- Storybook entry (jika pakai widgetbook/dashbook)
