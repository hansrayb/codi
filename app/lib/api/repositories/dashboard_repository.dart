import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/dashboard/domain/dashboard_state.dart';
import '../../models/dashboard_summary.dart';
import '../../utils/formatters/currency_formatter.dart';
import '../api_client.dart';
import '../api_exception.dart';

/// Akses `GET /dashboard/summary` + map JSON → [DashboardSummary]
/// (`docs/04-API-CONTRACT.md`).
class DashboardRepository {
  DashboardRepository(this._dio);

  final Dio _dio;

  static const _apiPeriod = {
    Period.hari: 'today',
    Period.minggu: 'week',
    Period.bulanIni: 'month',
    Period.tahun: 'year',
  };

  Future<DashboardSummary> getSummary(Period period) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/dashboard/summary',
        queryParameters: {'period': _apiPeriod[period]},
      );
      return _map(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  DashboardSummary _map(Map<String, dynamic> j) {
    final revenue = _obj(j['revenue']);
    final stats = _obj(j['quick_stats']);
    final ai = _obj(j['ai_summary']);
    final chart = _obj(j['chart_daily']);

    final growth = _num(revenue['growth_mom_pct']);
    final projection = CurrencyFormatter.compact(
      _num(revenue['projection_full_period']),
    );

    return DashboardSummary(
      periodLabel: (j['period_label'] ?? '').toString().toUpperCase(),
      omzet: _num(revenue['total']),
      trendText: '${growth >= 0 ? '+' : ''}${_id(growth)}% MoM',
      trendDirection: growth >= 0 ? TrendDirection.up : TrendDirection.down,
      periodInfo: '${_int(j['days_elapsed'])} hari · '
          '${_int(stats['orders_total'])} order · '
          'proyeksi ${projection.currency} ${projection.number} '
          '${projection.unit}'.trim(),
      sparkline: [
        for (final p in _list(revenue['sparkline']))
          _num(_obj(p)['value']).toDouble(),
      ],
      stats: _mapStats(stats),
      aiSummary: AiSummary(
        paragraphs: [
          for (final p in _list(ai['paragraphs'])) _obj(p)['text'].toString(),
        ],
        updatedAt: _date(ai['generated_at']),
        dataPoints: _int(ai['data_points_count']),
      ),
      chart: [
        for (final c in _list(chart['data']))
          ChartBar(
            label: _obj(c)['label'].toString(),
            retail: _num(_obj(c)['retail']).toDouble(),
            rotasi: _num(_obj(c)['rotasi']).toDouble(),
          ),
      ],
      highlights: [
        for (final h in _list(j['highlights']))
          Highlight(
            title: _obj(h)['title'].toString(),
            description: _obj(h)['description'].toString(),
            timestamp: _date(_obj(h)['timestamp']),
            severity: _severity(_obj(h)['severity'].toString()),
          ),
      ],
      updatedAt: _date(j['updated_at']),
    );
  }

  List<QuickStat> _mapStats(Map<String, dynamic> s) {
    final convDelta = _num(s['conversion_rate_delta_pct']);
    final expense = CurrencyFormatter.compact(_num(s['expense_total']));
    return [
      QuickStat(
        label: 'Order',
        value: _int(s['orders_total']).toString(),
        unit: 'tx',
        deltaText: '${_int(s['orders_retail'])} retail',
        direction: TrendDirection.up,
      ),
      QuickStat(
        label: 'Conv. Rate',
        value: _id(_num(s['conversion_rate_pct'])),
        unit: '%',
        deltaText: '${_id(convDelta.abs())}%',
        direction: convDelta < 0 ? TrendDirection.down : TrendDirection.up,
      ),
      QuickStat(
        label: 'Beban',
        value: expense.number,
        unit: expense.unit,
        deltaText: '${_id(_num(s['expense_pct_of_revenue']))}% omzet',
        direction: TrendDirection.flat,
        isCost: true,
      ),
    ];
  }

  HighlightSeverity _severity(String s) {
    switch (s) {
      case 'green':
        return HighlightSeverity.green;
      case 'red':
        return HighlightSeverity.red;
      case 'gold':
        return HighlightSeverity.gold;
      default:
        return HighlightSeverity.navy;
    }
  }

  // ── JSON helpers ──────────────────────────────────────────────
  Map<String, dynamic> _obj(Object? v) =>
      v is Map<String, dynamic> ? v : const {};

  List<Object?> _list(Object? v) => v is List ? v : const [];

  num _num(Object? v) => v is num ? v : num.tryParse('$v') ?? 0;

  int _int(Object? v) => _num(v).toInt();

  DateTime _date(Object? v) =>
      DateTime.tryParse('$v')?.toLocal() ?? DateTime.now();

  /// Format angka gaya Indonesia (titik desimal → koma), buang `,0`.
  String _id(num v) {
    final s = v.toStringAsFixed(1);
    return (s.endsWith('.0') ? s.substring(0, s.length - 2) : s)
        .replaceAll('.', ',');
  }
}

/// Provider repository dashboard.
final dashboardRepositoryProvider = Provider<DashboardRepository>((ref) {
  return DashboardRepository(ref.read(dioProvider));
});
