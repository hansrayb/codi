import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/report_detail.dart';
import '../../models/report_item.dart';
import '../api_client.dart';
import '../api_exception.dart';

/// Akses `GET /reports?period=` + map JSON → `List<ReportGroup>`
/// (`docs/04-API-CONTRACT.md`). Pola sama [InsightRepository].
class ReportsRepository {
  ReportsRepository(this._dio);

  final Dio _dio;

  static const _apiPeriod = {
    ReportFilter.semua: 'all',
    ReportFilter.bulanIni: 'month',
    ReportFilter.kuartal: 'quarter',
    ReportFilter.tahun: 'year',
  };

  Future<List<ReportGroup>> getReports(ReportFilter filter) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/reports',
        queryParameters: {'period': _apiPeriod[filter]},
      );
      return _map(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  List<ReportGroup> _map(Map<String, dynamic> j) {
    return [
      for (final g in _list(j['groups']))
        ReportGroup(
          label: _obj(g)['label']?.toString() ?? '',
          items: [
            for (final it in _list(_obj(g)['items'])) _item(_obj(it)),
          ],
        ),
    ];
  }

  ReportItem _item(Map<String, dynamic> j) {
    final ref = j['detail_ref']?.toString();
    return ReportItem(
      title: j['title']?.toString() ?? '',
      category: _category(j['category']?.toString()),
      status: _status(j['status']?.toString()),
      createdAt: DateTime.tryParse('${j['created_at']}')?.toLocal() ??
          DateTime.now(),
      meta: j['meta']?.toString() ?? '',
      detailRef: (ref == null || ref.isEmpty) ? null : ref,
    );
  }

  /// `GET /reports/detail?ref=` → [ReportDetail]. Dipakai saat card di-klik.
  Future<ReportDetail> getReportDetail(String ref) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/reports/detail',
        queryParameters: {'ref': ref},
      );
      return _mapDetail(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  ReportDetail _mapDetail(Map<String, dynamic> j) {
    return ReportDetail(
      ref: j['ref']?.toString() ?? '',
      title: j['title']?.toString() ?? '',
      category: _category(j['category']?.toString()),
      status: _status(j['status']?.toString()),
      summary: [
        for (final s in _list(j['summary']))
          ReportStat(
            label: _obj(s)['label']?.toString() ?? '',
            value: _obj(s)['value']?.toString() ?? '',
          ),
      ],
      rows: [
        for (final r in _list(j['rows']))
          ReportDetailRow(
            label: _obj(r)['label']?.toString() ?? '',
            sub: _obj(r)['sub']?.toString() ?? '',
            value: _obj(r)['value']?.toString() ?? '',
          ),
      ],
    );
  }

  ReportCategory _category(String? v) => switch (v) {
        'payroll' => ReportCategory.payroll,
        'absensi' => ReportCategory.absensi,
        _ => ReportCategory.omzet,
      };

  ReportStatus _status(String? v) =>
      v == 'draft' ? ReportStatus.draft : ReportStatus.finalized;

  // ── helpers ───────────────────────────────────────────────────
  Map<String, dynamic> _obj(Object? v) =>
      v is Map<String, dynamic> ? v : const {};
  List<Object?> _list(Object? v) => v is List ? v : const [];
}

/// Provider repository laporan.
final reportsRepositoryProvider = Provider<ReportsRepository>((ref) {
  return ReportsRepository(ref.read(dioProvider));
});
