import 'package:flutter/widgets.dart';

/// Palet warna theme-aware Emas Berlian Insight.
///
/// Brand color: biru-cyan (gradient dari logo aplikasi). Mendukung
/// **dark** & **light** mode. Token diakses via `context.colors`
/// (lihat `app_palette.dart`), bukan statik — agar resolve per theme.
///
/// Catatan: nama token `gold*` dipertahankan untuk kompatibilitas
/// kode lama; nilainya kini biru (brand color baru).
@immutable
class AppColors {
  const AppColors({
    required this.bgPage,
    required this.bgApp,
    required this.bgCard,
    required this.bgElev,
    required this.bgInput,
    required this.bgHighlight,
    required this.ink,
    required this.inkDim,
    required this.inkMuted,
    required this.inkFaint,
    required this.gold,
    required this.goldBright,
    required this.goldDim,
    required this.goldSoft,
    required this.goldLine,
    required this.diamond,
    required this.diamondSoft,
    required this.navyBlue,
    required this.navySoft,
    required this.purpleAccent,
    required this.green,
    required this.greenSoft,
    required this.red,
    required this.redSoft,
    required this.amber,
    required this.amberSoft,
    required this.line,
    required this.lineStrong,
  });

  // Background
  final Color bgPage;
  final Color bgApp;
  final Color bgCard;
  final Color bgElev;
  final Color bgInput;
  final Color bgHighlight;

  // Ink (text)
  final Color ink;
  final Color inkDim;
  final Color inkMuted;
  final Color inkFaint;

  // Brand accent (biru — nama `gold*` legacy)
  final Color gold;
  final Color goldBright;
  final Color goldDim;
  final Color goldSoft;
  final Color goldLine;

  // Diamond / secondary
  final Color diamond;
  final Color diamondSoft;

  // Navy / secondary data viz
  final Color navyBlue;
  final Color navySoft;

  /// Titik aksen ungu (orbit di logo).
  final Color purpleAccent;

  // Semantic
  final Color green;
  final Color greenSoft;
  final Color red;
  final Color redSoft;
  final Color amber;
  final Color amberSoft;

  // Lines
  final Color line;
  final Color lineStrong;

  // ── Brand biru (estimasi dari logo) ──────────────────────────
  static const _accent = Color(0xFF3B9EFF);
  static const _accentBright = Color(0xFF5AC8FA);
  static const _accentDim = Color(0xFF2563EB);
  static const _purple = Color(0xFF9B7BF5);

  /// Dark mode — navy background, brand biru terang.
  static const AppColors dark = AppColors(
    bgPage: Color(0xFF060A14),
    bgApp: Color(0xFF0A1124),
    bgCard: Color(0xFF111A31),
    bgElev: Color(0xFF18233F),
    bgInput: Color(0xFF0F1830),
    bgHighlight: Color(0xFF1A2547),
    ink: Color(0xFFF4F6FB),
    inkDim: Color(0xFFA8B0C4),
    inkMuted: Color(0xFF6B7390),
    inkFaint: Color(0xFF404863),
    gold: _accent,
    goldBright: _accentBright,
    goldDim: _accentDim,
    goldSoft: Color(0x1F3B9EFF),
    goldLine: Color(0x4D3B9EFF),
    diamond: Color(0xFFE8EDF5),
    diamondSoft: Color(0x1AE8EDF5),
    navyBlue: Color(0xFF4A7BC8),
    navySoft: Color(0x264A7BC8),
    purpleAccent: _purple,
    green: Color(0xFF5EC99A),
    greenSoft: Color(0x1F5EC99A),
    red: Color(0xFFE07A7A),
    redSoft: Color(0x1FE07A7A),
    amber: Color(0xFFD4A544),
    amberSoft: Color(0x1FD4A544),
    line: Color(0x0DFFFFFF),
    lineStrong: Color(0x17FFFFFF),
  );

  /// Light mode — putih bersih, brand biru tetap.
  static const AppColors light = AppColors(
    bgPage: Color(0xFFEDF0F4),
    bgApp: Color(0xFFF4F6F8),
    bgCard: Color(0xFFFFFFFF),
    bgElev: Color(0xFFFFFFFF),
    bgInput: Color(0xFFEEF1F5),
    bgHighlight: Color(0xFFE4E9F0),
    ink: Color(0xFF0A1124),
    inkDim: Color(0xFF3D4561),
    inkMuted: Color(0xFF6B7390),
    inkFaint: Color(0xFF9AA1B5),
    gold: _accentDim,
    goldBright: _accent,
    goldDim: Color(0xFF1D4ED8),
    goldSoft: Color(0x163B9EFF),
    goldLine: Color(0x382563EB),
    diamond: Color(0xFF2563EB),
    diamondSoft: Color(0x142563EB),
    navyBlue: Color(0xFF3B6FB8),
    navySoft: Color(0x1A3B6FB8),
    purpleAccent: _purple,
    green: Color(0xFF1FA871),
    greenSoft: Color(0x1A1FA871),
    red: Color(0xFFD64545),
    redSoft: Color(0x1AD64545),
    amber: Color(0xFFB8841F),
    amberSoft: Color(0x1AB8841F),
    line: Color(0x0F0A1124),
    lineStrong: Color(0x1F0A1124),
  );
}
