import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../widgets/widgets.dart';

/// Galeri showcase widget — **dev-only, sementara**.
///
/// Dipakai Fase 1 (Foundation) untuk verifikasi visual theme + common
/// widget via `flutter run`. Akan diganti Login screen di Fase 1 Minggu 2
/// (`docs/07-ROADMAP.md`). Jangan referensi dari kode produksi.
class WidgetGallery extends StatelessWidget {
  const WidgetGallery({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Galeri Widget', style: AppTypography.headlineM),
      ),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.s20),
        children: [
          _section(context, 'Typography'),
          Text('Emas Berlian Insight', style: AppTypography.displayL),
          const SizedBox(height: AppSpacing.s8),
          Text('Rp 1.250.000.000', style: AppTypography.numLarge),
          const SizedBox(height: AppSpacing.s8),
          Text(
            'Body teks default — ringkasan kondisi operasional kantor.',
            style: AppTypography.bodyL,
          ),
          const SizedBox(height: AppSpacing.s8),
          Text('14:30 · 17 MEI 2026', style: AppTypography.mono),

          _section(context, 'Buttons'),
          const EmasButton(
            label: 'Tombol Primary',
            onPressed: _noop,
            expand: true,
          ),
          const SizedBox(height: AppSpacing.s12),
          const EmasButton(
            label: 'Tombol Secondary',
            onPressed: _noop,
            variant: EmasButtonVariant.secondary,
            icon: Icons.refresh,
            expand: true,
          ),
          const SizedBox(height: AppSpacing.s12),
          const Align(
            alignment: Alignment.centerLeft,
            child: EmasButton(
              label: 'Ghost →',
              onPressed: _noop,
              variant: EmasButtonVariant.ghost,
            ),
          ),
          const SizedBox(height: AppSpacing.s12),
          const EmasButton(label: 'Disabled', onPressed: null, expand: true),

          _section(context, 'Cards'),
          const EmasCard(
            child: Text('Default card — bgCard, border line, radius 14.'),
          ),
          const SizedBox(height: AppSpacing.s12),
          EmasElevatedCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Omzet Bulan Ini', style: AppTypography.labelS),
                const SizedBox(height: AppSpacing.s8),
                Text('Rp 2.850.000.000', style: AppTypography.numLarge),
              ],
            ),
          ),

          _section(context, 'Avatar'),
          const Row(
            children: [
              EmasAvatar(name: 'Leo Sastra'),
              SizedBox(width: AppSpacing.s12),
              EmasAvatar(name: 'Codi', size: 38),
            ],
          ),

          _section(context, 'Input'),
          const EmasInput(hintText: 'Tanya Codi sesuatu...'),

          _section(context, 'Alert'),
          const EmasAlert(
            title: 'Pertumbuhan Sehat',
            message: 'Omzet naik 12% dibanding bulan lalu.',
            severity: EmasAlertSeverity.success,
          ),
          const SizedBox(height: AppSpacing.s12),
          const EmasAlert(
            title: 'Perlu Perhatian',
            message: 'Conversion rate turun di bawah target mingguan.',
            severity: EmasAlertSeverity.warning,
          ),

          _section(context, 'Loading'),
          const EmasLoadingCard(),

          _section(context, 'Error State'),
          const SizedBox(
            height: 220,
            child: EmasErrorView(
              message: 'Tidak ada koneksi internet. Cek WiFi/data Anda.',
              onRetry: _noop,
            ),
          ),

          _section(context, 'Empty State'),
          const SizedBox(
            height: 180,
            child: EmasEmptyView(
              message: 'Belum ada data untuk periode ini.',
            ),
          ),
          const SizedBox(height: AppSpacing.s40),
        ],
      ),
    );
  }

  Widget _section(BuildContext context, String title) => Padding(
        padding: const EdgeInsets.only(
          top: AppSpacing.s32,
          bottom: AppSpacing.s12,
        ),
        child: Text(
          title.toUpperCase(),
          style: AppTypography.labelS.copyWith(color: context.colors.gold),
        ),
      );

  static void _noop() {}
}
