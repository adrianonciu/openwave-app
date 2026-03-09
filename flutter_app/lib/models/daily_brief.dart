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
