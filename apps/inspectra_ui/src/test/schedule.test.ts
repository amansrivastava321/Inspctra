import { describe, expect, it } from 'vitest';
import {
  buildSchedule,
  describeSchedule,
  isNotScheduled,
  isSupportedSchedule,
  parseSchedule,
  validateInterval,
} from '../config/schedule';

describe('schedule strings', () => {
  it.each([
    ['every_15m', { kind: 'minutes', every: 15 }],
    ['every_6h', { kind: 'hours', every: 6 }],
    ['hourly', { kind: 'hourly', every: 1 }],
    ['daily', { kind: 'daily', every: 1 }],
    ['nightly', { kind: 'daily', every: 1 }],
    ['weekdays', { kind: 'weekdays', every: 1 }],
    ['none', { kind: 'none', every: 15 }],
    [undefined, { kind: 'none', every: 15 }],
  ])('parses %s', (schedule, expected) => {
    expect(parseSchedule(schedule)).toEqual(expected);
  });

  it.each(['every_15m', 'every_6h', 'hourly', 'daily', 'weekdays'])('round-trips %s', (schedule) => {
    expect(buildSchedule(parseSchedule(schedule))).toBe(schedule);
  });

  it('saves nightly as the identical daily schedule', () => {
    expect(buildSchedule(parseSchedule('nightly'))).toBe('daily');
  });

  it.each([
    ['every_5m', true], ['every_720m', true], ['every_1h', true], ['every_168h', true], ['hourly', true],
    ['every_4m', false], ['every_721m', false], ['every_169h', false], ['on PR', false], ['weekdays 09:00', false],
    ['none', false], ['manual', false], [undefined, false],
  ])('knows whether %s is runnable', (schedule, supported) => {
    expect(isSupportedSchedule(schedule)).toBe(supported);
  });

  it.each(['', 'none', 'manual', 'on_demand', undefined])('treats %s as not scheduled', (schedule) => {
    expect(isNotScheduled(schedule)).toBe(true);
  });

  it('flags an interval outside the limits and accepts one inside them', () => {
    expect(validateInterval({ kind: 'minutes', every: 4 })).toMatch(/5 to 720/);
    expect(validateInterval({ kind: 'minutes', every: 721 })).not.toBeNull();
    expect(validateInterval({ kind: 'hours', every: 0 })).toMatch(/1 to 168/);
    expect(validateInterval({ kind: 'minutes', every: 2.5 })).not.toBeNull();
    expect(validateInterval({ kind: 'minutes', every: NaN })).not.toBeNull();
    expect(validateInterval({ kind: 'minutes', every: 15 })).toBeNull();
    expect(validateInterval({ kind: 'daily', every: 1 })).toBeNull();
  });

  it('describes schedules in plain words', () => {
    expect(describeSchedule('every_15m')).toBe('Every 15 minutes');
    expect(describeSchedule('every_1h')).toBe('Every hour');
    expect(describeSchedule('every_6h')).toBe('Every 6 hours');
    expect(describeSchedule('hourly')).toBe('Every hour');
    expect(describeSchedule('daily', 'Asia/Kolkata')).toBe('Every day at 02:00 (Asia/Kolkata)');
    expect(describeSchedule('weekdays')).toBe('Weekdays at 09:00 (UTC)');
    expect(describeSchedule('none')).toBe('Not scheduled');
    expect(describeSchedule(undefined)).toBe('Not scheduled');
  });
});
