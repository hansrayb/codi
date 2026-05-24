import 'package:flutter/foundation.dart';

/// Kategori laporan — menentukan ikon & warna card (mockup SCREEN 5).
enum ReportCategory { omzet, payroll, absensi }

/// Status laporan — badge (mockup `.badge-final` / `.badge-draft`).
enum ReportStatus {
  finalized('Final'),
  draft('Draft');

  const ReportStatus(this.label);

  /// Label badge.
  final String label;
}

/// Satu kartu laporan (mockup `.report-card`).
@immutable
class ReportItem {
  const ReportItem({
    required this.title,
    required this.category,
    required this.status,
    required this.createdAt,
    required this.meta,
  });

  /// Mis. "Ringkasan Omzet — Mei 2026".
  final String title;

  final ReportCategory category;
  final ReportStatus status;

  /// Tanggal generate — dipakai grouping (Terbaru / Bulan Lalu).
  final DateTime createdAt;

  /// Mis. "4 hal", "22 karyawan · Rp 159 jt".
  final String meta;
}

/// Grup laporan dengan label section (mockup `.list-section-label`).
@immutable
class ReportGroup {
  const ReportGroup({required this.label, required this.items});

  /// Mis. "Terbaru", "Bulan Lalu".
  final String label;
  final List<ReportItem> items;
}

/// Filter periode (mockup `.filter-bar .filter-chip`).
enum ReportFilter {
  semua('Semua'),
  bulanIni('Bulan Ini'),
  kuartal('Kuartal'),
  tahun('Tahun');

  const ReportFilter(this.label);

  /// Label chip.
  final String label;
}
