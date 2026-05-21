import 'package:flutter/foundation.dart';

import '../../../models/insight_detail.dart';

/// State Insight — loading / success / error / offline
/// (`docs/06-SCREENS.md` S4 → State). Pola sama dengan Dashboard.
sealed class InsightState {
  const InsightState();
}

class InsightLoading extends InsightState {
  const InsightLoading();
}

class InsightSuccess extends InsightState {
  const InsightSuccess(this.data);
  final InsightDetail data;
}

class InsightError extends InsightState {
  const InsightError(this.message);
  final String message;
}

/// Offline — tampilkan cache + banner.
@immutable
class InsightOffline extends InsightState {
  const InsightOffline(this.cached);
  final InsightDetail cached;
}
