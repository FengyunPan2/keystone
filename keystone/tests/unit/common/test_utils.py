# encoding: utf-8
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import datetime
import fixtures
import uuid

from oslo_config import fixture as config_fixture
from oslo_log import log
from oslo_serialization import jsonutils
import six

from keystone.common import fernet_utils
from keystone.common import utils as common_utils
import keystone.conf
from keystone.credential.providers import fernet as credential_fernet
from keystone import exception
from keystone.tests import unit
from keystone.tests.unit import ksfixtures
from keystone.tests.unit import utils
from keystone.version import service


CONF = keystone.conf.CONF

TZ = utils.TZ


class UtilsTestCase(unit.BaseTestCase):
    OPTIONAL = object()

    def setUp(self):
        super(UtilsTestCase, self).setUp()
        self.config_fixture = self.useFixture(config_fixture.Config(CONF))

    def test_resource_uuid(self):
        # Basic uuid test, most IDs issued by keystone look like this:
        value = u'536e28c2017e405e89b25a1ed777b952'
        self.assertEqual(value, common_utils.resource_uuid(value))

    def test_resource_64_char_uuid(self):
        # Exact 64 length string, like ones used by mapping_id backend, are not
        # valid UUIDs, so they will be UUID5 namespaced
        value = u'f13de678ac714bb1b7d1e9a007c10db5' * 2
        if six.PY2:
            value = value.encode('utf-8')
        expected_id = uuid.uuid5(common_utils.RESOURCE_ID_NAMESPACE, value).hex
        self.assertEqual(expected_id, common_utils.resource_uuid(value))

    def test_resource_non_ascii_chars(self):
        # IDs with non-ASCII characters will be UUID5 namespaced
        value = u'ß' * 32
        if six.PY2:
            value = value.encode('utf-8')
        expected_id = uuid.uuid5(common_utils.RESOURCE_ID_NAMESPACE, value).hex
        self.assertEqual(expected_id, common_utils.resource_uuid(value))

    def test_resource_invalid_id(self):
        # This input is invalid because it's length is more than 64.
        value = u'x' * 65
        self.assertRaises(ValueError, common_utils.resource_uuid,
                          value)

    def test_hash(self):
        password = 'right'
        wrong = 'wrongwrong'  # Two wrongs don't make a right
        hashed = common_utils.hash_password(password)
        self.assertTrue(common_utils.check_password(password, hashed))
        self.assertFalse(common_utils.check_password(wrong, hashed))

    def test_verify_normal_password_strict(self):
        self.config_fixture.config(strict_password_check=False)
        password = uuid.uuid4().hex
        verified = common_utils.verify_length_and_trunc_password(password)
        self.assertEqual(password, verified)

    def test_that_a_hash_can_not_be_validated_against_a_hash(self):
        # NOTE(dstanek): Bug 1279849 reported a problem where passwords
        # were not being hashed if they already looked like a hash. This
        # would allow someone to hash their password ahead of time
        # (potentially getting around password requirements, like
        # length) and then they could auth with their original password.
        password = uuid.uuid4().hex
        hashed_password = common_utils.hash_password(password)
        new_hashed_password = common_utils.hash_password(hashed_password)
        self.assertFalse(common_utils.check_password(password,
                                                     new_hashed_password))

    def test_verify_long_password_strict(self):
        self.config_fixture.config(strict_password_check=False)
        self.config_fixture.config(group='identity', max_password_length=5)
        max_length = CONF.identity.max_password_length
        invalid_password = 'passw0rd'
        trunc = common_utils.verify_length_and_trunc_password(invalid_password)
        self.assertEqual(invalid_password[:max_length], trunc)

    def test_verify_long_password_strict_raises_exception(self):
        self.config_fixture.config(strict_password_check=True)
        self.config_fixture.config(group='identity', max_password_length=5)
        invalid_password = 'passw0rd'
        self.assertRaises(exception.PasswordVerificationError,
                          common_utils.verify_length_and_trunc_password,
                          invalid_password)

    def test_hash_long_password_truncation(self):
        self.config_fixture.config(strict_password_check=False)
        invalid_length_password = '0' * 9999999
        hashed = common_utils.hash_password(invalid_length_password)
        self.assertTrue(common_utils.check_password(invalid_length_password,
                                                    hashed))

    def test_hash_long_password_strict(self):
        self.config_fixture.config(strict_password_check=True)
        invalid_length_password = '0' * 9999999
        self.assertRaises(exception.PasswordVerificationError,
                          common_utils.hash_password,
                          invalid_length_password)

    def _create_test_user(self, password=OPTIONAL):
        user = {"name": "hthtest"}
        if password is not self.OPTIONAL:
            user['password'] = password

        return user

    def test_hash_user_password_without_password(self):
        user = self._create_test_user()
        hashed = common_utils.hash_user_password(user)
        self.assertEqual(user, hashed)

    def test_hash_user_password_with_null_password(self):
        user = self._create_test_user(password=None)
        hashed = common_utils.hash_user_password(user)
        self.assertEqual(user, hashed)

    def test_hash_user_password_with_empty_password(self):
        password = ''
        user = self._create_test_user(password=password)
        user_hashed = common_utils.hash_user_password(user)
        password_hashed = user_hashed['password']
        self.assertTrue(common_utils.check_password(password, password_hashed))

    def test_hash_edge_cases(self):
        hashed = common_utils.hash_password('secret')
        self.assertFalse(common_utils.check_password('', hashed))
        self.assertFalse(common_utils.check_password(None, hashed))

    def test_hash_unicode(self):
        password = u'Comment \xe7a va'
        wrong = 'Comment ?a va'
        hashed = common_utils.hash_password(password)
        self.assertTrue(common_utils.check_password(password, hashed))
        self.assertFalse(common_utils.check_password(wrong, hashed))

    def test_auth_str_equal(self):
        self.assertTrue(common_utils.auth_str_equal('abc123', 'abc123'))
        self.assertFalse(common_utils.auth_str_equal('a', 'aaaaa'))
        self.assertFalse(common_utils.auth_str_equal('aaaaa', 'a'))
        self.assertFalse(common_utils.auth_str_equal('ABC123', 'abc123'))

    def test_unixtime(self):
        global TZ

        @utils.timezone
        def _test_unixtime():
            epoch = common_utils.unixtime(dt)
            self.assertEqual(epoch, epoch_ans, "TZ=%s" % TZ)

        dt = datetime.datetime(1970, 1, 2, 3, 4, 56, 0)
        epoch_ans = 56 + 4 * 60 + 3 * 3600 + 86400
        for d in ['+0', '-11', '-8', '-5', '+5', '+8', '+14']:
            TZ = 'UTC' + d
            _test_unixtime()

    def test_pki_encoder(self):
        data = {'field': 'value'}
        json = jsonutils.dumps(data, cls=common_utils.PKIEncoder)
        expected_json = '{"field":"value"}'
        self.assertEqual(expected_json, json)

    def test_url_safe_check(self):
        base_str = 'i am safe'
        self.assertFalse(common_utils.is_not_url_safe(base_str))
        for i in common_utils.URL_RESERVED_CHARS:
            self.assertTrue(common_utils.is_not_url_safe(base_str + i))

    def test_url_safe_with_unicode_check(self):
        base_str = u'i am \xe7afe'
        self.assertFalse(common_utils.is_not_url_safe(base_str))
        for i in common_utils.URL_RESERVED_CHARS:
            self.assertTrue(common_utils.is_not_url_safe(base_str + i))


class ServiceHelperTests(unit.BaseTestCase):

    @service.fail_gracefully
    def _do_test(self):
        raise Exception("Test Exc")

    def test_fail_gracefully(self):
        self.assertRaises(unit.UnexpectedExit, self._do_test)


class FernetUtilsTestCase(unit.BaseTestCase):

    def setUp(self):
        super(FernetUtilsTestCase, self).setUp()
        self.config_fixture = self.useFixture(config_fixture.Config(CONF))

    def test_debug_message_logged_when_loading_fernet_token_keys(self):
        self.useFixture(
            ksfixtures.KeyRepository(
                self.config_fixture,
                'fernet_tokens',
                CONF.fernet_tokens.max_active_keys
            )
        )
        logging_fixture = self.useFixture(fixtures.FakeLogger(level=log.DEBUG))
        fernet_utilities = fernet_utils.FernetUtils(
            CONF.fernet_tokens.key_repository,
            CONF.fernet_tokens.max_active_keys
        )
        fernet_utilities.load_keys()
        expected_debug_message = (
            'Loaded 2 Fernet keys from %(dir)s, but `[fernet_tokens] '
            'max_active_keys = %(max)d`; perhaps there have not been enough '
            'key rotations to reach `max_active_keys` yet?') % {
                'dir': CONF.fernet_tokens.key_repository,
                'max': CONF.fernet_tokens.max_active_keys}
        self.assertIn(expected_debug_message, logging_fixture.output)

    def test_debug_message_not_logged_when_loading_fernet_credential_key(self):
        self.useFixture(
            ksfixtures.KeyRepository(
                self.config_fixture,
                'credential',
                CONF.fernet_tokens.max_active_keys
            )
        )
        logging_fixture = self.useFixture(fixtures.FakeLogger(level=log.DEBUG))
        fernet_utilities = fernet_utils.FernetUtils(
            CONF.credential.key_repository,
            credential_fernet.MAX_ACTIVE_KEYS
        )
        fernet_utilities.load_keys()
        debug_message = (
            'Loaded 2 Fernet keys from %(dir)s, but `[fernet_tokens] '
            'max_active_keys = %(max)d`; perhaps there have not been enough '
            'key rotations to reach `max_active_keys` yet?') % {
                'dir': CONF.credential.key_repository,
                'max': credential_fernet.MAX_ACTIVE_KEYS}
        self.assertNotIn(debug_message, logging_fixture.output)
