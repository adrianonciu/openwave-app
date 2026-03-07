class DailyBrief {
  final DateTime date;
  final String headline;
  final List<String> highlights;
  final List<DailyBriefArticle> articles;

  DailyBrief({
    required this.date,
    required this.headline,
    required this.highlights,
    required this.articles,
  });

  factory DailyBrief.fromJson(Map<String, dynamic> json) {
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
