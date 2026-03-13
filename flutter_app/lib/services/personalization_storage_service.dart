import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/user_personalization.dart';

class PersonalizationStorageService {
  static const String _storageKey = 'openwave_user_personalization';

  Future<UserPersonalization?> loadPersonalization() async {
    final preferences = await SharedPreferences.getInstance();
    final rawValue = preferences.getString(_storageKey);
    if (rawValue == null || rawValue.trim().isEmpty) {
      return null;
    }

    final payload = jsonDecode(rawValue) as Map<String, dynamic>;
    return UserPersonalization.fromJson(payload);
  }

  Future<void> savePersonalization(UserPersonalization personalization) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(
      _storageKey,
      jsonEncode(personalization.toJson()),
    );
  }
}
