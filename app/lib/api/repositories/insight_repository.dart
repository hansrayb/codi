import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/dashboard/domain/dashboard_state.dart';
import '../../models/insight_detail.dart';
import '../../utils/formatters/currency_formatter.dart';
import '../api_client.dart';
import '../api_exception.dart';

/// Akses `GET /dashboard/insight` + map JSON → [InsightDetail]
/// (`docs/04-API-CONTRACT.md`).
class InsightRepository {
  InsightRepository(this._dio);

  final Dio _dio;

  static const _apiPeriod = {
    Period.hari: 'today',
    Period.minggu: 'week',
    Period.bulanIni: 'month',
    Period.tahun: 'year',
  };

  Future<InsightDetail> getInsight(Period period) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/dashboard/insight',
        queryParameters: {'period': _apiPeriod[period]},
      );
      return _map(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  InsightDetail _map(Map<String, dynamic> j) {
    final comp = _obj(j['composition']);
    final analysis = _obj(j['ai_analysis']);
    final meta = _obj(analysis['metadata']);
    final total = CurrencyFormatter.compact(_num(comp['total']));

    return InsightDetail(
      title: 'Insight Operasional',
      periodLabel: 'Periode: ${j['period_label'] ?? '-'}',
      isLive: true,
      kpis: [for (final k in _list(j['kpis'])) _kpi(_obj(k))],
      donutTotalLabel: total.number,
      donutTotalUnit: total.unit,
      donutCaption: comp['label']?.toString() ?? 'Komposisi Omzet',
      donutSlices: [
        for (final s in _list(comp['segments']))
          DonutSlice(
            label: _obj(s)['label'].toString(),
            percent: _num(_obj(s)['pct']).toDouble(),
            color: _obj(s)['color'] == 'navy'
                ? DonutColor.navy
                : DonutColor.gold,
          ),
      ],
      analysisTitle: 'Analisis Mendalam',
      analysisAuthor: 'Disusun oleh Codi',
      analysisUpdatedAt: _date(analysis['generated_at']),
      analysisSections: [
        for (final s in _list(analysis['sections']))
          DeepAnalysisSection(
            heading: _obj(s)['title'].toString(),
            body: _obj(s)['content'].toString(),
          ),
      ],
      analysisMeta: '${_int(meta['data_points'])} data point · '
          '${_int(meta['sources_count'])} sumber',
      updatedAt: _date(j['updated_at']),
    );
  }

  InsightKpi _kpi(Map<String, dynamic> k) {
    final unit = k['unit']?.toString() ?? '';
    final trend = k['trend']?.toString();
    final isMoney = unit == 'IDR';
    final String value;
    final String displayUnit;
    if (isMoney) {
      final c = CurrencyFormatter.compact(_num(k['value']));
      value = '${c.currency} ${c.number}';
      displayUnit = c.unit;
    } else {
      value = _int(k['value']).toString();
      displayUnit = unit;
    }
    return InsightKpi(
      label: k['label'].toString(),
      value: value,
      unit: displayUnit,
      deltaText: k['delta_label']?.toString() ?? '',
      direction: trend == 'down' ? TrendDirection.down : TrendDirection.up,
      isCost: k['key'] == 'potential_lost',
    );
  }

  // ── helpers ───────────────────────────────────────────────────
  Map<String, dynamic> _obj(Object? v) =>
      v is Map<String, dynamic> ? v : const {};
  List<Object?> _list(Object? v) => v is List ? v : const [];
  num _num(Object? v) => v is num ? v : num.tryParse('$v') ?? 0;
  int _int(Object? v) => _num(v).toInt();
  DateTime _date(Object? v) =>
      DateTime.tryParse('$v')?.toLocal() ?? DateTime.now();
}

/// Provider repository insight.
final insightRepositoryProvider = Provider<InsightRepository>((ref) {
  return InsightRepository(ref.read(dioProvider));
});
