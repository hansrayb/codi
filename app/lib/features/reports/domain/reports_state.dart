import 'package:flutter/foundation.dart';

import '../../../models/report_item.dart';

/// State Laporan — loading / success / error / offline
/// (`docs/06-SCREENS.md` S5 → State). Pola sama Dashboard/Insight.
sealed class ReportsState {
  const ReportsState();
}

class ReportsLoading extends ReportsState {
  const ReportsLoading();
}

class ReportsSuccess extends ReportsState {
  const ReportsSuccess(this.groups);
  final List<ReportGroup> groups;
}

class ReportsError extends ReportsState {
  const ReportsError(this.message);
  final String message;
}

@immutable
class ReportsOffline extends ReportsState {
  const ReportsOffline(this.cached);
  final List<ReportGroup> cached;
}
