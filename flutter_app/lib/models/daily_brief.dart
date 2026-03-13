class DailyBrief {
  final DateTime date;
  final String headline;
  final List<String> highlights;
  final List<DailyBriefArticle> articles;
  final List<DailyBriefSegment>? segments;

  DailyBrief({
    required this.date,
    required this.headline,
    required this.highlights,
    required this.articles,
    this.segments,
  });

  factory DailyBrief.fromJson(Map<String, dynamic> json) {
    final rawSegments = json['segments'] as List<dynamic>?;

    return DailyBrief(
      date: DateTime.parse(json['date'] as String),
      headline: json['headline'] as String? ?? '',
      highlights: (json['highlights'] as List<dynamic>? ?? const <dynamic>[])
          .map((item) => item.toString())
          .toList(),
      articles: (json['articles'] as List<dynamic>? ?? const <dynamic>[])
          .map(
            (item) => DailyBriefArticle.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
      segments: rawSegments == null
          ? null
          : rawSegments
                .map(
                  (item) =>
                      DailyBriefSegment.fromJson(item as Map<String, dynamic>),
                )
                .toList(),
    );
  }

  factory DailyBrief.fromEditorialPackage(Map<String, dynamic> json) {
    final createdAt = DateTime.tryParse(json['created_at'] as String? ?? '') ??
        DateTime.now();
    final storyItems = (json['story_items'] as List<dynamic>? ?? const <dynamic>[])
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();

    final articles = <DailyBriefArticle>[];
    final segments = <DailyBriefSegment>[
      DailyBriefSegment(
        id: 0,
        type: 'intro',
        title: 'OpenWave intro',
        summary: json['intro_text'] as String? ?? '',
        source: 'OpenWave',
        estimatedDurationSeconds: 10,
        tags: const ['intro'],
        articleId: 0,
        narrationText: json['intro_text'] as String? ?? '',
        section: 'Intro',
      ),
    ];

    for (var index = 0; index < storyItems.length; index++) {
      final item = storyItems[index];
      final story = Map<String, dynamic>.from(item['story'] as Map? ?? const {});
      final title = story['short_headline'] as String? ??
          story['representative_title'] as String? ??
          'OpenWave story';
      final summary = story['summary_text'] as String? ?? '';
      final sourceLabels =
          (story['source_labels'] as List<dynamic>? ?? const <dynamic>[])
              .map((entry) => entry.toString())
              .toList();
      final policyCompliance = Map<String, dynamic>.from(
        story['policy_compliance'] as Map? ?? const {},
      );
      final topicLabel = story['topic_label'] as String? ?? 'general';
      final sourceLabel =
          sourceLabels.isEmpty ? 'OpenWave' : sourceLabels.join(', ');
      final passPhrase = item['pass_phrase_used'] as String?;
      final narrationText = passPhrase == null || passPhrase.trim().isEmpty
          ? summary
          : '${passPhrase.trim()} $summary';

      articles.add(
        DailyBriefArticle(
          id: index + 1,
          title: title,
          source: sourceLabel,
          summary: summary,
          url: '',
          publishedAt: createdAt,
        ),
      );

      segments.add(
        DailyBriefSegment(
          id: index + 1,
          type: 'article',
          title: title,
          summary: summary,
          source: sourceLabel,
          estimatedDurationSeconds:
              policyCompliance['estimated_duration_seconds'] as int? ?? 30,
          tags: [topicLabel],
          articleId: index + 1,
          narrationText: narrationText,
          section: topicLabel,
        ),
      );

      final perspectiveSegments =
          (item['perspective_segments'] as List<dynamic>? ?? const <dynamic>[])
              .map((entry) => Map<String, dynamic>.from(entry as Map))
              .toList();
      for (final perspective in perspectiveSegments) {
        segments.add(DailyBriefSegment.fromJson(perspective));
      }
    }

    segments.add(
      DailyBriefSegment(
        id: storyItems.length + 1,
        type: 'outro',
        title: 'OpenWave outro',
        summary: json['outro_text'] as String? ?? '',
        source: 'OpenWave',
        estimatedDurationSeconds: 10,
        tags: const ['outro'],
        articleId: 0,
        narrationText: json['outro_text'] as String? ?? '',
        section: 'Outro',
      ),
    );

    return DailyBrief(
      date: createdAt,
      headline: 'OpenWave personalized briefing',
      highlights: articles.map((article) => article.title).toList(),
      articles: articles,
      segments: segments,
    );
  }
}

class DailyBriefArticle {
  final int id;
  final String title;
  final String source;
  final String summary;
  final String url;
  final DateTime publishedAt;

  DailyBriefArticle({
    required this.id,
    required this.title,
    required this.source,
    required this.summary,
    required this.url,
    required this.publishedAt,
  });

  factory DailyBriefArticle.fromJson(Map<String, dynamic> json) {
    return DailyBriefArticle(
      id: json['id'] as int? ?? 0,
      title: json['title'] as String? ?? '',
      source: json['source'] as String? ?? '',
      summary: json['summary'] as String? ?? '',
      url: json['url'] as String? ?? '',
      publishedAt: DateTime.parse(json['published_at'] as String),
    );
  }
}

class DailyBriefSegment {
  final int id;
  final String type;
  final String title;
  final String summary;
  final String source;
  final int estimatedDurationSeconds;
  final List<String> tags;
  final int articleId;
  final String narrationText;
  final String section;
  final int? durationEstimate;

  DailyBriefSegment({
    required this.id,
    required this.type,
    required this.title,
    required this.summary,
    required this.source,
    required this.estimatedDurationSeconds,
    required this.tags,
    required this.articleId,
    required this.narrationText,
    required this.section,
    this.durationEstimate,
  });

  factory DailyBriefSegment.fromJson(Map<String, dynamic> json) {
    return DailyBriefSegment(
      id: json['id'] as int? ?? 0,
      type: json['type'] as String? ?? '',
      title: json['title'] as String? ?? '',
      summary: json['summary'] as String? ?? '',
      source: json['source'] as String? ?? '',
      estimatedDurationSeconds:
          json['estimated_duration_seconds'] as int? ?? 0,
      tags: (json['tags'] as List<dynamic>? ?? const <dynamic>[])
          .map((item) => item.toString())
          .toList(),
      articleId: json['article_id'] as int? ?? 0,
      narrationText: json['narration_text'] as String? ?? '',
      section: json['section'] as String? ?? 'General',
      durationEstimate: json['duration_estimate'] as int?,
    );
  }
}
