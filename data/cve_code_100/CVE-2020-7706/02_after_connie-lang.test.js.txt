var assert = require('assert');
var ConnieLang = require('../');

describe('ConnieLang', function () {
  describe('getEntries', function () {
    it('should return entries for nested objects', function () {
      var entries = ConnieLang.getEntries({
        foo: 'bar',
        bar: {
          baz: {
            a: {
              b: 'c',
              c: 'd',
              d: ['e', 'f', 'g'],
            },
          },
        },
      });

      assert.deepEqual(entries, [
        { key: ['foo'], value: 'bar' },
        { key: ['bar', 'baz', 'a', 'b'], value: 'c' },
        { key: ['bar', 'baz', 'a', 'c'], value: 'd' },
        { key: ['bar', 'baz', 'a', 'd', 0], value: 'e' },
        { key: ['bar', 'baz', 'a', 'd', 1], value: 'f' },
        { key: ['bar', 'baz', 'a', 'd', 2], value: 'g' },
      ]);
    });

    it('should return entries for an array', function () {
      var entries = ConnieLang.getEntries(['foo', { bar: 'baz' }]);

      assert.deepEqual(entries, [
        { key: [0], value: 'foo' },
        { key: [1, 'bar'], value: 'baz' },
      ]);
    });

    it('filters out entries that have __proto__ in the key path', function () {
      var obj = Object.create(null);
      obj['__proto__'] = { polluted: true };
      var entries = ConnieLang.getEntries(obj);
      assert.deepEqual(entries, []);
    });

    it('filters out entries that have __proto__ in the deep key path', function () {
      var obj = Object.create(null);
      obj['__proto__'] = { polluted: true };
      var entries = ConnieLang.getEntries({ foo: obj });
      assert.deepEqual(entries, []);
    });

    it('filters out entries that have constructor in the key path', function () {
      var entries = ConnieLang.getEntries({ constructor: { polluted: true } });
      assert.deepEqual(entries, []);
    });

    it('filters out entries that have constructor in the deep key path', function () {
      var entries = ConnieLang.getEntries({ foo: { constructor: { polluted: true } } });
      assert.deepEqual(entries, []);
    });
  });

  describe('firstInnermostInterpreterFromValue', function () {
    it('should return null when no interpreters are found', function () {
      var interpreter = ConnieLang.firstInnermostInterpreterFromValue('foobar');
      assert.equal(interpreter, null);
    });

    it('should handle complex values', function () {
      var value = '${FOO_${PORT}} @{foo.bar}';

      var interpreter = ConnieLang.firstInnermostInterpreterFromValue(value);
      assert.equal(interpreter.type, '$');
      assert.equal(interpreter.match, '${PORT}');
      assert.equal(interpreter.value, 'PORT');
      assert.equal(interpreter.start, 6);
      assert.equal(interpreter.end, 13);
    });
  });

  describe('parse', function () {
    it('should parse environment variables correctly', function () {
      var config = ConnieLang.parse(
        {
          a: 'PORT',
          b: {
            c: {
              d: 'e',
              e: '${@{a}}',
            },
          },
        },
        {
          PORT: '3000',
        }
      );

      assert.deepEqual(config, {
        a: 'PORT',
        b: {
          c: {
            d: 'e',
            e: '3000',
          },
        },
      });
    });

    it('should parse inside of arrays', function () {
      var config = ConnieLang.parse(
        {
          bar: 'hey',
          arr: [{ foo: '@{bar}' }, { bar: '${FOOBAR:4}' }, '${PORT}'],
        },
        {
          PORT: '3000',
        }
      );

      assert.deepEqual(config, {
        bar: 'hey',
        arr: [{ foo: 'hey' }, { bar: 4 }, '3000'],
      });
    });

    it('should parse env inside of env', function () {
      var config = ConnieLang.parse(
        {
          a: '${FOO_${BAR}}',
          b: '${FOO_${BAZ}}',
        },
        {
          BAR: 'BAR',
          BAZ: 'BAZ',
          FOO_BAR: 'hello',
          FOO_BAZ: 'world',
        }
      );

      assert.deepEqual(config, {
        a: 'hello',
        b: 'world',
      });
    });

    it('should ignore null and undefined values', function () {
      var config = ConnieLang.parse({
        a: {
          b: ['foo', null, 4],
        },
        b: undefined,
      });

      assert.deepEqual(config, {
        a: {
          b: ['foo', null, 4],
        },
        b: undefined,
      });
    });

    it('should substitute a missing env var with an empty string', function () {
      var config = ConnieLang.parse({
        foo: '${HELLO}',
      });

      assert.deepEqual(config, {
        foo: '',
      });
    });

    it('should substitute a default value when env var does not exist', function () {
      var config = ConnieLang.parse({
        foo: '${HELLO:default}',
      });

      assert.deepEqual(config, {
        foo: 'default',
      });
    });

    it('should substitute a default value when ref does not exist', function () {
      var config = ConnieLang.parse({
        foo: '@{bar:default}',
      });

      assert.deepEqual(config, {
        foo: 'default',
      });
    });
  });
});
