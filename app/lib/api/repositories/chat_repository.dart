import 'dart:async';
import 'dart:convert';

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

/// Ringkasan satu percakapan tersimpan (`GET /chat/conversations`).
class ChatConversation {
  const ChatConversation({
    required this.id,
    required this.title,
    required this.preview,
    required this.messageCount,
    this.lastMessageAt,
  });

  final String id;
  final String title;
  final String preview;
  final int messageCount;
  final DateTime? lastMessageAt;
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

  /// Streaming reply via SSE (`POST /chat/messages/stream`).
  /// Token-by-token append via [onToken]; [onDone] di akhir; [onError]
  /// untuk error server-side. Return future yang complete saat stream ditutup.
  ///
  /// Backend emit event SSE: `meta`, `token`, `done`, `error`. Heartbeat
  /// `: ping\n\n` keep-alive setiap 15s.
  Future<void> sendStream({
    required String message,
    required void Function(String delta) onToken,
    required void Function() onDone,
    required void Function(String code, String msg) onError,
    String? conversationId,
    void Function(String conversationId)? onMeta,
  }) async {
    try {
      final res = await _dio.post<ResponseBody>(
        '/chat/messages/stream',
        data: {
          'message': message,
          if (conversationId != null) 'conversation_id': conversationId,
        },
        options: Options(
          responseType: ResponseType.stream,
          receiveTimeout: const Duration(minutes: 5),
          sendTimeout: const Duration(seconds: 30),
          headers: {'Accept': 'text/event-stream'},
        ),
      );
      final stream = res.data!.stream
          .cast<List<int>>()
          .transform(utf8.decoder)
          .transform(const LineSplitter());
      String currentEvent = '';
      var ended = false;
      await for (final line in stream) {
        if (line.isEmpty) {
          currentEvent = '';
          continue;
        }
        if (line.startsWith(':')) continue; // keep-alive ping
        if (line.startsWith('event:')) {
          currentEvent = line.substring(6).trim();
          continue;
        }
        if (line.startsWith('data:')) {
          final data = line.substring(5).trim();
          if (data.isEmpty) continue;
          try {
            final j = jsonDecode(data) as Map<String, dynamic>;
            switch (currentEvent) {
              case 'meta':
                final cid = j['conversation_id']?.toString();
                if (cid != null && cid.isNotEmpty) onMeta?.call(cid);
                break;
              case 'token':
                final delta = j['delta']?.toString() ?? '';
                if (delta.isNotEmpty) onToken(delta);
                break;
              case 'done':
                ended = true;
                onDone();
                return;
              case 'error':
                ended = true;
                onError(
                  j['code']?.toString() ?? 'unknown',
                  j['message']?.toString() ?? 'Error.',
                );
                return;
            }
          } catch (_) {
            // skip malformed event
          }
        }
      }
      if (!ended) onDone();
    } on DioException catch (e) {
      onError(_errorCode(e), ApiException.fromDio(e).message);
    }
  }

  /// Daftar percakapan tersimpan (urut terbaru, server-side).
  Future<List<ChatConversation>> getConversations() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>('/chat/conversations');
      final j = res.data ?? const {};
      return [
        for (final c in _list(j['conversations']))
          ChatConversation(
            id: _obj(c)['id']?.toString() ?? '',
            title: _obj(c)['title']?.toString() ?? '',
            preview: _obj(c)['preview']?.toString() ?? '',
            messageCount: _num(_obj(c)['message_count']).toInt(),
            lastMessageAt:
                DateTime.tryParse('${_obj(c)['last_message_at']}')?.toLocal(),
          ),
      ];
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Pesan-pesan dalam satu percakapan.
  Future<List<ChatMessage>> getMessages(String conversationId) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/chat/conversations/$conversationId/messages',
      );
      final j = res.data ?? const {};
      return [
        for (final m in _list(j['messages']))
          ChatMessage(
            id: _obj(m)['id']?.toString() ?? '',
            sender: _obj(m)['role']?.toString() == 'user'
                ? MessageSender.user
                : MessageSender.bot,
            text: _obj(_obj(m)['content'])['text']?.toString() ?? '',
            time: DateTime.tryParse('${_obj(m)['timestamp']}')?.toLocal() ??
                DateTime.now(),
          ),
      ];
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  String _errorCode(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.sendTimeout:
        return 'timeout';
      case DioExceptionType.connectionError:
        return 'network';
      case DioExceptionType.badResponse:
        return 'http_${e.response?.statusCode ?? 0}';
      default:
        return 'unknown';
    }
  }
}

/// Provider repository chat.
final chatRepositoryProvider = Provider<ChatRepository>((ref) {
  return ChatRepository(ref.read(dioProvider));
});
