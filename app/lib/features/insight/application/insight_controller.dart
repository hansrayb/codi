import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/insight_detail.dart';
import '../../dashboard/application/dashboard_controller.dart'
    show selectedPeriodProvider;
import '../domain/insight_state.dart';

/// Controller Insight (S4).
///
/// **Mock data** sesuai angka mockup `docs/emas-berlian-insight.html`
/// (SCREEN 4). Ganti dengan `GET /insight/detail?period=` saat backend
/// Codi siap (`docs/04-API-CONTRACT.md`, `docs/07-ROADMAP.md`). Reload
/// saat periode berubah — share `selectedPeriodProvider` dgn Dashboard.
class InsightController extends Notifier<InsightState> {
  @override
  InsightState build() {
    ref.watch(selectedPeriodProvider);
    _load();
    return const InsightLoading();
  }

  Future<void> _load() async {
    state = const InsightLoading();
    await Future<void>.delayed(const Duration(milliseconds: 700));
    state = InsightSuccess(_mock());
  }

  /// Pull-to-refresh.
  Future<void> refresh() => _load();

  InsightDetail _mock() {
    final now = DateTime(2026, 5, 17, 14, 30);
    return InsightDetail(
      title: 'Insight Operasional',
      periodLabel: 'Periode: 1 – 17 Mei 2026',
      isLive: true,
      kpis: const [
        InsightKpi(
          label: 'Omzet Total',
          value: 'Rp 828,8',
          unit: 'jt',
          deltaText: '+321% MoM',
          direction: TrendDirection.up,
        ),
        InsightKpi(
          label: 'Order Settled',
          value: '55',
          unit: ' tx',
          deltaText: '15 retail · 40 rotasi',
          direction: TrendDirection.up,
        ),
        InsightKpi(
          label: 'Avg. Ticket',
          value: 'Rp 15,1',
          unit: 'jt',
          deltaText: '+21,8%',
          direction: TrendDirection.up,
        ),
        InsightKpi(
          label: 'Potensi Hilang',
          value: 'Rp 127',
          unit: 'jt',
          deltaText: '24 order expired',
          direction: TrendDirection.down,
          isCost: true,
        ),
      ],
      donutTotalLabel: '828,8',
      donutTotalUnit: 'jt',
      donutSlices: const [
        DonutSlice(
          label: 'Penjualan Emas',
          percent: 79.2,
          color: DonutColor.gold,
        ),
        DonutSlice(
          label: 'Rotasi Masuk',
          percent: 20.8,
          color: DonutColor.navy,
        ),
      ],
      donutCaption: 'Komposisi Omzet',
      analysisTitle: 'Analisis Mendalam',
      analysisAuthor: 'Disusun oleh Codi',
      analysisUpdatedAt: now.subtract(const Duration(minutes: 14)),
      analysisSections: const [
        DeepAnalysisSection(
          heading: 'Yang Sehat.',
          body: 'Omzet Mei naik tajam ke Rp 828,8 jt — pertumbuhan '
              '+321% dibanding April. Penjualan emas retail kembali '
              'aktif setelah bulan April nol transaksi. Avg. ticket '
              'size naik dari Rp 12,4 jt ke Rp 15,1 jt, menunjukkan '
              'kualitas pembeli yang membaik. Beban komisi terjaga '
              'rendah di 1,3% dari omzet — rasio yang sangat aman.',
        ),
        DeepAnalysisSection(
          heading: 'Yang Perlu Perhatian.',
          body: 'Conversion rate turun dari 100% di April ke 68,8% — '
              '24 order senilai Rp 127 jt tidak terbayar. Ini bukan '
              'kerugian, melainkan missed revenue. Jika tim Marketing '
              '& Kemitraan dapat memperbaiki tindak lanjut, potensi '
              'tambahan Rp 50–60 jt di sisa bulan dapat tercapai.',
        ),
        DeepAnalysisSection(
          heading: 'Catatan.',
          body: 'Data sistem baru sejak April 2026 — benchmark '
              'historis belum solid. Estimasi gross profit emas '
              'berkisar Rp 6–20 jt (margin 1–3%) — angka ini perlu '
              'dibandingkan dengan total payroll Rp 159 jt untuk '
              'gambaran kas operasional yang akurat.',
        ),
      ],
      analysisMeta: '12 data point · 4 sumber',
      updatedAt: now,
    );
  }
}

/// Provider state Insight.
final insightControllerProvider =
    NotifierProvider<InsightController, InsightState>(
  InsightController.new,
);
