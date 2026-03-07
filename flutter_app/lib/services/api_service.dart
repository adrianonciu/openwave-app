import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/daily_brief.dart';

class ApiService {
  ApiService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  String get _baseUrl {
    if (Platform.isAndroid) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://127.0.0.1:8000';
  }

  Future<DailyBrief> getDailyBrief() async {
    final response = await _client.get(Uri.parse('$_baseUrl/briefing/today'));

    if (response.statusCode != 200) {
      throw Exception('Failed to load daily brief: ${response.statusCode}');
    }

    final Map<String, dynamic> payload =
        jsonDecode(response.body) as Map<String, dynamic>;

    return DailyBrief.fromJson(payload);
  }
}