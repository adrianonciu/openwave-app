class TtsPilotSummary {
  final String pilotId;
  final String title;
  final String presenterName;

  const TtsPilotSummary({
    required this.pilotId,
    required this.title,
    required this.presenterName,
  });

  factory TtsPilotSummary.fromJson(Map<String, dynamic> json) {
    return TtsPilotSummary(
      pilotId: json['pilot_id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      presenterName: json['presenter_name'] as String? ?? 'Corina',
    );
  }
}

class GeneratedPilotAudio {
  final String pilotId;
  final String title;
  final String presenterName;
  final String audioUrl;
  final String briefingText;
  final String ttsProvider;
  final String ttsVoiceId;

  const GeneratedPilotAudio({
    required this.pilotId,
    required this.title,
    required this.presenterName,
    required this.audioUrl,
    required this.briefingText,
    required this.ttsProvider,
    required this.ttsVoiceId,
  });

  factory GeneratedPilotAudio.fromJson(
    Map<String, dynamic> json, {
    required String resolvedAudioUrl,
  }) {
    return GeneratedPilotAudio(
      pilotId: json['pilot_id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      presenterName: json['presenter_name'] as String? ?? 'Corina',
      audioUrl: resolvedAudioUrl,
      briefingText: json['briefing_text'] as String? ?? '',
      ttsProvider: json['tts_provider'] as String? ?? '',
      ttsVoiceId: json['tts_voice_id'] as String? ?? '',
    );
  }
}
