import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../../../../api/repositories/profile_repository.dart';
import '../../../../models/codi_session.dart';
import '../../../../providers/settings_store.dart';
import '../../../../providers/token_store.dart';
import '../../../../theme/app_theme.dart';
import '../../application/profile_controller.dart';

/// Buka bottom sheet generik (handle + judul + child).
Future<void> _openSheet(BuildContext context, Widget child) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _SheetShell(child: child),
  );
}

/// Identitas (read-only) — nama, email, role, id akun, biometric.
Future<void> showIdentitasSheet(BuildContext context, TokenStore store) {
  final rows = <(String, String)>[
    ('Nama', store.name.isNotEmpty ? store.name : '-'),
    ('Email', store.email.isNotEmpty ? store.email : '-'),
    ('Jabatan', store.title.isNotEmpty ? store.title : '-'),
    ('Role', store.role.isNotEmpty ? store.role : '-'),
    if (store.accountId.isNotEmpty) ('ID Akun', store.accountId),
    ('Biometric', store.hasEnrolledBiometric ? 'Aktif' : 'Nonaktif'),
  ];
  return _openSheet(
    context,
    _InfoBody(title: 'Identitas', icon: Icons.person_outline, rows: rows),
  );
}

/// Info perusahaan (read-only).
Future<void> showPerusahaanSheet(BuildContext context, String org) {
  final rows = <(String, String)>[
    ('Perusahaan', 'PT Odc Inter Rotasi'),
    ('Unit', 'Kantor Operasional'),
    ('Konteks', org),
    ('Aplikasi', 'Emas Berlian Insight'),
  ];
  return _openSheet(
    context,
    _InfoBody(title: 'Perusahaan', icon: Icons.apartment_outlined, rows: rows),
  );
}

/// Picker tema (Sistem / Terang / Gelap) — set + persist via [themeModeProvider].
Future<void> showThemePicker(BuildContext context) {
  return _openSheet(context, const _ThemePickerBody());
}

/// Sheet daftar sesi Codi aktif (fetch `GET /me/sessions`).
Future<void> showSessionsSheet(BuildContext context) {
  return _openSheet(context, const _SessionsBody());
}

/// Tentang — versi real (`package_info_plus`) + lisensi.
Future<void> showAboutSheet(BuildContext context) {
  return _openSheet(context, const _AboutBody());
}

// ── Shell + shared bits ───────────────────────────────────────────────

class _SheetShell extends StatelessWidget {
  const _SheetShell({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final maxH = MediaQuery.sizeOf(context).height * 0.8;
    return SafeArea(
      child: Container(
        constraints: BoxConstraints(maxHeight: maxH),
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.s20,
          AppSpacing.s12,
          AppSpacing.s20,
          AppSpacing.s20,
        ),
        decoration: BoxDecoration(
          color: c.bgApp,
          borderRadius: const BorderRadius.vertical(
            top: Radius.circular(AppRadius.r20),
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: c.line,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.s16),
            Flexible(child: child),
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.title, required this.icon});
  final String title;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Row(
      children: [
        Container(
          width: 42,
          height: 42,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: c.goldSoft,
            borderRadius: BorderRadius.circular(AppRadius.r12),
            border: Border.all(color: c.goldLine),
          ),
          child: Icon(icon, size: 20, color: c.gold),
        ),
        const SizedBox(width: AppSpacing.s14),
        Expanded(
          child: Text(
            title,
            style: AppTypography.headlineS.copyWith(color: c.ink),
          ),
        ),
      ],
    );
  }
}

// ── Info sheet (identitas / perusahaan) ───────────────────────────────

class _InfoBody extends StatelessWidget {
  const _InfoBody({required this.title, required this.icon, required this.rows});
  final String title;
  final IconData icon;
  final List<(String, String)> rows;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _Header(title: title, icon: icon),
          const SizedBox(height: AppSpacing.s16),
          Container(
            padding: const EdgeInsets.all(AppSpacing.s16),
            decoration: BoxDecoration(
              color: c.bgCard,
              borderRadius: BorderRadius.circular(AppRadius.r16),
              border: Border.all(color: c.line),
            ),
            child: Column(
              children: [
                for (var i = 0; i < rows.length; i++) ...[
                  if (i > 0) const SizedBox(height: AppSpacing.s10),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        rows[i].$1,
                        style: AppTypography.bodyS.copyWith(color: c.inkMuted),
                      ),
                      const SizedBox(width: AppSpacing.s12),
                      Expanded(
                        child: Text(
                          rows[i].$2,
                          textAlign: TextAlign.right,
                          style: AppTypography.bodyM.copyWith(
                            color: c.ink,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Theme picker ──────────────────────────────────────────────────────

class _ThemePickerBody extends ConsumerWidget {
  const _ThemePickerBody();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final current = ref.watch(themeModeProvider);
    const modes = [ThemeMode.system, ThemeMode.light, ThemeMode.dark];
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _Header(title: 'Tema', icon: Icons.dark_mode_outlined),
        const SizedBox(height: AppSpacing.s16),
        for (final m in modes) ...[
          _ChoiceRow(
            label: ProfileController.themeLabel(m),
            selected: m == current,
            onTap: () async {
              await ref.read(themeModeProvider.notifier).set(m);
              if (context.mounted) Navigator.of(context).pop();
            },
          ),
          if (m != modes.last) const SizedBox(height: AppSpacing.s8),
        ],
      ],
    );
  }
}

class _ChoiceRow extends StatelessWidget {
  const _ChoiceRow({
    required this.label,
    required this.selected,
    required this.onTap,
  });
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.s14),
        decoration: BoxDecoration(
          color: c.bgCard,
          borderRadius: BorderRadius.circular(AppRadius.r12),
          border: Border.all(color: selected ? c.goldLine : c.line),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: AppTypography.bodyL.copyWith(
                  color: c.ink,
                  fontWeight: FontWeight.w500,
                  fontSize: 13,
                ),
              ),
            ),
            if (selected) Icon(Icons.check, size: 18, color: c.gold),
          ],
        ),
      ),
    );
  }
}

// ── Sessions ──────────────────────────────────────────────────────────

final _sessionsProvider = FutureProvider.autoDispose<CodiSessions>((ref) {
  return ref.read(profileRepositoryProvider).getSessions();
});

class _SessionsBody extends ConsumerWidget {
  const _SessionsBody();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final async = ref.watch(_sessionsProvider);
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _Header(title: 'Sesi Codi', icon: Icons.auto_awesome),
        const SizedBox(height: AppSpacing.s16),
        Flexible(
          child: async.when(
            loading: () => const Padding(
              padding: EdgeInsets.symmetric(vertical: AppSpacing.s32),
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (e, _) => Padding(
              padding: const EdgeInsets.symmetric(vertical: AppSpacing.s24),
              child: Text(
                'Gagal memuat sesi.\n$e',
                textAlign: TextAlign.center,
                style: AppTypography.bodyS.copyWith(color: c.red),
              ),
            ),
            data: (d) => d.sessions.isEmpty
                ? Padding(
                    padding:
                        const EdgeInsets.symmetric(vertical: AppSpacing.s24),
                    child: Text(
                      'Tidak ada sesi orchestrator aktif.',
                      textAlign: TextAlign.center,
                      style: AppTypography.bodyM.copyWith(color: c.inkMuted),
                    ),
                  )
                : SingleChildScrollView(
                    child: Column(
                      children: [
                        for (var i = 0; i < d.sessions.length; i++) ...[
                          if (i > 0) const SizedBox(height: AppSpacing.s8),
                          _SessionTile(s: d.sessions[i]),
                        ],
                      ],
                    ),
                  ),
          ),
        ),
      ],
    );
  }
}

class _SessionTile extends StatelessWidget {
  const _SessionTile({required this.s});
  final CodiSession s;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final sub = [
      if (s.repoName.isNotEmpty) s.repoName,
      if (s.idleSeconds != null) 'idle ${_idle(s.idleSeconds!)}',
    ].join(' · ');
    final started = s.startedAt == null
        ? ''
        : DateFormat('d MMM, HH:mm', 'id_ID').format(s.startedAt!);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.s14),
      decoration: BoxDecoration(
        color: c.bgCard,
        borderRadius: BorderRadius.circular(AppRadius.r12),
        border: Border.all(color: c.line),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  s.role.isNotEmpty ? s.role : 'sesi',
                  style: AppTypography.bodyL.copyWith(
                    color: c.ink,
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                  ),
                ),
                if (sub.isNotEmpty) ...[
                  const SizedBox(height: 1),
                  Text(
                    sub,
                    style: AppTypography.bodyS
                        .copyWith(color: c.inkMuted, fontSize: 11),
                  ),
                ],
              ],
            ),
          ),
          if (started.isNotEmpty) ...[
            const SizedBox(width: AppSpacing.s12),
            Text(
              started,
              style: AppTypography.bodyS.copyWith(color: c.inkFaint),
            ),
          ],
        ],
      ),
    );
  }

  static String _idle(int seconds) {
    if (seconds < 60) return '${seconds}d';
    final m = seconds ~/ 60;
    if (m < 60) return '${m}mnt';
    final h = m ~/ 60;
    return '${h}j ${m % 60}mnt';
  }
}

// ── About ─────────────────────────────────────────────────────────────

class _AboutBody extends StatelessWidget {
  const _AboutBody();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return FutureBuilder<PackageInfo>(
      future: PackageInfo.fromPlatform(),
      builder: (context, snap) {
        final info = snap.data;
        final version = info == null
            ? '…'
            : 'v${info.version} (build ${info.buildNumber})';
        return SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const _Header(title: 'Tentang', icon: Icons.info_outline),
              const SizedBox(height: AppSpacing.s16),
              _InfoCard(rows: [
                ('Aplikasi', info?.appName ?? 'Emas Berlian Insight'),
                ('Versi', version),
                if (info != null && info.packageName.isNotEmpty)
                  ('Paket', info.packageName),
                ('Engine', 'Powered by Codi'),
              ]),
              const SizedBox(height: AppSpacing.s12),
              Text(
                '© 2026 PT Odc Inter Rotasi. Hak cipta dilindungi.\n'
                'Penggunaan internal eksekutif.',
                textAlign: TextAlign.center,
                style: AppTypography.bodyS.copyWith(color: c.inkFaint),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({required this.rows});
  final List<(String, String)> rows;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.s16),
      decoration: BoxDecoration(
        color: c.bgCard,
        borderRadius: BorderRadius.circular(AppRadius.r16),
        border: Border.all(color: c.line),
      ),
      child: Column(
        children: [
          for (var i = 0; i < rows.length; i++) ...[
            if (i > 0) const SizedBox(height: AppSpacing.s10),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  rows[i].$1,
                  style: AppTypography.bodyS.copyWith(color: c.inkMuted),
                ),
                const SizedBox(width: AppSpacing.s12),
                Expanded(
                  child: Text(
                    rows[i].$2,
                    textAlign: TextAlign.right,
                    style: AppTypography.bodyM.copyWith(
                      color: c.ink,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
