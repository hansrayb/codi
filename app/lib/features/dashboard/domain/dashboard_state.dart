import 'package:flutter/foundation.dart';

import '../../../models/dashboard_summary.dart';

/// Periode filter dashboard (`docs/06-SCREENS.md` → Period Selector).
enum Period {
  hari('Hari'),
  minggu('Minggu'),
  bulanIni('Bulan Ini'),
  tahun('Tahun');

  const Period(this.label);

  /// Label tampil di chip.
  final String label;
}

/// State dashboard — loading / success / error / offline
/// (`docs/06-SCREENS.md` → State).
sealed class DashboardState {
  const DashboardState();
}

class DashboardLoading extends DashboardState {
  const DashboardLoading();
}

class DashboardSuccess extends DashboardState {
  const DashboardSuccess(this.data);
  final DashboardSummary data;
}

class DashboardError extends DashboardState {
  const DashboardError(this.message);
  final String message;
}

/// Offline — tampilkan cache + banner.
@immutable
class DashboardOffline extends DashboardState {
  const DashboardOffline(this.cached);
  final DashboardSummary cached;
}
