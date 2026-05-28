// Fake TokenStore untuk widget test — tak butuh secure storage real.

import 'package:emas_berlian_insight/providers/token_store.dart';

class FakeTokenStore implements TokenStore {
  FakeTokenStore({
    this.accessToken = 'fake-token',
    this.name = 'Leo Sastra C.W.',
    this.title = 'Direktur Utama',
    this.email = 'leo@lumbungemas.co.id',
    this.role = 'director',
    this.accountId = 'acc_test',
    this.scopes = const <String>['dashboard:read', 'insight:read', 'chat:use'],
    this.hasEnrolledBiometric = false,
  });

  @override
  String? accessToken;
  @override
  String name;
  @override
  String title;
  @override
  String email;
  @override
  String role;
  @override
  String accountId;
  @override
  List<String> scopes;
  @override
  bool hasEnrolledBiometric;

  @override
  bool get hasToken => (accessToken ?? '').isNotEmpty;

  @override
  bool hasScope(String scope) => scopes.contains(scope);

  @override
  Future<void> load() async {}

  @override
  Future<void> save({required String accessToken, String? refreshToken}) async {
    this.accessToken = accessToken;
  }

  @override
  Future<void> saveSession({
    required String accessToken,
    String? refreshToken,
    List<String>? scopes,
    String? role,
    String? email,
    String? accountId,
    String? name,
    String? title,
  }) async {
    this.accessToken = accessToken;
    if (scopes != null) this.scopes = scopes;
    if (role != null) this.role = role;
    if (email != null) this.email = email;
    if (accountId != null) this.accountId = accountId;
    if (name != null) this.name = name;
    if (title != null) this.title = title;
  }

  @override
  Future<void> setEnrolled(bool value) async {
    hasEnrolledBiometric = value;
  }

  @override
  Future<void> clear() async {
    accessToken = null;
  }

  @override
  Future<void> clearEnrollment() async {
    hasEnrolledBiometric = false;
  }
}
