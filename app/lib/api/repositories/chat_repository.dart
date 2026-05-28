import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/chat_message.dart';
import '../api_client.dart';
import '../api_exception.dart';

/// Hasil kirim pesan: balasan bot + saran lanjutan + id percakapan.
class ChatReply {
  const ChatReply({
    required this.message,
    required this.suggestions,
    required this.conversationId,
  });

  final ChatMessage message;
  final List<String> suggestions;
  final String conversationId;
}

/// Akses endpoint chat (`docs/04-API-CONTRACT.md` → Chat).
class ChatRepository {
  ChatRepository(this._dio);

  final Dio _dio;
  int _seq = 0;

  /// Kirim pesan → balasan Codi. Throw [ApiException] jika gagal.
  ///
  /// Timeout 120s — Claude CLI subprocess di backend bisa lambat
  /// (~30-90s untuk pertanyaan kompleks). Default Dio 30s tak cukup.
  Future<ChatReply> send({
    required String message,
    String? conversationId,
    String? screen,
  }) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/chat/messages',
        options: Options(
          receiveTimeout: const Duration(seconds: 120),
          sendTimeout: const Duration(seconds: 30),
        ),
        data: {
          'conversation_id': conversationId,
          'message': message,
          if (screen != null) 'context': {'screen': screen},
        },
      );
      final j = res.data ?? const {};
      final content = _obj(j['content']);
      final meta = _obj(j['metadata']);
      final ms = _num(meta['response_time_ms']);
      return ChatReply(
        conversationId: (j['conversation_id'] ?? 'conv_001').toString(),
        suggestions: [
          for (final s in _list(j['suggestions'])) s.toString(),
        ],
        message: ChatMessage(
          id: (j['message_id'] ?? 'bot_${_seq++}').toString(),
          sender: MessageSender.bot,
          text: content['text']?.toString() ?? '',
          time: DateTime.now(),
          responSeconds: ms > 0 ? ms / 1000.0 : null,
          card: _card(_obj(content['card'])),
        ),
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  RichCard? _card(Map<String, dynamic> c) {
    if (c.isEmpty) return null;
    final badge = _obj(c['badge']);
    final chart = _obj(c['inline_chart']);
    return RichCard(
      title: c['title']?.toString() ?? '',
      badge: badge['label']?.toString(),
      badgeColor: _badgeColor(badge['color']?.toString()),
      rows: [
        for (final r in _list(c['rows']))
          RichRow(
            label: _obj(r)['label'].toString(),
            value: _obj(r)['value'].toString(),
            trend: _trend(_obj(r)['trend']?.toString()),
          ),
      ],
      sparkline: [
        for (final v in _list(chart['data'])) _num(v).toDouble(),
      ],
      actions: [
        for (final a in _list(c['actions']))
          RichAction(
            label: _obj(a)['label'].toString(),
            primary: _obj(a)['deep_link'] != null,
          ),
      ],
    );
  }

  RichBadgeColor _badgeColor(String? c) {
    switch (c) {
      case 'red':
        return RichBadgeColor.red;
      case 'gold':
        return RichBadgeColor.gold;
      default:
        return RichBadgeColor.green;
    }
  }

  RichTrend _trend(String? t) {
    switch (t) {
      case 'up':
        return RichTrend.up;
      case 'down':
        return RichTrend.down;
      default:
        return RichTrend.neutral;
    }
  }

  Map<String, dynamic> _obj(Object? v) =>
      v is Map<String, dynamic> ? v : const {};
  List<Object?> _list(Object? v) => v is List ? v : const [];
  num _num(Object? v) => v is num ? v : num.tryParse('$v') ?? 0;
}

/// Provider repository chat.
final chatRepositoryProvider = Provider<ChatRepository>((ref) {
  return ChatRepository(ref.read(dioProvider));
});
