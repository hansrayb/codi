import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/api_exception.dart';
import '../../../api/repositories/reports_repository.dart';
import '../../../models/report_item.dart';
import '../domain/reports_state.dart';

/// Filter periode terpilih — default `Semua` (mockup SCREEN 5).
final selectedReportFilterProvider =
    StateProvider<ReportFilter>((ref) => ReportFilter.semua);

/// Controller Laporan (S5) — fetch `GET /reports?period=` via repository
/// (`docs/04-API-CONTRACT.md`). Reload saat filter berubah.
class ReportsController extends Notifier<ReportsState> {
  @override
  ReportsState build() {
    ref.watch(selectedReportFilterProvider);
    _load();
    return const ReportsLoading();
  }

  Future<void> _load() async {
    state = const ReportsLoading();
    final repo = ref.read(reportsRepositoryProvider);
    final filter = ref.read(selectedReportFilterProvider);
    try {
      state = ReportsSuccess(await repo.getReports(filter));
    } on ApiException catch (e) {
      state = ReportsError(e.message);
    }
  }

  /// Pull-to-refresh.
  Future<void> refresh() => _load();
}

/// Provider state Laporan.
final reportsControllerProvider =
    NotifierProvider<ReportsController, ReportsState>(
  ReportsController.new,
);
