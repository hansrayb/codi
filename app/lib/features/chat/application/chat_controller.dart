import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/api_exception.dart';
import '../../../api/repositories/chat_repository.dart';
import '../../../models/chat_message.dart';
import '../domain/chat_state.dart';

/// Controller Chat.
///
/// **Mock** — history awal = percakapan mockup
/// `docs/emas-berlian-insight.html`. Kirim pesan → canned reply setelah
/// delay (backend `POST /chat/messages` belum ada,
/// `docs/04-API-CONTRACT.md`, `docs/07-ROADMAP.md` Risk Register).
class ChatController extends Notifier<ChatState> {
  int _seq = 0;

  @override
  ChatState build() {
    return ChatState(
      messages: _seedConversation(),
      suggestions: const [
        '📊 Perbandingan dengan April',
        '📈 Proyeksi akhir bulan',
        '👥 Status karyawan',
      ],
    );
  }

  String _nextId() => 'm${_seq++}';

  List<ChatMessage> _seedConversation() {
    final base = DateTime(2026, 5, 17, 9, 42);
    return [
      ChatMessage(
        id: _nextId(),
        sender: MessageSender.user,
        text: 'Bagaimana kondisi operasional hari ini, Codi?',
        time: base,
      ),
      ChatMessage(
        id: _nextId(),
        sender: MessageSender.bot,
        text: 'Selamat pagi Bapak Leo. Berikut ringkasan kondisi kantor '
            'hari ini:',
        time: base,
        responSeconds: 0.8,
        card: const RichCard(
          title: 'Status Mei 2026',
          badge: 'SEHAT',
          badgeColor: RichBadgeColor.green,
          rows: [
            RichRow(
              label: 'Omzet',
              value: 'Rp 828,8 jt',
              trend: RichTrend.up,
            ),
            RichRow(
              label: 'Pertumbuhan MoM',
              value: '+321%',
              trend: RichTrend.up,
            ),
            RichRow(
              label: 'Conv. Rate',
              value: '68,8%',
              trend: RichTrend.down,
            ),
            RichRow(label: 'Beban Komisi', value: '1,3% omzet'),
          ],
          sparkline: [12, 15, 10, 22, 30, 36, 42, 50],
          actions: [
            RichAction(label: 'Lihat Ringkasan'),
            RichAction(label: 'Export PDF', primary: false),
          ],
        ),
      ),
      ChatMessage(
        id: _nextId(),
        sender: MessageSender.user,
        text: 'Apa yang perlu jadi prioritas Bapak?',
        time: DateTime(2026, 5, 17, 9, 44),
      ),
      ChatMessage(
        id: _nextId(),
        sender: MessageSender.bot,
        text: 'Tiga hal yang sebaiknya Bapak ketahui:\n\n'
            '1. Conversion rate turun ke 68,8% — ada Rp 127 jt potensi '
            'yang lolos. Tim Marketing & Kemitraan dapat menindaklanjuti.\n\n'
            '2. Susi Susan (Komisaris) absen 7 hari berturut-turut — '
            'perlu klarifikasi dari HRGA.\n\n'
            '3. Pertumbuhan retail sangat positif — momentum yang bisa '
            'diperkuat.',
        time: DateTime(2026, 5, 17, 9, 44),
        responSeconds: 1.1,
      ),
    ];
  }

  String? _conversationId;

  /// Kirim pesan user → balasan Codi via `POST /chat/messages`.
  Future<void> send(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || state.isSending) return;

    final userMsg = ChatMessage(
      id: _nextId(),
      sender: MessageSender.user,
      text: trimmed,
      time: DateTime.now(),
    );
    state = state.copyWith(
      messages: [...state.messages, userMsg],
      isSending: true,
      clearError: true,
    );

    try {
      final reply = await ref.read(chatRepositoryProvider).send(
            message: trimmed,
            conversationId: _conversationId,
            screen: 'chat',
          );
      _conversationId = reply.conversationId;
      state = state.copyWith(
        messages: [...state.messages, reply.message],
        suggestions: reply.suggestions.isNotEmpty
            ? reply.suggestions
            : state.suggestions,
        isSending: false,
      );
    } on ApiException catch (e) {
      state = state.copyWith(isSending: false, error: e.message);
    }
  }
}

/// Provider state Chat.
final chatControllerProvider =
    NotifierProvider<ChatController, ChatState>(ChatController.new);
