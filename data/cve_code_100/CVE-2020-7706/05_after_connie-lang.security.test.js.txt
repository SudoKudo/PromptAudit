var assert = require('assert');
var ConnieLang = require('../');

describe('ConnieLang', function () {
  it('should not allow prototype pollution at the top level', function () {
    var obj = Object.create(null);
    obj['__proto__'] = { polluted: true };
    var config = ConnieLang.parse(obj);
    assert.deepEqual(config, {});
    assert.equal(Object.polluted, undefined);
  });

  it('should not allow prototype pollution at a nested level', function () {
    var obj = Object.create(null);
    obj['__proto__'] = { polluted: true };
    var config = ConnieLang.parse({ foo: obj });
    assert.deepEqual(config, {});
    assert.equal(Object.polluted, undefined);
  });
});
