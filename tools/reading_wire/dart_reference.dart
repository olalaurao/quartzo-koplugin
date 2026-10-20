import 'dart:convert';
import 'package:quartzo/models/reading_activity_event.dart';

void main() {
  final cases = <Map<String, Object?>>[];
  for (final started in [
    '0001-01-01T00:00:00.000Z',
    '1969-12-31T23:59:59.000Z',
    '2000-02-29T12:00:00.000Z',
    '2100-02-28T12:00:00.000Z',
    '9999-12-31T23:59:59.000Z',
  ]) {
    final event = ReadingActivityEvent(
      deviceId: 'qrd_fixture', sourceEpoch: 'db_epoch_fixture',
      bookRowId: 9007199254740991, page: 9007199254740991,
      totalPages: 9007199254740991, durationSeconds: 1800,
      startedAt: DateTime.parse(started),
      observedAt: DateTime.parse('9999-12-31T23:59:59.123456Z'),
      sourceSchemaVersion: started.startsWith('2000')
          ? 'fixture-水😀\b\f\t\u0001\u2028\u2029/' : 'fixture-水😀',
    );
    cases.add({'line': jsonEncode(event.toMap()), 'native_payload': event.nativePayload});
  }
  print(jsonEncode({'cases': cases, 'unicode_blank_rejected': '\u00a0\u2007\ufeff'.trim().isEmpty,
    'escaped': jsonEncode('á水😀\b\f\t\u0001\u2028\u2029/')}));
}
