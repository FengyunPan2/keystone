# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack LLC
#
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

import subprocess

from keystone import config
from keystone import test
from keystone.identity.backends import ldap as identity_ldap

import default_fixtures
import test_backend


CONF = config.CONF


def delete_object(name):
    devnull = open('/dev/null', 'w')
    dn = '%s,%s' % (name, CONF.ldap.suffix)
    subprocess.call(['ldapdelete',
                     '-x',
                     '-D', CONF.ldap.user,
                     '-H', CONF.ldap.url,
                     '-w', CONF.ldap.password,
                     dn],
                    stderr=devnull)


def clear_live_database():
    roles = ['keystone_admin']
    groups = ['baz', 'bar', 'tenent4add', 'fake1', 'fake2']
    users = ['foo', 'two', 'fake1', 'fake2', 'no_meta']
    roles = ['keystone_admin', 'useless']

    for group in groups:
        for role in roles:
            delete_object('cn=%s,cn=%s,ou=Groups' % (role, group))
        delete_object('cn=%s,ou=Groups' % group)

    for user in users:
        delete_object('cn=%s,ou=Users' % user)

    for role in roles:
        delete_object('cn=%s,ou=Roles' % role)


class LDAPIdentity(test.TestCase, test_backend.IdentityTests):
    def setUp(self):
        super(LDAPIdentity, self).setUp()
        CONF(config_files=[test.etcdir('keystone.conf.sample'),
                           test.testsdir('test_overrides.conf'),
                           test.testsdir('backend_liveldap.conf')])
        clear_live_database()
        self.identity_api = identity_ldap.Identity()
        self.load_fixtures(default_fixtures)

    def tearDown(self):
        test.TestCase.tearDown(self)
