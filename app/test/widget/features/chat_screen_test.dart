// Widget test Chat — welcome message + real API call via fake repository.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/api/repositories/chat_repository.dart';
import 'package:emas_berlian_insight/models/chat_message.dart';
import 'package:emas_berlian_insight/features/chat/presentation/chat_screen.dart';
import 'package:emas_berlian_insight/features/chat/presentation/widgets/chat_hero.dart';
import 'package:emas_berlian_insight/providers/token_store.dart';

import '../../helpers/fake_token_store.dart';

const _replyText = 'Terima kasih, ini balasan Codi.';

class _FakeChatRepo implements ChatRepository {
  @override
  Future<ChatReply> send({
    required String message,
    String? conversationId,
    String? screen,
  }) async {
    return ChatReply(
      conversationId: 'conv_001',
      suggestions: const [],
      message: ChatMessage(
        id: 'bot_x',
        sender: MessageSender.bot,
        text: _replyText,
        time: DateTime(2026, 5, 17, 10),
        responSeconds: 0.8,
      ),
    );
  }

  @override
  Future<void> sendStream({
    required String message,
    required void Function(String delta) onToken,
    required void Function() onDone,
    required void Function(String code, String msg) onError,
  }) async {
    // Emit reply per-char untuk simulate streaming.
    for (final c in _replyText.split('')) {
      onToken(c);
      await Future<void>.delayed(const Duration(milliseconds: 1));
    }
    onDone();
  }
}

Future<void> _pump(WidgetTester tester) {
  return tester.pumpWidget(
    ProviderScope(
      overrides: [
        chatRepositoryProvider.overrideWithValue(_FakeChatRepo()),
        tokenStoreProvider.overrideWithValue(FakeTokenStore()),
      ],
      child: MaterialApp(
        theme: AppTheme.darkTheme,
        home: const ChatScreen(),
      ),
    ),
  );
}

void main() {
  testWidgets('render header + ChatHero saat empty', (tester) async {
    await _pump(tester);
    await tester.pump();

    expect(find.text('Codi'), findsOneWidget);
    expect(find.byType(ChatHero), findsOneWidget);
  });

  testWidgets('kirim pesan → user bubble + bot reply', (tester) async {
    await _pump(tester);
    await tester.pump();

    await tester.enterText(find.byType(TextField), 'Tes pertanyaan');
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pump(); // user msg + sending
    await tester.pump(); // reply future resolves
    await tester.pump(const Duration(milliseconds: 16));

    await tester.scrollUntilVisible(
      find.textContaining(_replyText),
      300,
      scrollable: find.byType(Scrollable).first,
    );

    expect(find.textContaining(_replyText), findsOneWidget);
  });

  testWidgets('tap suggestion chip → isi input', (tester) async {
    await _pump(tester);
    await tester.pump();

    // Chip pertama: "📊 Ringkasan kondisi hari ini" (controller seed).
    const firstChip = '📊 Ringkasan kondisi hari ini';
    await tester.tap(find.text(firstChip));
    await tester.pump();

    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.controller?.text, firstChip);
  });
}
