class ListenerProfile {
  const ListenerProfile({
    required this.firstName,
    required this.country,
    required this.region,
    required this.city,
  });

  final String firstName;
  final String country;
  final String region;
  final String city;

  factory ListenerProfile.empty() {
    return const ListenerProfile(
      firstName: '',
      country: 'Romania',
      region: '',
      city: '',
    );
  }

  factory ListenerProfile.fromJson(Map<String, dynamic> json) {
    return ListenerProfile(
      firstName: json['first_name'] as String? ?? '',
      country: json['country'] as String? ?? 'Romania',
      region: json['region'] as String? ?? '',
      city: json['city'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'first_name': firstName.trim(),
      'country': country.trim(),
      'region': region.trim(),
      'city': city.trim(),
    };
  }

  ListenerProfile copyWith({
    String? firstName,
    String? country,
    String? region,
    String? city,
  }) {
    return ListenerProfile(
      firstName: firstName ?? this.firstName,
      country: country ?? this.country,
      region: region ?? this.region,
      city: city ?? this.city,
    );
  }
}

class GeographyPreferenceMix {
  const GeographyPreferenceMix({
    required this.local,
    required this.national,
    required this.international,
  });

  final int local;
  final int national;
  final int international;

  factory GeographyPreferenceMix.defaults() {
    return const GeographyPreferenceMix(local: 34, national: 33, international: 33);
  }

  factory GeographyPreferenceMix.fromJson(Map<String, dynamic> json) {
    return GeographyPreferenceMix(
      local: _asInt(json['local'], 34),
      national: _asInt(json['national'], 33),
      international: _asInt(json['international'], 33),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'local': local,
      'national': national,
      'international': international,
    };
  }

  int get total => local + national + international;

  GeographyPreferenceMix copyWith({
    int? local,
    int? national,
    int? international,
  }) {
    return GeographyPreferenceMix(
      local: local ?? this.local,
      national: national ?? this.national,
      international: international ?? this.international,
    );
  }
}

class DomainPreferenceMix {
  const DomainPreferenceMix({
    required this.politics,
    required this.economy,
    required this.sport,
    required this.entertainment,
    required this.education,
    required this.health,
    required this.tech,
  });

  final int politics;
  final int economy;
  final int sport;
  final int entertainment;
  final int education;
  final int health;
  final int tech;

  factory DomainPreferenceMix.defaults() {
    return const DomainPreferenceMix(
      politics: 15,
      economy: 15,
      sport: 15,
      entertainment: 15,
      education: 10,
      health: 15,
      tech: 15,
    );
  }

  factory DomainPreferenceMix.fromJson(Map<String, dynamic> json) {
    return DomainPreferenceMix(
      politics: _asInt(json['politics'], 15),
      economy: _asInt(json['economy'], 15),
      sport: _asInt(json['sport'], 15),
      entertainment: _asInt(json['entertainment'], 15),
      education: _asInt(json['education'], 10),
      health: _asInt(json['health'], 15),
      tech: _asInt(json['tech'], 15),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'politics': politics,
      'economy': economy,
      'sport': sport,
      'entertainment': entertainment,
      'education': education,
      'health': health,
      'tech': tech,
    };
  }

  int get total =>
      politics + economy + sport + entertainment + education + health + tech;

  DomainPreferenceMix copyWith({
    int? politics,
    int? economy,
    int? sport,
    int? entertainment,
    int? education,
    int? health,
    int? tech,
  }) {
    return DomainPreferenceMix(
      politics: politics ?? this.politics,
      economy: economy ?? this.economy,
      sport: sport ?? this.sport,
      entertainment: entertainment ?? this.entertainment,
      education: education ?? this.education,
      health: health ?? this.health,
      tech: tech ?? this.tech,
    );
  }

  List<MapEntry<String, int>> rankedEntries() {
    final entries = <MapEntry<String, int>>[
      MapEntry('politics', politics),
      MapEntry('economy', economy),
      MapEntry('sport', sport),
      MapEntry('entertainment', entertainment),
      MapEntry('education', education),
      MapEntry('health', health),
      MapEntry('tech', tech),
    ];
    entries.sort((left, right) => right.value.compareTo(left.value));
    return entries;
  }
}

class EditorialPreferences {
  const EditorialPreferences({
    required this.geography,
    required this.domains,
  });

  final GeographyPreferenceMix geography;
  final DomainPreferenceMix domains;

  factory EditorialPreferences.defaults() {
    return EditorialPreferences(
      geography: GeographyPreferenceMix.defaults(),
      domains: DomainPreferenceMix.defaults(),
    );
  }

  factory EditorialPreferences.fromJson(Map<String, dynamic> json) {
    return EditorialPreferences(
      geography: GeographyPreferenceMix.fromJson(
        Map<String, dynamic>.from(json['geography'] as Map? ?? const {}),
      ),
      domains: DomainPreferenceMix.fromJson(
        Map<String, dynamic>.from(json['domains'] as Map? ?? const {}),
      ),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'geography': geography.toJson(),
      'domains': domains.toJson(),
    };
  }

  EditorialPreferences copyWith({
    GeographyPreferenceMix? geography,
    DomainPreferenceMix? domains,
  }) {
    return EditorialPreferences(
      geography: geography ?? this.geography,
      domains: domains ?? this.domains,
    );
  }
}

class UserPersonalization {
  const UserPersonalization({
    required this.listenerProfile,
    required this.editorialPreferences,
  });

  final ListenerProfile listenerProfile;
  final EditorialPreferences editorialPreferences;

  factory UserPersonalization.defaults() {
    return UserPersonalization(
      listenerProfile: ListenerProfile.empty(),
      editorialPreferences: EditorialPreferences.defaults(),
    );
  }

  factory UserPersonalization.fromJson(Map<String, dynamic> json) {
    return UserPersonalization(
      listenerProfile: ListenerProfile.fromJson(
        Map<String, dynamic>.from(json['listener_profile'] as Map? ?? const {}),
      ),
      editorialPreferences: EditorialPreferences.fromJson(
        Map<String, dynamic>.from(json['editorial_preferences'] as Map? ?? const {}),
      ),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'listener_profile': listenerProfile.toJson(),
      'editorial_preferences': editorialPreferences.toJson(),
    };
  }

  UserPersonalization copyWith({
    ListenerProfile? listenerProfile,
    EditorialPreferences? editorialPreferences,
  }) {
    return UserPersonalization(
      listenerProfile: listenerProfile ?? this.listenerProfile,
      editorialPreferences: editorialPreferences ?? this.editorialPreferences,
    );
  }

  String get locationSummary {
    final city = listenerProfile.city.trim();
    if (city.isEmpty) {
      return '${listenerProfile.country} / ${listenerProfile.region}';
    }
    return '${listenerProfile.country} / ${listenerProfile.region} / $city';
  }
}

int _asInt(Object? value, int fallback) {
  if (value is int) {
    return value;
  }
  if (value is double) {
    return value.round();
  }
  return fallback;
}
