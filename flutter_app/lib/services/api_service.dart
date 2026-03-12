import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/daily_brief.dart';
import '../models/tts_pilot.dart';

class ApiService {
  ApiService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  static const String _baseUrl = 'http://127.0.0.1:8000';

  Future<DailyBrief> getDailyBrief() async {
    final response = await _client.get(Uri.parse('$_baseUrl/briefing/today'));

    if (response.statusCode != 200) {
      throw Exception('Failed to load daily brief: ${response.statusCode}');
    }

    final Map<String, dynamic> payload =
        jsonDecode(response.body) as Map<String, dynamic>;

    return DailyBrief.fromJson(payload);
  }

  Future<List<TtsPilotSummary>> getTtsPilots() async {
    final response = await _client.get(Uri.parse('$_baseUrl/api/tts/pilots'));

    if (response.statusCode != 200) {
      throw Exception('Failed to load TTS pilots: ${response.statusCode}');
    }

    final List<dynamic> payload = jsonDecode(response.body) as List<dynamic>;
    return payload
        .map((item) => TtsPilotSummary.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<GeneratedPilotAudio> generatePilotAudio(String pilotId) async {
    final response = await _client.post(
      Uri.parse('$_baseUrl/api/tts/generate-from-pilot'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'pilot_id': pilotId,
        'presenter_name': 'Corina',
      }),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to generate pilot audio: ${response.statusCode}');
    }

    final Map<String, dynamic> payload =
        jsonDecode(response.body) as Map<String, dynamic>;
    final audioPath = payload['audio_url'] as String? ?? '';

    return GeneratedPilotAudio.fromJson(
      payload,
      resolvedAudioUrl: resolveUrl(audioPath),
    );
  }

  String resolveUrl(String path) {
    return Uri.parse(_baseUrl).resolve(path).toString();
  }
}
