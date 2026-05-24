import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/api_exception.dart';
import '../../../api/repositories/insight_repository.dart';
import '../../dashboard/application/dashboard_controller.dart'
    show selectedPeriodProvider;
import '../domain/insight_state.dart';

/// Controller Insight (S4) — fetch `GET /dashboard/insight` via repository
/// (`docs/04-API-CONTRACT.md`). Share `selectedPeriodProvider` dgn Dashboard.
class InsightController extends Notifier<InsightState> {
  @override
  InsightState build() {
    ref.watch(selectedPeriodProvider);
    _load();
    return const InsightLoading();
  }

  Future<void> _load() async {
    state = const InsightLoading();
    final repo = ref.read(insightRepositoryProvider);
    final period = ref.read(selectedPeriodProvider);
    try {
      state = InsightSuccess(await repo.getInsight(period));
    } on ApiException catch (e) {
      state = InsightError(e.message);
    }
  }

  /// Pull-to-refresh.
  Future<void> refresh() => _load();
}

/// Provider state insight.
final insightControllerProvider =
    NotifierProvider<InsightController, InsightState>(
  InsightController.new,
);
