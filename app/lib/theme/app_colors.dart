import 'package:flutter/material.dart';

/// Color token Emas Berlian Insight.
///
/// Sumber kebenaran: `docs/03-DESIGN-SYSTEM.md`. Jangan pakai warna di luar
/// token ini — tidak ada magic color di widget.
abstract final class AppColors {
  // ── Background (Navy) ──────────────────────────────────────────
  /// Outermost background, splash, body.
  static const bgPage = Color(0xFF060A14);

  /// App-level background, scaffold.
  static const bgApp = Color(0xFF0A1124);

  /// Card surface, default.
  static const bgCard = Color(0xFF111A31);

  /// Elevated card, dialog, modal.
  static const bgElev = Color(0xFF18233F);

  /// Input field background.
  static const bgInput = Color(0xFF0F1830);

  /// Hover/pressed state.
  static const bgHighlight = Color(0xFF1A2547);

  // ── Ink (Text) ─────────────────────────────────────────────────
  /// Primary text, headlines.
  static const ink = Color(0xFFF4F6FB);

  /// Body text, descriptions.
  static const inkDim = Color(0xFFA8B0C4);

  /// Secondary text, labels.
  static const inkMuted = Color(0xFF6B7390);

  /// Tertiary text, timestamps.
  static const inkFaint = Color(0xFF404863);

  // ── Gold Accent (Brand) ────────────────────────────────────────
  /// Primary brand color, important numbers, CTAs.
  static const gold = Color(0xFFC9A857);

  /// Hover state, gradient end.
  static const goldBright = Color(0xFFE6C47A);

  /// Pressed state, gradient start.
  static const goldDim = Color(0xFF8E7634);

  /// Subtle background tint — `rgba(201,168,87,0.12)`.
  static const goldSoft = Color(0x1FC9A857);

  /// Border for highlighted elements — `rgba(201,168,87,0.30)`.
  static const goldLine = Color(0x4DC9A857);

  // ── Diamond (Secondary Accent) ─────────────────────────────────
  /// Logo facet, special highlights — pakai SANGAT jarang.
  static const diamond = Color(0xFFE8EDF5);

  /// Very subtle accent — `rgba(232,237,245,0.10)`.
  static const diamondSoft = Color(0x1AE8EDF5);

  // ── Navy Blue (Secondary) ──────────────────────────────────────
  /// Data viz secondary, chat user bubble.
  static const navyBlue = Color(0xFF4A7BC8);

  /// Tint background — `rgba(74,123,200,0.15)`.
  static const navySoft = Color(0x264A7BC8);

  // ── Semantic ───────────────────────────────────────────────────
  /// Success, positive trend, healthy status.
  static const green = Color(0xFF5EC99A);

  /// Background tint — `rgba(94,201,154,0.12)`.
  static const greenSoft = Color(0x1F5EC99A);

  /// Error, negative trend, alert.
  static const red = Color(0xFFE07A7A);

  /// Background tint — `rgba(224,122,122,0.12)`.
  static const redSoft = Color(0x1FE07A7A);

  /// Warning, requires attention.
  static const amber = Color(0xFFD4A544);

  /// Background tint — `rgba(212,165,68,0.12)`.
  static const amberSoft = Color(0x1FD4A544);

  // ── Lines & Dividers ───────────────────────────────────────────
  /// Subtle divider — `rgba(255,255,255,0.05)`.
  static const line = Color(0x0DFFFFFF);

  /// Active border, input border — `rgba(255,255,255,0.09)`.
  static const lineStrong = Color(0x17FFFFFF);
}
