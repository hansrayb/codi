import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/report_item.dart';
import '../domain/reports_state.dart';

/// Filter periode terpilih — default `Semua` (mockup SCREEN 5).
final selectedReportFilterProvider =
    StateProvider<ReportFilter>((ref) => ReportFilter.semua);

/// Controller Laporan (S5).
///
/// **Mock data** sesuai mockup `docs/emas-berlian-insight.html`
/// (SCREEN 5). Ganti dengan `GET /reports?period=` saat backend Codi
/// siap (`docs/04-API-CONTRACT.md`). Reload saat filter berubah.
class ReportsController extends Notifier<ReportsState> {
  @override
  ReportsState build() {
    ref.watch(selectedReportFilterProvider);
    _load();
    return const ReportsLoading();
  }

  Future<void> _load() async {
    state = const ReportsLoading();
    await Future<void>.delayed(const Duration(milliseconds: 700));
    state = ReportsSuccess(_mock(ref.read(selectedReportFilterProvider)));
  }

  /// Pull-to-refresh.
  Future<void> refresh() => _load();

  List<ReportGroup> _mock(ReportFilter filter) {
    final terbaru = ReportGroup(
      label: 'Terbaru',
      items: [
        ReportItem(
          title: 'Ringkasan Omzet — Mei 2026',
          category: ReportCategory.omzet,
          status: ReportStatus.finalized,
          createdAt: _d(2026, 5, 17),
          meta: '17 Mei 2026 · 4 hal',
        ),
        ReportItem(
          title: 'Payroll Run — Mei 2026',
          category: ReportCategory.payroll,
          status: ReportStatus.draft,
          createdAt: _d(2026, 5, 15),
          meta: '15 Mei 2026 · 22 karyawan · Rp 159 jt',
        ),
        ReportItem(
          title: 'Rekap Absensi — Mei 2026',
          category: ReportCategory.absensi,
          status: ReportStatus.finalized,
          createdAt: _d(2026, 5, 14),
          meta: '14 Mei 2026 · 22 karyawan',
        ),
      ],
    );
    final bulanLalu = ReportGroup(
      label: 'Bulan Lalu',
      items: [
        ReportItem(
          title: 'Ringkasan Omzet — April 2026',
          category: ReportCategory.omzet,
          status: ReportStatus.finalized,
          createdAt: _d(2026, 4, 30),
          meta: '30 Apr 2026 · 3 hal',
        ),
        ReportItem(
          title: 'Payroll Run — April 2026',
          category: ReportCategory.payroll,
          status: ReportStatus.finalized,
          createdAt: _d(2026, 4, 16),
          meta: '16 Apr 2026 · 22 karyawan · Rp 154 jt',
        ),
      ],
    );

    // Filter periode mempersempit grup yang ditampilkan.
    switch (filter) {
      case ReportFilter.bulanIni:
        return [terbaru];
      case ReportFilter.semua:
      case ReportFilter.kuartal:
      case ReportFilter.tahun:
        return [terbaru, bulanLalu];
    }
  }

  /// Const DateTime helper (mock).
  static DateTime _d(int y, int m, int day) => DateTime(y, m, day);
}

/// Provider state Laporan.
final reportsControllerProvider =
    NotifierProvider<ReportsController, ReportsState>(
  ReportsController.new,
);
