import 'package:flutter/material.dart';

import '../models/user_personalization.dart';
import '../services/personalization_storage_service.dart';

class PersonalizationFlowScreen extends StatefulWidget {
  const PersonalizationFlowScreen({
    super.key,
    required this.isOnboarding,
    this.initialPersonalization,
    this.onSaved,
  });

  final bool isOnboarding;
  final UserPersonalization? initialPersonalization;
  final ValueChanged<UserPersonalization>? onSaved;

  @override
  State<PersonalizationFlowScreen> createState() =>
      _PersonalizationFlowScreenState();
}

class _PersonalizationFlowScreenState extends State<PersonalizationFlowScreen> {
  final _storageService = PersonalizationStorageService();
  final _firstNameController = TextEditingController();
  final _cityController = TextEditingController();

  int _currentStep = 0;
  bool _isSaving = false;
  String _country = 'Romania';
  String? _region;
  late GeographyPreferenceMix _geography;
  late DomainPreferenceMix _domains;

  @override
  void initState() {
    super.initState();
    final personalization =
        widget.initialPersonalization ?? UserPersonalization.defaults();
    _firstNameController.text = personalization.listenerProfile.firstName;
    _cityController.text = personalization.listenerProfile.city;
    _country = personalization.listenerProfile.country.isEmpty
        ? 'Romania'
        : personalization.listenerProfile.country;
    _region = personalization.listenerProfile.region.isEmpty
        ? null
        : personalization.listenerProfile.region;
    _geography = personalization.editorialPreferences.geography;
    _domains = personalization.editorialPreferences.domains;
  }

  @override
  void dispose() {
    _firstNameController.dispose();
    _cityController.dispose();
    super.dispose();
  }

  bool get _isProfileValid =>
      _firstNameController.text.trim().isNotEmpty &&
      (_region ?? '').trim().isNotEmpty;

  bool get _isPreferencesValid =>
      _geography.total == 100 && _domains.total == 100;

  UserPersonalization get _currentPersonalization {
    return UserPersonalization(
      listenerProfile: ListenerProfile(
        firstName: _firstNameController.text.trim(),
        country: _country,
        region: (_region ?? '').trim(),
        city: _cityController.text.trim(),
      ),
      editorialPreferences: EditorialPreferences(
        geography: _geography,
        domains: _domains,
      ),
    );
  }

  Future<void> _save() async {
    if (!_isProfileValid || !_isPreferencesValid) {
      return;
    }

    setState(() {
      _isSaving = true;
    });

    final personalization = _currentPersonalization;
    await _storageService.savePersonalization(personalization);
    widget.onSaved?.call(personalization);

    if (!mounted) {
      return;
    }

    setState(() {
      _isSaving = false;
    });

    if (widget.isOnboarding) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Personalization saved. Your next bulletin will use it.'),
        ),
      );
      return;
    }

    Navigator.of(context).pop(personalization);
  }

  Widget _buildProfileStep(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          'Listener profile',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        Text(
          'Set the identity and county anchor used by OpenWave for personalization.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 20),
        TextField(
          controller: _firstNameController,
          decoration: const InputDecoration(
            labelText: 'First name *',
            border: OutlineInputBorder(),
          ),
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 16),
        DropdownButtonFormField<String>(
          value: _country,
          decoration: const InputDecoration(
            labelText: 'Country',
            border: OutlineInputBorder(),
          ),
          items: _countries
              .map(
                (country) => DropdownMenuItem<String>(
                  value: country,
                  child: Text(country),
                ),
              )
              .toList(),
          onChanged: (value) {
            if (value == null) return;
            setState(() {
              _country = value;
            });
          },
        ),
        const SizedBox(height: 16),
        DropdownButtonFormField<String>(
          value: _region,
          decoration: const InputDecoration(
            labelText: 'Region / county *',
            helperText: 'Local news uses the county or region, not the city.',
            border: OutlineInputBorder(),
          ),
          items: _romanianCounties
              .map(
                (region) => DropdownMenuItem<String>(
                  value: region,
                  child: Text(region),
                ),
              )
              .toList(),
          onChanged: (value) {
            setState(() {
              _region = value;
            });
          },
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _cityController,
          decoration: const InputDecoration(
            labelText: 'City (optional)',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 16),
        if (!_isProfileValid)
          Text(
            'First name and region are required to continue.',
            style: TextStyle(
              color: Theme.of(context).colorScheme.error,
            ),
          ),
      ],
    );
  }

  Widget _buildPreferencesStep(BuildContext context) {
    final personalization = _currentPersonalization;
    final topDomains = personalization.editorialPreferences.domains
        .rankedEntries()
        .take(2)
        .map((entry) => '${_labelize(entry.key)} ${entry.value}')
        .join(' / ');

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          'Editorial preferences',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        Text(
          'Keep each group at exactly 100 so the next bulletin can use your mix safely.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 20),
        _PreferenceSection(
          title: 'Geography',
          total: _geography.total,
          onReset: () {
            setState(() {
              _geography = GeographyPreferenceMix.defaults();
            });
          },
          children: [
            _buildSliderRow(
              label: 'Local',
              value: _geography.local,
              onChanged: (value) => setState(() {
                _geography = _geography.copyWith(local: value);
              }),
            ),
            _buildSliderRow(
              label: 'National',
              value: _geography.national,
              onChanged: (value) => setState(() {
                _geography = _geography.copyWith(national: value);
              }),
            ),
            _buildSliderRow(
              label: 'International',
              value: _geography.international,
              onChanged: (value) => setState(() {
                _geography = _geography.copyWith(international: value);
              }),
            ),
          ],
        ),
        const SizedBox(height: 16),
        _PreferenceSection(
          title: 'Domains',
          total: _domains.total,
          onReset: () {
            setState(() {
              _domains = DomainPreferenceMix.defaults();
            });
          },
          children: [
            _buildSliderRow(
              label: 'Politics',
              value: _domains.politics,
              onChanged: (value) => setState(() {
                _domains = _domains.copyWith(politics: value);
              }),
            ),
            _buildSliderRow(
              label: 'Economy',
              value: _domains.economy,
              onChanged: (value) => setState(() {
                _domains = _domains.copyWith(economy: value);
              }),
            ),
            _buildSliderRow(
              label: 'Sport',
              value: _domains.sport,
              onChanged: (value) => setState(() {
                _domains = _domains.copyWith(sport: value);
              }),
            ),
            _buildSliderRow(
              label: 'Entertainment',
              value: _domains.entertainment,
              onChanged: (value) => setState(() {
                _domains = _domains.copyWith(entertainment: value);
              }),
            ),
            _buildSliderRow(
              label: 'Education',
              value: _domains.education,
              onChanged: (value) => setState(() {
                _domains = _domains.copyWith(education: value);
              }),
            ),
            _buildSliderRow(
              label: 'Health',
              value: _domains.health,
              onChanged: (value) => setState(() {
                _domains = _domains.copyWith(health: value);
              }),
            ),
            _buildSliderRow(
              label: 'Tech',
              value: _domains.tech,
              onChanged: (value) => setState(() {
                _domains = _domains.copyWith(tech: value);
              }),
            ),
          ],
        ),
        const SizedBox(height: 16),
        if (!_isPreferencesValid)
          Text(
            'Both slider groups must total exactly 100 before you can finish.',
            style: TextStyle(
              color: Theme.of(context).colorScheme.error,
            ),
          ),
        const SizedBox(height: 20),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Review',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                Text(personalization.listenerProfile.firstName),
                Text(personalization.locationSummary),
                const SizedBox(height: 12),
                Text(
                  'Geography: ${_geography.local} / ${_geography.national} / ${_geography.international}',
                ),
                Text('Domains: $topDomains'),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSliderRow({
    required String label,
    required int value,
    required ValueChanged<int> onChanged,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label),
            Text('$value'),
          ],
        ),
        Slider(
          value: value.toDouble(),
          min: 0,
          max: 100,
          divisions: 20,
          label: '$value',
          onChanged: (next) => onChanged(next.round()),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final isLastStep = _currentStep == 1;

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.isOnboarding ? 'OpenWave setup' : 'Personalization'),
      ),
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 250),
        child: _currentStep == 0
            ? _buildProfileStep(context)
            : _buildPreferencesStep(context),
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
          child: Row(
            children: [
              if (_currentStep > 0)
                Expanded(
                  child: OutlinedButton(
                    onPressed: _isSaving
                        ? null
                        : () {
                            setState(() {
                              _currentStep--;
                            });
                          },
                    child: const Text('Back'),
                  ),
                ),
              if (_currentStep > 0) const SizedBox(width: 12),
              Expanded(
                child: FilledButton(
                  onPressed: _isSaving
                      ? null
                      : () {
                          if (!isLastStep) {
                            if (!_isProfileValid) {
                              setState(() {});
                              return;
                            }
                            setState(() {
                              _currentStep = 1;
                            });
                            return;
                          }
                          _save();
                        },
                  child: Text(_isSaving
                      ? 'Saving...'
                      : (isLastStep
                          ? (widget.isOnboarding ? 'Finish setup' : 'Save')
                          : 'Continue')),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PreferenceSection extends StatelessWidget {
  const _PreferenceSection({
    required this.title,
    required this.total,
    required this.children,
    required this.onReset,
  });

  final String title;
  final int total;
  final List<Widget> children;
  final VoidCallback onReset;

  @override
  Widget build(BuildContext context) {
    final totalColor = total == 100
        ? Theme.of(context).colorScheme.primary
        : Theme.of(context).colorScheme.error;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                TextButton(
                  onPressed: onReset,
                  child: const Text('Reset'),
                ),
              ],
            ),
            Text(
              'Total: $total / 100',
              style: TextStyle(color: totalColor),
            ),
            const SizedBox(height: 12),
            ...children,
          ],
        ),
      ),
    );
  }
}

String _labelize(String value) {
  switch (value) {
    case 'politics':
      return 'Politics';
    case 'economy':
      return 'Economy';
    case 'sport':
      return 'Sport';
    case 'entertainment':
      return 'Entertainment';
    case 'education':
      return 'Education';
    case 'health':
      return 'Health';
    case 'tech':
      return 'Tech';
  }
  return value;
}

const List<String> _countries = ['Romania'];

const List<String> _romanianCounties = [
  'Alba',
  'Arad',
  'Arges',
  'Bacau',
  'Bihor',
  'Bistrita-Nasaud',
  'Botosani',
  'Braila',
  'Brasov',
  'Bucuresti',
  'Buzau',
  'Calarasi',
  'Caras-Severin',
  'Cluj',
  'Constanta',
  'Covasna',
  'Dambovita',
  'Dolj',
  'Galati',
  'Giurgiu',
  'Gorj',
  'Harghita',
  'Hunedoara',
  'Ialomita',
  'Iasi',
  'Ilfov',
  'Maramures',
  'Mehedinti',
  'Mures',
  'Neamt',
  'Olt',
  'Prahova',
  'Satu Mare',
  'Salaj',
  'Sibiu',
  'Suceava',
  'Teleorman',
  'Timis',
  'Tulcea',
  'Valcea',
  'Vaslui',
  'Vrancea',
];
