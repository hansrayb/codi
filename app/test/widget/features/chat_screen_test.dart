// Widget test Chat — mock conversation + canned reply.
//
// Catatan: messages pakai ListView.builder (lazy) — tak semua bubble
// ter-build sekaligus. Test fokus ke item yang pasti visible + interaksi.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/features/chat/presentation/chat_screen.dart';
import 'package:emas_berlian_insight/features/chat/presentation/widgets/message_bubble.dart';

Future<void> _pump(WidgetTester tester) {
  return tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        theme: AppTheme.darkTheme,
        home: const ChatScreen(),
      ),
    ),
  );
}

void main() {
  testWidgets('render header + seed conversation', (tester) async {
    await _pump(tester);
    await tester.pump();

    expect(find.text('Codi'), findsOneWidget);
    expect(
      find.text('Bagaimana kondisi operasional hari ini, Codi?'),
      findsOneWidget,
    );
    // Lazy ListView — minimal beberapa bubble ter-render.
    expect(find.byType(MessageBubble), findsWidgets);
  });

  testWidgets('kirim pesan → user bubble + canned bot reply',
      (tester) async {
    await _pump(tester);
    await tester.pump();

    await tester.enterText(find.byType(TextField), 'Tes pertanyaan');
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pump(); // user msg + sending
    await tester.pump(const Duration(milliseconds: 1200)); // reply delay
    await tester.pump(const Duration(milliseconds: 16));

    // ListView.builder lazy — reply terbaru di bawah, scroll dulu.
    await tester.scrollUntilVisible(
      find.textContaining('masih dalam pengembangan'),
      300,
      scrollable: find.byType(Scrollable).first,
    );

    expect(
      find.textContaining('masih dalam pengembangan'),
      findsOneWidget,
    );
  });

  testWidgets('tap suggestion chip → isi input', (tester) async {
    await _pump(tester);
    await tester.pump();

    // Chip pertama pasti dalam viewport (chip ke-3 off-screen di test
    // 800px). Tap → controller input terisi teks chip.
    const firstChip = '📊 Perbandingan dengan April';
    await tester.tap(find.text(firstChip));
    await tester.pump();

    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.controller?.text, firstChip);
  });
}
