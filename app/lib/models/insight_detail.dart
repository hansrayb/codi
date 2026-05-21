import 'package:flutter/foundation.dart';

import 'dashboard_summary.dart' show TrendDirection;

export 'dashboard_summary.dart' show TrendDirection;

/// Satu KPI cell di grid Insight (mockup `.kpi-cell`).
@immutable
class InsightKpi {
  const InsightKpi({
    required this.label,
    required this.value,
    required this.unit,
    required this.deltaText,
    required this.direction,
    this.isCost = false,
  });

  /// Mis. "Omzet Total".
  final String label;

  /// Nilai sudah ter-format, mis. "Rp 828,8".
  final String value;

  /// Unit kecil di belakang value, mis. "jt", " tx".
  final String unit;

  /// Mis. "+321% MoM", "24 order expired".
  final String deltaText;

  final TrendDirection direction;

  /// True kalau metrik biaya/negatif — arah delta dibalik (naik = merah).
  final bool isCost;
}

/// Satu potong donut komposisi omzet (mockup `.donut-legend .dlg`).
@immutable
class DonutSlice {
  const DonutSlice({
    required this.label,
    required this.percent,
    required this.color,
  });

  /// Mis. "Penjualan Emas".
  final String label;

  /// Persentase 0–100.
  final double percent;

  /// Token warna: `gold` (brand) atau `navy` (sekunder).
  final DonutColor color;
}

/// Pilihan warna slice — resolve ke `context.colors` di painter.
enum DonutColor { gold, navy }

/// Analisis mendalam dari Codi (mockup `.ai-summary` di screen Insight).
///
/// Tiap paragraf punya judul tebal + body. Untuk MVP body plain text.
@immutable
class DeepAnalysisSection {
  const DeepAnalysisSection({required this.heading, required this.body});

  /// Mis. "Yang Sehat.".
  final String heading;

  /// Isi paragraf.
  final String body;
}

/// Payload detail Insight — `GET /insight/detail?period=...`
/// (`docs/04-API-CONTRACT.md`). Saat ini di-mock.
@immutable
class InsightDetail {
  const InsightDetail({
    required this.title,
    required this.periodLabel,
    required this.isLive,
    required this.kpis,
    required this.donutTotalLabel,
    required this.donutTotalUnit,
    required this.donutSlices,
    required this.donutCaption,
    required this.analysisTitle,
    required this.analysisAuthor,
    required this.analysisUpdatedAt,
    required this.analysisSections,
    required this.analysisMeta,
    required this.updatedAt,
  });

  /// Mis. "Insight Operasional".
  final String title;

  /// Mis. "Periode: 1 – 17 Mei 2026".
  final String periodLabel;

  /// Badge "· Live".
  final bool isLive;

  final List<InsightKpi> kpis;

  /// Angka tengah donut, mis. "828,8".
  final String donutTotalLabel;

  /// Unit tengah donut, mis. "jt".
  final String donutTotalUnit;

  final List<DonutSlice> donutSlices;

  /// Mis. "Komposisi Omzet".
  final String donutCaption;

  /// Mis. "Analisis Mendalam".
  final String analysisTitle;

  /// Mis. "Disusun oleh Codi".
  final String analysisAuthor;

  final DateTime analysisUpdatedAt;
  final List<DeepAnalysisSection> analysisSections;

  /// Mis. "12 data point · 4 sumber".
  final String analysisMeta;

  final DateTime updatedAt;
}
