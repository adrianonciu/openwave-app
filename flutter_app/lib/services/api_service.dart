import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/daily_brief.dart';
import '../models/tts_pilot.dart';
import '../models/user_personalization.dart';

class BulletinGenerationException implements Exception {
  BulletinGenerationException({
    required this.message,
    this.code,
    this.suggestions = const <String>[],
    this.estimatedRequiredCredits,
    this.remainingCredits,
    this.estimatedTotalCharacters,
    this.segmentCount,
    this.estimatedDurationSeconds,
  });

  final String message;
  final String? code;
  final List<String> suggestions;
  final int? estimatedRequiredCredits;
  final int? remainingCredits;
  final int? estimatedTotalCharacters;
  final int? segmentCount;
  final int? estimatedDurationSeconds;

  String get userMessage => message;

  bool get isTtsBudgetIssue => code == 'tts_budget_exceeded';

  String? get estimateSummary {
    final parts = <String>[];
    if (estimatedDurationSeconds != null && estimatedDurationSeconds! > 0) {
      final minutes = (estimatedDurationSeconds! / 60).ceil();
      parts.add('Estimated briefing length: about $minutes min');
    }
    if (estimatedTotalCharacters != null && estimatedTotalCharacters! > 0) {
      parts.add('audio size $estimatedTotalCharacters chars');
    }
    if (segmentCount != null && segmentCount! > 0) {
      parts.add('$segmentCount segments');
    }
    if (parts.isEmpty) {
      return null;
    }
    return parts.join(' | ');
  }

  String? get budgetSummary {
    if (estimatedRequiredCredits == null && remainingCredits == null) {
      return null;
    }

    final pieces = <String>[];
    if (estimatedRequiredCredits != null) {
      pieces.add('Required: $estimatedRequiredCredits');
    }
    if (remainingCredits != null) {
      pieces.add('Remaining: $remainingCredits');
    }
    return pieces.join(' | ');
  }

  @override
  String toString() => message;
}

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
      throw _buildGenerationException(payload);
    }

    final finalBriefing =
        payload['final_editorial_briefing'] as Map<String, dynamic>?;
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

  BulletinGenerationException _buildGenerationException(
    Map<String, dynamic> payload,
  ) {
    final errors = payload['errors'] as List<dynamic>? ?? const <dynamic>[];
    final firstError = errors.isEmpty
        ? const <String, dynamic>{}
        : Map<String, dynamic>.from(errors.first as Map);
    final ttsBudgetEstimate = payload['tts_budget_estimate'] as Map<String, dynamic>?;
    final estimatedDurationSeconds = payload['estimated_total_duration_seconds'] as int?;

    final code = firstError['code'] as String?;
    if (code == 'tts_budget_exceeded') {
      return BulletinGenerationException(
        code: code,
        message:
            'Audio could not be generated because this briefing is larger than the current TTS quota allows.',
        suggestions: const <String>[
          'Try a shorter bulletin.',
          'Reduce the story count for this run.',
          'Use a lower-cost voice or test mode if it is available.',
        ],
        estimatedRequiredCredits: _readInt(
          firstError['estimated_required_credits'] ??
              ttsBudgetEstimate?['estimated_required_credits'],
        ),
        remainingCredits: _readInt(
          firstError['remaining_credits'] ?? ttsBudgetEstimate?['remaining_credits'],
        ),
        estimatedTotalCharacters: _readInt(
          firstError['estimated_total_characters'] ??
              ttsBudgetEstimate?['estimated_total_characters'],
        ),
        segmentCount: _readInt(
          firstError['segment_count'] ?? ttsBudgetEstimate?['segment_count'],
        ),
        estimatedDurationSeconds: estimatedDurationSeconds,
      );
    }

    final message = firstError['message'] as String? ?? 'Bulletin generation failed.';
    return BulletinGenerationException(
      code: code,
      message: _sanitizeMessage(message),
      estimatedDurationSeconds: estimatedDurationSeconds,
    );
  }

  int? _readInt(Object? value) {
    if (value is int) {
      return value;
    }
    if (value is String) {
      return int.tryParse(value);
    }
    return null;
  }

  String _sanitizeMessage(String message) {
    final trimmed = message.trim();
    if (trimmed.startsWith('Exception: ')) {
      return trimmed.substring('Exception: '.length);
    }
    if (trimmed.startsWith('ElevenLabs request failed:')) {
      return 'Audio generation failed while contacting the TTS provider.';
    }
    return trimmed;
  }

  String resolveUrl(String path) {
    return Uri.parse(_baseUrl).resolve(path).toString();
  }
}
