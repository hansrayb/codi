import 'package:flutter/widgets.dart';
import 'package:google_fonts/google_fonts.dart';

/// Type scale Emas Berlian Insight.
///
/// Sumber kebenaran: `docs/03-DESIGN-SYSTEM.md`. Font via `google_fonts`:
/// Inter (UI), Fraunces (headline/number), JetBrains Mono (timestamp).
///
/// `letterSpacing` dihitung dari nilai `em` di dok dikali `fontSize`
/// (Flutter pakai logical px, bukan em).
abstract final class AppTypography {
  const AppTypography._();

  // ── Display & Headline (Fraunces) ──────────────────────────────
  /// Brand display — Fraunces 900, 44px, -0.02em.
  static TextStyle get displayXL => GoogleFonts.fraunces(
        fontSize: 44,
        fontWeight: FontWeight.w900,
        height: 1.05,
        letterSpacing: -0.88,
      );

  /// Page hero — Fraunces 800, 32px, -0.02em.
  static TextStyle get displayL => GoogleFonts.fraunces(
        fontSize: 32,
        fontWeight: FontWeight.w800,
        height: 1.1,
        letterSpacing: -0.64,
      );

  /// Section title detail — Fraunces 700, 22px.
  static TextStyle get headlineL => GoogleFonts.fraunces(
        fontSize: 22,
        fontWeight: FontWeight.w700,
        height: 1.2,
        letterSpacing: -0.22,
      );

  /// Card title, brand — Fraunces 700, 18px.
  static TextStyle get headlineM => GoogleFonts.fraunces(
        fontSize: 18,
        fontWeight: FontWeight.w700,
        height: 1.2,
        letterSpacing: -0.18,
      );

  /// Subsection title — Fraunces 700, 16px.
  static TextStyle get headlineS => GoogleFonts.fraunces(
        fontSize: 16,
        fontWeight: FontWeight.w700,
        height: 1.3,
      );

  // ── Numbers (Fraunces) ─────────────────────────────────────────
  /// Hero number (omzet) — Fraunces 700, 34px, -0.02em.
  static TextStyle get numLarge => GoogleFonts.fraunces(
        fontSize: 34,
        fontWeight: FontWeight.w700,
        height: 1.0,
        letterSpacing: -0.68,
      );

  /// KPI cell value — Fraunces 700, 22px.
  static TextStyle get numMedium => GoogleFonts.fraunces(
        fontSize: 22,
        fontWeight: FontWeight.w700,
        height: 1.0,
      );

  /// Stat mini — Fraunces 700, 18px.
  static TextStyle get numSmall => GoogleFonts.fraunces(
        fontSize: 18,
        fontWeight: FontWeight.w700,
        height: 1.0,
      );

  // ── Body (Inter) ───────────────────────────────────────────────
  /// Body default — Inter 500, 14px.
  static TextStyle get bodyL => GoogleFonts.inter(
        fontSize: 14,
        fontWeight: FontWeight.w500,
        height: 1.5,
      );

  /// Body small, chat msg — Inter 400, 13px.
  static TextStyle get bodyM => GoogleFonts.inter(
        fontSize: 13,
        fontWeight: FontWeight.w400,
        height: 1.55,
      );

  /// Caption, sub-text — Inter 400, 12px.
  static TextStyle get bodyS => GoogleFonts.inter(
        fontSize: 12,
        fontWeight: FontWeight.w400,
        height: 1.5,
      );

  // ── Labels (Inter) ─────────────────────────────────────────────
  /// Button, badge — Inter 600, 11px.
  static TextStyle get labelM => GoogleFonts.inter(
        fontSize: 11,
        fontWeight: FontWeight.w600,
        height: 1.3,
      );

  /// Label uppercase — Inter 600, 10px, +0.15em.
  static TextStyle get labelS => GoogleFonts.inter(
        fontSize: 10,
        fontWeight: FontWeight.w600,
        height: 1.3,
        letterSpacing: 1.5,
      );

  // ── Mono (JetBrains Mono) ──────────────────────────────────────
  /// Timestamp — JetBrains Mono 400, 10px.
  static TextStyle get mono => GoogleFonts.jetBrainsMono(
        fontSize: 10,
        fontWeight: FontWeight.w400,
        height: 1.3,
      );
}
