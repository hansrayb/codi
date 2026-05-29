// Widget test Chat — welcome message + real API call via fake repository.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

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
    String? conversationId,
    void Function(String conversationId)? onMeta,
  }) async {
    onMeta?.call('conv_fake_1');
    // Emit reply per-char untuk simulate streaming.
    for (final c in _replyText.split('')) {
      onToken(c);
      await Future<void>.delayed(const Duration(milliseconds: 1));
    }
    onDone();
  }

  @override
  Future<List<ChatConversation>> getConversations() async {
    await Future<void>.delayed(const Duration(milliseconds: 10));
    return [
      ChatConversation(
        id: 'conv_fake_1',
        title: 'Kondisi operasional Mei',
        preview: 'Tiga hal yang perlu Bapak tahu...',
        messageCount: 4,
        lastMessageAt: DateTime(2026, 5, 17, 9, 44),
      ),
    ];
  }

  @override
  Future<List<ChatMessage>> getMessages(String conversationId) async {
    await Future<void>.delayed(const Duration(milliseconds: 10));
    return [
      ChatMessage(
        id: 'h1',
        sender: MessageSender.user,
        text: 'Halo dari riwayat',
        time: DateTime(2026, 5, 17, 9, 42),
      ),
      ChatMessage(
        id: 'h2',
        sender: MessageSender.bot,
        text: 'Balasan tersimpan dari riwayat.',
        time: DateTime(2026, 5, 17, 9, 43),
      ),
    ];
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
  setUpAll(() async {
    await initializeDateFormatting('id_ID');
  });

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

  testWidgets('tap ⋯ → menu muncul', (tester) async {
    await _pump(tester);
    await tester.pump();

    await tester.tap(find.byIcon(Icons.more_horiz));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300)); // menu anim

    expect(find.text('Percakapan baru'), findsOneWidget);
    expect(find.text('Salin percakapan'), findsOneWidget);
    expect(find.text('Tentang Codi'), findsOneWidget);
  });

  testWidgets('menu → Tentang Codi → sheet', (tester) async {
    await _pump(tester);
    await tester.pump();

    await tester.tap(find.byIcon(Icons.more_horiz));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Tentang Codi'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300)); // sheet anim

    expect(find.text('Penasihat (advisor)'), findsOneWidget);
  });

  testWidgets('kirim lalu Percakapan baru → kembali ke ChatHero',
      (tester) async {
    await _pump(tester);
    await tester.pump();

    await tester.enterText(find.byType(TextField), 'Halo');
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pump();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 16));
    expect(find.byType(ChatHero), findsNothing); // ada pesan

    await tester.tap(find.byIcon(Icons.more_horiz));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Percakapan baru'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300)); // confirm dialog
    await tester.tap(find.text('Mulai baru'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 16));

    expect(find.byType(ChatHero), findsOneWidget); // kosong lagi
  });

  testWidgets('menu → Riwayat → pilih percakapan → muat pesan',
      (tester) async {
    await _pump(tester);
    await tester.pump();

    await tester.tap(find.byIcon(Icons.more_horiz));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Riwayat percakapan'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300)); // sheet anim
    await tester.pump(const Duration(milliseconds: 50)); // fetch convs

    expect(find.text('Kondisi operasional Mei'), findsOneWidget);

    await tester.tap(find.text('Kondisi operasional Mei'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50)); // fetch messages
    await tester.pump(const Duration(milliseconds: 16));

    await tester.scrollUntilVisible(
      find.textContaining('Balasan tersimpan dari riwayat'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(
      find.textContaining('Balasan tersimpan dari riwayat'),
      findsOneWidget,
    );
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
