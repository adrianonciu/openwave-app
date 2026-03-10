import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../models/daily_brief.dart';

class PlayerScreen extends StatefulWidget {
  final DailyBrief dailyBrief;

  const PlayerScreen({
    super.key,
    required this.dailyBrief,
  });

  @override
  State<PlayerScreen> createState() => _PlayerScreenState();
}

class _PlayerScreenState extends State<PlayerScreen> {
  int _currentIndex = 0;
  final FlutterTts _flutterTts = FlutterTts();
  bool _isPlaying = false;
  int _currentProgressSeconds = 0;
  int _currentArticleDurationSeconds = 0;
  Timer? _progressTimer;
  final ScrollController _playlistScrollController = ScrollController();
  final Map<int, GlobalKey> _playlistItemKeys = {};
  bool _isPlayingCue = false;
  bool _isPlayingIntro = false;
  int? _queuedPlaybackIndex;
  int _lastScrolledPlaylistIndex = -1;

  List<_PlaybackItem> get _playlistItems {
    final segments = widget.dailyBrief.segments;
    if (segments != null && segments.isNotEmpty) {
      return segments.map(_PlaybackItem.fromSegment).toList();
    }

    return widget.dailyBrief.articles
        .map(_PlaybackItem.fromArticle)
        .toList();
  }

  int get _storyCount {
    return _playlistItems.where((item) => !item.isSectionCue).length;
  }

  @override
  void initState() {
    super.initState();
    _flutterTts.setCompletionHandler(() {
      _handleTtsCompletion();
    });
    if (_playlistItems.isNotEmpty) {
      _resetProgressForCurrentArticle();
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        if (!mounted) return;
        setState(() {
          _isPlaying = true;
        });
        await _playIntroIfNeeded();
      });
    }
  }

  Future<void> _playIntroIfNeeded() async {
    final articleCount = _storyCount;
    final countWord = <int, String>{
          1: 'One',
          2: 'Two',
          3: 'Three',
          4: 'Four',
          5: 'Five',
          6: 'Six',
          7: 'Seven',
          8: 'Eight',
          9: 'Nine',
          10: 'Ten',
        }[articleCount] ??
        articleCount.toString();
    final storyLabel = articleCount == 1 ? 'story' : 'stories';

    final totalEstimatedSeconds = _estimateTotalBriefingDurationSeconds();
    final roundedMinutes = (totalEstimatedSeconds / 60).round();
    final safeMinutes = roundedMinutes < 1 ? 1 : roundedMinutes;
    final minuteWord = <int, String>{
          1: 'one',
          2: 'two',
          3: 'three',
          4: 'four',
          5: 'five',
          6: 'six',
          7: 'seven',
          8: 'eight',
          9: 'nine',
          10: 'ten',
        }[safeMinutes] ??
        safeMinutes.toString();
    final minuteLabel = safeMinutes == 1 ? 'minute' : 'minutes';

    _isPlayingIntro = true;
    await _flutterTts.speak(
      'Your OpenWave Daily Brief. $countWord $storyLabel today. About $minuteWord $minuteLabel.',
    );
  }

  Future<void> _handleTtsCompletion() async {
    if (!_isPlaying) return;

    if (_isPlayingIntro) {
      _isPlayingIntro = false;
      final firstEditorialIndex = _findFirstEditorialIndex();
      if (firstEditorialIndex == null) {
        _stopProgressTimer();
        await _flutterTts.stop();
        if (!mounted) return;
        setState(() {
          _isPlaying = false;
        });
        return;
      }

      _queuedPlaybackIndex = firstEditorialIndex;
      _isPlayingCue = true;
      await _flutterTts.speak('Top story.');
      return;
    }

    if (_isPlayingCue) {
      _isPlayingCue = false;
      final queuedPlaybackIndex = _queuedPlaybackIndex;
      _queuedPlaybackIndex = null;
      if (queuedPlaybackIndex == null) {
        await _playCurrentArticle();
        return;
      }

      _moveToIndex(queuedPlaybackIndex);
      await _playCurrentArticle();
      return;
    }

    final nextIndex = _currentIndex + 1;
    final hasNext = nextIndex < _playlistItems.length;
    if (hasNext) {
      _stopProgressTimer();
      if (_shouldUseNextStoryCue(_currentIndex, nextIndex)) {
        _queuedPlaybackIndex = nextIndex;
        _isPlayingCue = true;
        await _flutterTts.speak('Next story.');
        return;
      }

      _moveToIndex(nextIndex);
      await _playCurrentArticle();
      return;
    }

    _stopProgressTimer();
    _isPlayingCue = false;
    _queuedPlaybackIndex = null;
    await _flutterTts.stop();
    if (!mounted) return;
    setState(() {
      _isPlaying = false;
      _currentProgressSeconds = _currentArticleDurationSeconds;
    });
  }

  String _buildNarrationText(_PlaybackItem item) {
    if (item.narrationText.trim().isNotEmpty) {
      return item.narrationText;
    }

    return '${item.title}. ${item.summary}';
  }

  int _estimateTotalBriefingDurationSeconds() {
    return _playlistItems
        .map((item) => _estimateDurationSeconds(_buildNarrationText(item)))
        .fold(0, (sum, duration) => sum + duration);
  }

  int _estimateDurationSeconds(String text) {
    final words = text
        .trim()
        .split(RegExp(r'\s+'))
        .where((word) => word.isNotEmpty)
        .length;
    if (words == 0) return 0;

    return ((words / 170) * 60).ceil();
  }

  String _playlistTypeSubtitle(_PlaybackItem item) {
    if (item.type == 'intro') return 'Briefing intro';
    if (item.type == 'section_cue') return 'Section';
    if (item.type == 'perspective') return 'Perspective';
    return '';
  }

  IconData _playlistTypeIcon(_PlaybackItem item) {
    if (item.type == 'intro') return Icons.wb_sunny;
    if (item.type == 'section_cue') return Icons.radio;
    if (item.type == 'perspective') return Icons.balance;
    return Icons.play_arrow;
  }

  String _buildPlaylistSubtitle(
    _PlaybackItem item,
    bool isNext,
    String durationLabel,
  ) {
    if (item.isArticle) {
      final sourceAndDuration = '${item.source} \u2022 $durationLabel';
      return isNext ? 'Next: $sourceAndDuration' : sourceAndDuration;
    }

    final typeSubtitle = _playlistTypeSubtitle(item);
    return isNext ? 'Next: $typeSubtitle' : typeSubtitle;
  }

  String _buildActivePlaylistMeta(_PlaybackItem item, String durationLabel) {
    if (item.isArticle) {
      return '${item.source} \u2022 $durationLabel';
    }

    return _playlistTypeSubtitle(item);
  }

  bool _isPerspectivePairStart(List<_PlaybackItem> items, int index) {
    if (index < 0 || index >= items.length - 1) {
      return false;
    }

    return items[index].isPerspective && items[index + 1].isPerspective;
  }

  int? _articlePerspectiveStartIndex(List<_PlaybackItem> items, int index) {
    if (index < 0 || index >= items.length) {
      return null;
    }

    final item = items[index];
    if (!item.isArticle) {
      return null;
    }

    if (index > items.length - 3) {
      return null;
    }

    if (items[index + 1].isPerspective && items[index + 2].isPerspective) {
      return index + 1;
    }

    if (index <= items.length - 4 &&
        items[index + 1].isSectionCue &&
        items[index + 2].isPerspective &&
        items[index + 3].isPerspective) {
      return index + 2;
    }

    return null;
  }

  bool _isArticlePerspectiveBlockStart(List<_PlaybackItem> items, int index) {
    return _articlePerspectiveStartIndex(items, index) != null;
  }

  int? _articlePerspectiveBlockAnchorIndex(List<_PlaybackItem> items, int index) {
    if (index < 0 || index >= items.length) {
      return null;
    }

    for (var offset = 0; offset <= 3; offset++) {
      final candidateIndex = index - offset;
      if (candidateIndex < 0 || candidateIndex >= items.length) {
        continue;
      }

      final perspectiveStartIndex = _articlePerspectiveStartIndex(items, candidateIndex);
      if (perspectiveStartIndex == null) {
        continue;
      }

      final lastBlockIndex = perspectiveStartIndex + 1;
      if (index >= candidateIndex && index <= lastBlockIndex) {
        return candidateIndex;
      }
    }

    return null;
  }

  bool _isPerspectivePairMember(List<_PlaybackItem> items, int index) {
    if (index < 0 || index >= items.length) {
      return false;
    }

    final item = items[index];
    if (!item.isPerspective) {
      return false;
    }

    final hasPreviousPerspective = index > 0 && items[index - 1].isPerspective;
    final hasNextPerspective = index < items.length - 1 && items[index + 1].isPerspective;
    return hasPreviousPerspective || hasNextPerspective;
  }

  int _playlistAnchorIndex(List<_PlaybackItem> items, int index) {
    final articleBlockAnchorIndex = _articlePerspectiveBlockAnchorIndex(items, index);
    if (articleBlockAnchorIndex != null) {
      return articleBlockAnchorIndex;
    }

    if (index <= 0 || index >= items.length) {
      return index;
    }

    if (items[index].isPerspective && items[index - 1].isPerspective) {
      return index - 1;
    }

    return index;
  }

  int _visiblePlaylistNumber(List<_PlaybackItem> items, int anchorIndex) {
    var visibleNumber = 0;

    for (var index = 0; index <= anchorIndex && index < items.length; index++) {
      if (_playlistAnchorIndex(items, index) == index) {
        visibleNumber++;
      }
    }

    return visibleNumber;
  }

  int? _nextPlaylistIndex(List<_PlaybackItem> items) {
    final activeAnchorIndex = _playlistAnchorIndex(items, _currentIndex);
    for (var nextIndex = _currentIndex + 1; nextIndex < items.length; nextIndex++) {
      final visibleAnchorIndex = _playlistAnchorIndex(items, nextIndex);
      if (visibleAnchorIndex != activeAnchorIndex) {
        return visibleAnchorIndex;
      }
    }

    return null;
  }

  GlobalKey _playlistItemKey(int index) {
    return _playlistItemKeys.putIfAbsent(index, GlobalKey.new);
  }

  double _estimatedPlaylistOffset(List<_PlaybackItem> items, int targetIndex) {
    var offset = 0.0;
    for (var index = 0; index < targetIndex; index++) {
      if (_articlePerspectiveBlockAnchorIndex(items, index) case final anchorIndex?
          when anchorIndex != index) {
        continue;
      }

      if (items[index].isPerspective && index > 0 && items[index - 1].isPerspective) {
        continue;
      }

      offset += _isArticlePerspectiveBlockStart(items, index)
          ? 296
          : (_isPerspectivePairStart(items, index) ? 208 : 96);
    }

    return offset;
  }

  void _scrollPlaylistToIndex(List<_PlaybackItem> items, int visibleIndex) {
    if (!_playlistScrollController.hasClients || visibleIndex < 0) {
      return;
    }

    final targetContext = _playlistItemKeys[visibleIndex]?.currentContext;
    if (targetContext != null) {
      Scrollable.ensureVisible(
        targetContext,
        alignment: 0,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOutCubic,
      );
      return;
    }

    final targetOffset = _estimatedPlaylistOffset(items, visibleIndex);
    final clampedOffset = targetOffset.clamp(
      0.0,
      _playlistScrollController.position.maxScrollExtent,
    );
    _playlistScrollController.animateTo(
      clampedOffset,
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOutCubic,
    );
  }

  void _schedulePlaylistSync(List<_PlaybackItem> items, int visibleIndex) {
    if (visibleIndex < 0 || visibleIndex == _lastScrolledPlaylistIndex) {
      return;
    }

    _lastScrolledPlaylistIndex = visibleIndex;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _scrollPlaylistToIndex(items, visibleIndex);
    });
  }

  int? _findFirstEditorialIndex() {
    for (var index = 0; index < _playlistItems.length; index++) {
      final item = _playlistItems[index];
      if (item.type != 'intro' && !item.isSectionCue) {
        return index;
      }
    }

    return null;
  }

  bool _shouldUseNextStoryCue(int currentIndex, int nextIndex) {
    final currentItem = _playlistItems[currentIndex];
    final nextItem = _playlistItems[nextIndex];
    return nextItem.isArticle && !currentItem.isPerspective;
  }

  void _moveToIndex(int index) {
    setState(() {
      _currentIndex = index;
      _resetProgressForCurrentArticle();
    });
  }

  String _formatDuration(int seconds) {
    final safeSeconds = seconds < 0 ? 0 : seconds;
    final minutes = safeSeconds ~/ 60;
    final remainingSeconds = safeSeconds % 60;
    final paddedSeconds = remainingSeconds.toString().padLeft(2, '0');

    return '$minutes:$paddedSeconds';
  }

  void _resetProgressForCurrentArticle() {
    final items = _playlistItems;
    if (items.isEmpty) {
      _currentProgressSeconds = 0;
      _currentArticleDurationSeconds = 0;
      return;
    }

    final text = _buildNarrationText(items[_currentIndex]);
    _currentProgressSeconds = 0;
    _currentArticleDurationSeconds = _estimateDurationSeconds(text);
  }

  void _startProgressTimer() {
    _stopProgressTimer();
    if (_currentArticleDurationSeconds <= 0) return;

    _progressTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }

      setState(() {
        if (_currentProgressSeconds < _currentArticleDurationSeconds) {
          _currentProgressSeconds++;
        } else {
          timer.cancel();
        }
      });
    });
  }

  void _stopProgressTimer() {
    _progressTimer?.cancel();
    _progressTimer = null;
  }

  Future<void> _selectArticle(int index) async {
    setState(() {
      _currentIndex = index;
      _resetProgressForCurrentArticle();
    });

    if (_isPlaying) {
      await _flutterTts.stop();
      await _playCurrentArticle();
    }
  }

  Future<void> _playPrevious() async {
    if (_currentIndex == 0) return;

    setState(() {
      _currentIndex--;
      _resetProgressForCurrentArticle();
    });

    if (_isPlaying) {
      await _flutterTts.stop();
      await _playCurrentArticle();
    }
  }

  Future<void> _playNext() async {
    if (_currentIndex >= _playlistItems.length - 1) return;

    setState(() {
      _currentIndex++;
      _resetProgressForCurrentArticle();
    });

    if (_isPlaying) {
      await _flutterTts.stop();
      await _playCurrentArticle();
    }
  }

  Future<void> _playCurrentArticle() async {
    final items = _playlistItems;
    if (items.isEmpty) return;

    final item = items[_currentIndex];
    final text = _buildNarrationText(item);

    if (text.trim().isEmpty) return;

    setState(() {
      _currentProgressSeconds = 0;
      _currentArticleDurationSeconds = _estimateDurationSeconds(text);
    });
    _startProgressTimer();

    await _flutterTts.speak(text);
  }

  Future<void> _togglePlayback() async {
    if (_isPlaying) {
      _isPlayingCue = false;
      _isPlayingIntro = false;
      _stopProgressTimer();
      await _flutterTts.stop();
      setState(() {
        _isPlaying = false;
      });
      return;
    }

    setState(() {
      _isPlaying = true;
    });
    await _playCurrentArticle();
  }

  @override
  void dispose() {
    _stopProgressTimer();
    _playlistScrollController.dispose();
    _flutterTts.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final items = _playlistItems;
    final totalEstimatedBriefingSeconds = _estimateTotalBriefingDurationSeconds();
    final nowPlaying = items.isNotEmpty ? items[_currentIndex] : null;
    final narrationText = nowPlaying != null ? _buildNarrationText(nowPlaying) : '';
    final activePlaylistIndex = items.isNotEmpty
        ? _playlistAnchorIndex(items, _currentIndex)
        : -1;
    final nextPlaylistIndex = _nextPlaylistIndex(items);
    final nextItem = _currentIndex < items.length - 1 ? items[_currentIndex + 1] : null;
    if (items.isNotEmpty) {
      _schedulePlaylistSync(items, activePlaylistIndex);
    } else {
      _lastScrolledPlaylistIndex = -1;
    }
    final estimatedDurationLabel = _currentArticleDurationSeconds >= 60
        ? '${(_currentArticleDurationSeconds / 60).round()} min'
        : '$_currentArticleDurationSeconds sec';
    final showPerspectivePairIndicator =
        nowPlaying != null &&
        (_isPerspectivePairMember(items, _currentIndex) ||
            _articlePerspectiveBlockAnchorIndex(items, _currentIndex) != null);
    final progressValue = _currentArticleDurationSeconds > 0
        ? (_currentProgressSeconds / _currentArticleDurationSeconds)
            .clamp(0.0, 1.0)
            .toDouble()
        : 0.0;
    final remainingSeconds =
        (_currentArticleDurationSeconds - _currentProgressSeconds)
            .clamp(0, _currentArticleDurationSeconds);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Daily Brief Player'),
      ),
      body: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.dailyBrief.headline,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 4),
            Text(
              'Estimated duration: ${_formatDuration(totalEstimatedBriefingSeconds)}',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 4),
            Text(
              '${_storyCount} stories',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 12),
            if (nowPlaying != null) ...[
              Text(
                'Now Playing',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 6),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (showPerspectivePairIndicator) ...[
                        Text(
                          '\u2696\uFE0F Two perspectives',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const SizedBox(height: 6),
                      ],
                      Text(
                        nowPlaying.title,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        nowPlaying.source,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        nowPlaying.summary,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                      if (narrationText.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Text(
                          'Audio narration ready',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                      const SizedBox(height: 8),
                      Text(
                        estimatedDurationLabel,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 12),
                      LinearProgressIndicator(
                        value: progressValue,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${_formatDuration(_currentProgressSeconds)} / ${_formatDuration(_currentArticleDurationSeconds)}  \u2022  -${_formatDuration(remainingSeconds)}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          IconButton(
                            onPressed: _playPrevious,
                            icon: const Icon(Icons.skip_previous),
                          ),
                          const SizedBox(width: 12),
                          IconButton(
                            onPressed: _togglePlayback,
                            iconSize: 40,
                            icon: Icon(
                              _isPlaying
                                  ? Icons.pause_circle_filled
                                  : Icons.play_circle_filled,
                            ),
                          ),
                          const SizedBox(width: 12),
                          IconButton(
                            onPressed: _playNext,
                            icon: const Icon(Icons.skip_next),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              if (nextItem != null) ...[
                const SizedBox(height: 8),
                Text(
                  'Up next: ${nextItem.title}',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ],
              const SizedBox(height: 12),
            ],
            Text(
              'Playlist',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Expanded(
              child: ListView.builder(
                controller: _playlistScrollController,
                itemCount: items.length,
                itemBuilder: (context, index) {
                  final item = items[index];
                  final articlePerspectiveBlockAnchorIndex =
                      _articlePerspectiveBlockAnchorIndex(items, index);
                  final previousItem = index > 0 ? items[index - 1] : null;
                  final nextPerspectiveItem =
                      index < items.length - 1 ? items[index + 1] : null;
                  final isPerspectivePairStart =
                      _isPerspectivePairStart(items, index);

                  if (articlePerspectiveBlockAnchorIndex != null &&
                      articlePerspectiveBlockAnchorIndex != index) {
                    return const SizedBox.shrink();
                  }

                  if (item.isPerspective && previousItem?.isPerspective == true) {
                    return const SizedBox.shrink();
                  }

                  final isActive = activePlaylistIndex == index;
                  final isNext = !isActive && nextPlaylistIndex == index;
                  final visiblePlaylistNumber =
                      _visiblePlaylistNumber(items, index);

                  final articlePerspectiveStartIndex =
                      _articlePerspectiveStartIndex(items, index);
                  if (articlePerspectiveStartIndex != null) {
                    return KeyedSubtree(
                      key: _playlistItemKey(index),
                      child: _StoryPerspectiveBlockTile(
                        article: item,
                        supporters: items[articlePerspectiveStartIndex],
                        critics: items[articlePerspectiveStartIndex + 1],
                        visibleNumber: visiblePlaylistNumber,
                        isActive: isActive,
                        isNext: isNext,
                        progressValue: isActive ? progressValue : 0,
                        onTap: () => _selectArticle(index),
                      ),
                    );
                  }

                  if (isPerspectivePairStart && nextPerspectiveItem != null) {
                    return KeyedSubtree(
                      key: _playlistItemKey(index),
                      child: _PerspectivePairTile(
                        first: item,
                        second: nextPerspectiveItem,
                        visibleNumber: visiblePlaylistNumber,
                        isActive: isActive,
                        isNext: isNext,
                        progressValue: isActive ? progressValue : 0,
                        onTap: () => _selectArticle(index),
                      ),
                    );
                  }

                  final playlistNarrationText = _buildNarrationText(item);
                  final playlistDurationSeconds =
                      _estimateDurationSeconds(playlistNarrationText);
                  final playlistDurationLabel = playlistDurationSeconds >= 60
                      ? '${(playlistDurationSeconds / 60).round()} min'
                      : '$playlistDurationSeconds sec';

                  return KeyedSubtree(
                    key: _playlistItemKey(index),
                    child: Card(
                      color: isActive
                          ? Theme.of(context).colorScheme.primaryContainer
                          : null,
                      shape: RoundedRectangleBorder(
                        side: BorderSide(
                          color: isActive
                              ? Theme.of(context).colorScheme.primary
                              : Colors.transparent,
                          width: isActive ? 2 : 0,
                        ),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: ListTile(
                        onTap: () => _selectArticle(index),
                        leading: CircleAvatar(
                          child: Text('$visiblePlaylistNumber'),
                        ),
                        title: Text(
                          item.title,
                          style: isActive
                              ? Theme.of(context).textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.w600,
                                )
                              : null,
                        ),
                        subtitle: isActive
                            ? Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(
                                    _buildActivePlaylistMeta(
                                      item,
                                      playlistDurationLabel,
                                    ),
                                  ),
                                  Text(
                                    'Playing now',
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodySmall
                                        ?.copyWith(
                                          fontWeight: FontWeight.w600,
                                        ),
                                  ),
                                  const SizedBox(height: 8),
                                  LinearProgressIndicator(
                                    value: progressValue,
                                    minHeight: 3,
                                  ),
                                ],
                              )
                            : Text(
                                _buildPlaylistSubtitle(
                                  item,
                                  isNext,
                                  playlistDurationLabel,
                                ),
                              ),
                        trailing: Icon(
                          isActive
                              ? Icons.graphic_eq
                              : (item.isArticle
                                  ? (isNext
                                      ? Icons.arrow_forward
                                      : Icons.play_arrow)
                                  : _playlistTypeIcon(item)),
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PlaybackItem {
  final String type;
  final String title;
  final String source;
  final String summary;
  final String narrationText;

  const _PlaybackItem({
    required this.type,
    required this.title,
    required this.source,
    required this.summary,
    required this.narrationText,
  });

  bool get isSectionCue => type == 'section_cue';
  bool get isArticle => type == 'article' || type == 'news';
  bool get isPerspective => type == 'perspective';

  factory _PlaybackItem.fromArticle(DailyBriefArticle article) {
    return _PlaybackItem(
      type: 'article',
      title: article.title,
      source: article.source,
      summary: article.summary,
      narrationText: '${article.title}. ${article.summary}',
    );
  }

  factory _PlaybackItem.fromSegment(DailyBriefSegment segment) {
    final fallbackNarration = '${segment.title}. ${segment.summary}';
    return _PlaybackItem(
      type: segment.type,
      title: segment.title,
      source: segment.source,
      summary: segment.summary,
      narrationText: segment.narrationText.trim().isEmpty
          ? fallbackNarration
          : segment.narrationText,
    );
  }
}

class _StoryPerspectiveBlockTile extends StatelessWidget {
  final _PlaybackItem article;
  final _PlaybackItem supporters;
  final _PlaybackItem critics;
  final int visibleNumber;
  final bool isActive;
  final bool isNext;
  final double progressValue;
  final VoidCallback onTap;

  const _StoryPerspectiveBlockTile({
    required this.article,
    required this.supporters,
    required this.critics,
    required this.visibleNumber,
    required this.isActive,
    required this.isNext,
    required this.progressValue,
    required this.onTap,
  });

  String _previewText(_PlaybackItem item) {
    final preview = item.summary.trim().isNotEmpty ? item.summary : item.title;
    return preview.trim();
  }

  Widget _buildPerspectiveRow(
    BuildContext context, {
    required String label,
    required _PlaybackItem item,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
        ),
        const SizedBox(height: 4),
        Text(
          _previewText(item),
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final editorialAccent = isActive
        ? colorScheme.primary.withValues(alpha: 0.14)
        : colorScheme.surfaceContainerHighest.withValues(alpha: 0.55);
    final editorialBorderColor = isActive
        ? colorScheme.primary.withValues(alpha: 0.35)
        : colorScheme.outlineVariant.withValues(alpha: 0.8);

    return Card(
      color: isActive ? colorScheme.primaryContainer : null,
      shape: RoundedRectangleBorder(
        side: BorderSide(
          color: isActive ? colorScheme.primary : Colors.transparent,
          width: isActive ? 2 : 0,
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                child: Text('$visibleNumber'),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                article.title,
                                style: Theme.of(context)
                                    .textTheme
                                    .titleMedium
                                    ?.copyWith(fontWeight: FontWeight.w700),
                              ),
                              const SizedBox(height: 6),
                              Text(
                                article.source,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 12),
                        Icon(
                          isActive
                              ? Icons.graphic_eq
                              : (isNext
                                  ? Icons.arrow_forward
                                  : Icons.play_arrow),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      _previewText(article),
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 14),
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: editorialAccent,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(color: editorialBorderColor),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 6,
                            ),
                            decoration: BoxDecoration(
                              color: colorScheme.surface.withValues(alpha: 0.75),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Text(
                              '\u2696\uFE0F Two perspectives',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleSmall
                                  ?.copyWith(fontWeight: FontWeight.w700),
                            ),
                          ),
                          const SizedBox(height: 14),
                          _buildPerspectiveRow(
                            context,
                            label: 'Supporters say',
                            item: supporters,
                          ),
                          const SizedBox(height: 12),
                          Divider(
                            height: 1,
                            thickness: 1,
                            color: colorScheme.outlineVariant.withValues(alpha: 0.7),
                          ),
                          const SizedBox(height: 12),
                          _buildPerspectiveRow(
                            context,
                            label: 'Critics argue',
                            item: critics,
                          ),
                        ],
                      ),
                    ),
                    if (isActive) ...[
                      const SizedBox(height: 12),
                      LinearProgressIndicator(
                        value: progressValue,
                        minHeight: 3,
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PerspectivePairTile extends StatelessWidget {
  final _PlaybackItem first;
  final _PlaybackItem second;
  final int visibleNumber;
  final bool isActive;
  final bool isNext;
  final double progressValue;
  final VoidCallback onTap;

  const _PerspectivePairTile({
    required this.first,
    required this.second,
    required this.visibleNumber,
    required this.isActive,
    required this.isNext,
    required this.progressValue,
    required this.onTap,
  });

  String _previewText(_PlaybackItem item) {
    final preview = item.summary.trim().isNotEmpty ? item.summary : item.title;
    return preview.trim();
  }

  Widget _buildPerspectiveRow(
    BuildContext context, {
    required String label,
    required _PlaybackItem item,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
        ),
        const SizedBox(height: 4),
        Text(
          _previewText(item),
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final pairAccent = isActive
        ? colorScheme.primary.withValues(alpha: 0.14)
        : colorScheme.surfaceContainerHighest.withValues(alpha: 0.55);
    final pairBorderColor = isActive
        ? colorScheme.primary.withValues(alpha: 0.35)
        : colorScheme.outlineVariant.withValues(alpha: 0.8);

    return Card(
      color: isActive
          ? colorScheme.primaryContainer
          : null,
      shape: RoundedRectangleBorder(
        side: BorderSide(
          color: isActive
              ? colorScheme.primary
              : Colors.transparent,
          width: isActive ? 2 : 0,
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                child: Text('$visibleNumber'),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: pairAccent,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: pairBorderColor),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 6,
                            ),
                            decoration: BoxDecoration(
                              color: colorScheme.surface.withValues(alpha: 0.75),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Text(
                              '⚖️ Two perspectives',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleSmall
                                  ?.copyWith(fontWeight: FontWeight.w700),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Icon(
                            isActive
                                ? Icons.graphic_eq
                                : (isNext
                                    ? Icons.arrow_forward
                                    : Icons.play_arrow),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      _buildPerspectiveRow(
                        context,
                        label: 'Supporters say',
                        item: first,
                      ),
                      const SizedBox(height: 12),
                      Divider(
                        height: 1,
                        thickness: 1,
                        color: colorScheme.outlineVariant.withValues(alpha: 0.7),
                      ),
                      const SizedBox(height: 12),
                      _buildPerspectiveRow(
                        context,
                        label: 'Critics argue',
                        item: second,
                      ),
                      if (isActive) ...[
                        const SizedBox(height: 12),
                        LinearProgressIndicator(
                          value: progressValue,
                          minHeight: 3,
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

