import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/daily_brief.dart';
import '../models/tts_pilot.dart';
import '../models/user_personalization.dart';

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

  Future<List<DailyBriefArticle>> getArticles() async {
    final response = await _client.get(Uri.parse('$_baseUrl/articles'));

    if (response.statusCode != 200) {
      throw Exception('Failed to load articles: ${response.statusCode}');
    }

    final List<dynamic> payload = jsonDecode(response.body) as List<dynamic>;
    return payload
        .map(
          (item) => DailyBriefArticle.fromJson(item as Map<String, dynamic>),
        )
        .toList();
  }

  Future<DailyBrief> generatePersonalizedBulletin(
    UserPersonalization personalization,
  ) async {
    final articles = await getArticles();
    final requestArticles = articles
        .take(10)
        .map(
          (article) => {
            'url': article.url,
            'title': article.title,
            'published_at': article.publishedAt.toUtc().toIso8601String(),
            'source': article.source,
            'content_text': article.summary,
          },
        )
        .toList();

    final response = await _client.post(
      Uri.parse('$_baseUrl/api/bulletins/generate-end-to-end'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'articles': requestArticles,
        'personalization': personalization.toJson(),
      }),
    );

    if (response.statusCode != 200) {
      throw Exception(
        'Failed to generate personalized bulletin: ${response.statusCode}',
      );
    }

    final Map<String, dynamic> payload =
        jsonDecode(response.body) as Map<String, dynamic>;
    final success = payload['success'] as bool? ?? false;
    if (!success) {
      final errors = payload['errors'] as List<dynamic>? ?? const <dynamic>[];
      final message = errors.isEmpty
          ? 'Bulletin generation failed.'
          : ((errors.first as Map<String, dynamic>)['message'] as String? ??
              'Bulletin generation failed.');
      throw Exception(message);
    }

    final finalBriefing = payload['final_editorial_briefing'] as Map<String, dynamic>?;
    if (finalBriefing == null) {
      throw Exception('Final editorial briefing is missing from the response.');
    }

    return DailyBrief.fromEditorialPackage(finalBriefing);
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
