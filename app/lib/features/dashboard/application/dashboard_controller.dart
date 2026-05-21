import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/dashboard_summary.dart';
import '../domain/dashboard_state.dart';

/// Periode terpilih — default `Bulan Ini` (`docs/06-SCREENS.md`).
final selectedPeriodProvider =
    StateProvider<Period>((ref) => Period.bulanIni);

/// Controller dashboard.
///
/// **Mock data** sesuai angka mockup `docs/emas-berlian-insight.html`.
/// Ganti dengan `GET /dashboard/summary?period=` saat backend Codi siap
/// (`docs/04-API-CONTRACT.md`, `docs/07-ROADMAP.md` Risk Register).
class DashboardController extends Notifier<DashboardState> {
  @override
  DashboardState build() {
    // Reload saat periode berubah.
    ref.watch(selectedPeriodProvider);
    _load();
    return const DashboardLoading();
  }

  Future<void> _load() async {
    state = const DashboardLoading();
    await Future<void>.delayed(const Duration(milliseconds: 700));
    state = DashboardSuccess(_mock());
  }

  /// Pull-to-refresh.
  Future<void> refresh() => _load();

  DashboardSummary _mock() {
    final now = DateTime(2026, 5, 17, 14, 30);
    return DashboardSummary(
      periodLabel: 'MEI 2026',
      omzet: 828800000,
      trendText: '+321% MoM',
      trendDirection: TrendDirection.up,
      periodInfo: '17 hari · 55 order · proyeksi Rp 1,51 M',
      sparkline: const [
        10, 12, 8, 15, 20, 18, 22, 28, 25, 30, 34, 38, 35, 40, 42, 45, 46,
      ],
      stats: const [
        QuickStat(
          label: 'Order',
          value: '55',
          unit: 'tx',
          deltaText: '15 retail',
          direction: TrendDirection.up,
        ),
        QuickStat(
          label: 'Conv. Rate',
          value: '68,8',
          unit: '%',
          deltaText: '31,2%',
          direction: TrendDirection.down,
        ),
        QuickStat(
          label: 'Beban',
          value: '10,8',
          unit: 'jt',
          deltaText: '1,3% omzet',
          direction: TrendDirection.flat,
          isCost: true,
        ),
      ],
      aiSummary: AiSummary(
        updatedAt: now.subtract(const Duration(minutes: 14)),
        dataPoints: 12,
        paragraphs: const [
          'Operasional kantor berada dalam kondisi sehat. Omzet Mei sudah '
              'melampaui April dengan pertumbuhan signifikan, didorong '
              'kembalinya penjualan emas retail (Rp 656 jt dari 15 order).',
          'Yang memerlukan perhatian: conversion rate turun ke 68,8% — '
              'terdapat Rp 127 jt potensi pendapatan dari 24 order yang '
              'expired. Jika dikonversi sebagian, omzet bulan ini berpotensi '
              'naik Rp 50–60 jt.',
          'Beban komisi tetap rendah di 1,3% dari omzet — rasio yang '
              'sangat sehat.',
        ],
      ),
      chart: const [
        ChartBar(label: '11', retail: 40, rotasi: 23),
        ChartBar(label: '12', retail: 58, rotasi: 30),
        ChartBar(label: '13', retail: 33, rotasi: 26),
        ChartBar(label: '14', retail: 70, rotasi: 33),
        ChartBar(label: '15', retail: 82, rotasi: 38),
        ChartBar(label: '16', retail: 66, rotasi: 28),
        ChartBar(label: '17', retail: 93, rotasi: 36),
      ],
      highlights: [
        Highlight(
          severity: HighlightSeverity.green,
          title: 'Penjualan emas retail kembali aktif',
          description:
              'Rp 656 jt dari 15 order (240,6g) — bulan April nol '
              'penjualan retail.',
          timestamp: DateTime(2026, 5, 14, 14, 30),
        ),
        Highlight(
          severity: HighlightSeverity.red,
          title: '24 order expired bulan ini',
          description:
              'Total nilai Rp 127 jt tidak terbayar — conversion rate '
              'turun dari 100% ke 68,8%.',
          timestamp: DateTime(2026, 5, 17, 9, 20),
        ),
        Highlight(
          severity: HighlightSeverity.navy,
          title: 'Payroll Mei sudah ter-generate',
          description:
              '22 karyawan · total Rp 159 jt · sedang menunggu '
              'finalisasi oleh HRGA.',
          timestamp: DateTime(2026, 5, 15, 16, 45),
        ),
      ],
      updatedAt: now,
    );
  }
}

/// Provider state dashboard.
final dashboardControllerProvider =
    NotifierProvider<DashboardController, DashboardState>(
  DashboardController.new,
);
