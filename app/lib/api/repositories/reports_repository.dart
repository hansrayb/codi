import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
    return ReportItem(
      title: j['title']?.toString() ?? '',
      category: _category(j['category']?.toString()),
      status: _status(j['status']?.toString()),
      createdAt: DateTime.tryParse('${j['created_at']}')?.toLocal() ??
          DateTime.now(),
      meta: j['meta']?.toString() ?? '',
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
