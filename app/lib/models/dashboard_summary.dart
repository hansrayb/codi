import 'package:flutter/foundation.dart';

/// Arah tren delta — menentukan warna & ikon.
enum TrendDirection { up, down, flat }

/// Severity highlight (border kiri berwarna di mockup).
enum HighlightSeverity { green, red, gold, navy }

/// Satu stat mini di stats row.
@immutable
class QuickStat {
  const QuickStat({
    required this.label,
    required this.value,
    required this.unit,
    required this.deltaText,
    required this.direction,
    this.isCost = false,
  });

  final String label;
  final String value;
  final String unit;
  final String deltaText;
  final TrendDirection direction;

  /// True kalau metrik biaya — arah delta dibalik (naik = merah).
  final bool isCost;
}

/// Ringkasan AI dari Codi (3 paragraf, plain text untuk MVP).
@immutable
class AiSummary {
  const AiSummary({
    required this.paragraphs,
    required this.updatedAt,
    required this.dataPoints,
  });

  final List<String> paragraphs;
  final DateTime updatedAt;
  final int dataPoints;
}

/// Satu bar group chart 7 hari (retail vs rotasi).
@immutable
class ChartBar {
  const ChartBar({
    required this.label,
    required this.retail,
    required this.rotasi,
  });

  final String label;
  final double retail;
  final double rotasi;
}

/// Item sorotan.
@immutable
class Highlight {
  const Highlight({
    required this.title,
    required this.description,
    required this.timestamp,
    required this.severity,
  });

  final String title;
  final String description;
  final DateTime timestamp;
  final HighlightSeverity severity;
}

/// Payload dashboard — `GET /dashboard/summary?period=...`
/// (`docs/04-API-CONTRACT.md`). Saat ini di-mock.
@immutable
class DashboardSummary {
  const DashboardSummary({
    required this.periodLabel,
    required this.omzet,
    required this.trendText,
    required this.trendDirection,
    required this.periodInfo,
    required this.sparkline,
    required this.stats,
    required this.aiSummary,
    required this.chart,
    required this.highlights,
    required this.updatedAt,
  });

  /// Mis. "MEI 2026".
  final String periodLabel;

  /// Nilai omzet mentah (di-format di UI).
  final num omzet;

  /// Mis. "+321% MoM".
  final String trendText;
  final TrendDirection trendDirection;

  /// Mis. "17 hari · 55 order · proyeksi Rp 1,51 M".
  final String periodInfo;

  /// Titik sparkline (y values, urut waktu).
  final List<double> sparkline;

  final List<QuickStat> stats;
  final AiSummary aiSummary;
  final List<ChartBar> chart;
  final List<Highlight> highlights;
  final DateTime updatedAt;
}
