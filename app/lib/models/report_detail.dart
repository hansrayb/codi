import 'package:flutter/foundation.dart';

import 'report_item.dart';

/// Satu baris ringkasan (header stat) detail laporan.
/// Mis. label "Total", value "Rp 159.410.448".
@immutable
class ReportStat {
  const ReportStat({required this.label, required this.value});

  final String label;
  final String value;
}

/// Satu baris rincian (line item) detail laporan.
/// Mis. label "Budi S.", sub "Operasional", value "Rp 7.500.000".
@immutable
class ReportDetailRow {
  const ReportDetailRow({
    required this.label,
    required this.value,
    this.sub = '',
  });

  final String label;
  final String value;
  final String sub;
}

/// Detail satu laporan (drill-down) — hasil `GET /reports/detail?ref=`.
/// Render generik & agnostik kategori: blok [summary] + list [rows].
@immutable
class ReportDetail {
  const ReportDetail({
    required this.ref,
    required this.title,
    required this.category,
    required this.status,
    required this.summary,
    required this.rows,
  });

  final String ref;
  final String title;
  final ReportCategory category;
  final ReportStatus status;
  final List<ReportStat> summary;
  final List<ReportDetailRow> rows;
}
