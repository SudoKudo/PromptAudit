from django.core import checks
from django.test import SimpleTestCase
from django.test.utils import override_settings

from anymail.checks import check_deprecated_settings

from .utils import AnymailTestMixin


class DeprecatedSettingsTests(SimpleTestCase, AnymailTestMixin):
    @override_settings(ANYMAIL={"WEBHOOK_AUTHORIZATION": "abcde:12345"})
    def test_webhook_authorization(self):
        errors = check_deprecated_settings(None)
        self.assertEqual(errors, [checks.Warning(
            "The ANYMAIL setting 'WEBHOOK_AUTHORIZATION' has been renamed 'WEBHOOK_SECRET' to improve security.",
            hint="You must update your settings.py. The old name will stop working in a near-future release.",
            id="anymail.W001",
        )])

    @override_settings(ANYMAIL_WEBHOOK_AUTHORIZATION="abcde:12345", ANYMAIL={})
    def test_anymail_webhook_authorization(self):
        errors = check_deprecated_settings(None)
        self.assertEqual(errors, [checks.Warning(
            "The ANYMAIL_WEBHOOK_AUTHORIZATION setting has been renamed ANYMAIL_WEBHOOK_SECRET to improve security.",
            hint="You must update your settings.py. The old name will stop working in a near-future release.",
            id="anymail.W001",
        )])
