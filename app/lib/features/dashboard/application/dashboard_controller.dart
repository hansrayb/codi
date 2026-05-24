import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/api_exception.dart';
import '../../../api/repositories/dashboard_repository.dart';
import '../domain/dashboard_state.dart';

/// Periode terpilih — default `Bulan Ini` (`docs/06-SCREENS.md`).
final selectedPeriodProvider =
    StateProvider<Period>((ref) => Period.bulanIni);

/// Controller dashboard — fetch `GET /dashboard/summary` via repository
/// (`docs/04-API-CONTRACT.md`). Reload saat periode berubah.
class DashboardController extends Notifier<DashboardState> {
  @override
  DashboardState build() {
    ref.watch(selectedPeriodProvider);
    _load();
    return const DashboardLoading();
  }

  Future<void> _load() async {
    state = const DashboardLoading();
    final repo = ref.read(dashboardRepositoryProvider);
    final period = ref.read(selectedPeriodProvider);
    try {
      final summary = await repo.getSummary(period);
      state = DashboardSuccess(summary);
    } on ApiException catch (e) {
      state = DashboardError(e.message);
    }
  }

  /// Pull-to-refresh.
  Future<void> refresh() => _load();
}

/// Provider state dashboard.
final dashboardControllerProvider =
    NotifierProvider<DashboardController, DashboardState>(
  DashboardController.new,
);
