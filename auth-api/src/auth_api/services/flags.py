# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Manage the Feature Flags initialization, setup and service."""
from flask import current_app
from ldclient import get as ldclient_get, set_config as ldclient_set_config  # noqa: I001
from ldclient.config import Config  # noqa: I005
from ldclient import Context
from ldclient.integrations import Files

from auth_api.models import User


class Flags():
    """Wrapper around the feature flag system.

    calls FAIL to FALSE

    If the feature flag service is unavailable
    AND
    there is no local config file
    Calls -> False

    """

    def __init__(self, app=None):
        """Initialize this object."""
        self.sdk_key = None
        self.app = None

        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the Feature Flag environment."""
        self.app = app
        self.sdk_key = app.config.get('AUTH_LD_SDK_KEY')

        if self.sdk_key or app.env != 'production':

            if app.env == 'production':
                config = Config(sdk_key=self.sdk_key)
            else:
                factory = Files.new_data_source(paths=['flags.json'], auto_update=True)
                config = Config(sdk_key=self.sdk_key,
                                update_processor_class=factory,
                                send_events=False)

            ldclient_set_config(config)
            client = ldclient_get()

            app.extensions['featureflags'] = client
            app.teardown_appcontext(self.teardown)

    def teardown(self, exception):  # pylint: disable=unused-argument; flask method signature
        """Destroy all objects created by this extension."""
        client = current_app.extensions['featureflags']
        client.close()

    def _get_client(self):
        try:
            client = current_app.extensions['featureflags']
        except KeyError:
            try:
                self.init_app(current_app)
                client = current_app.extensions['featureflags']
            except KeyError:
                client = None

        return client

    @staticmethod
    def _get_anonymous_user():
        return Context.create('anonymous')

    @staticmethod
    def _user_as_key(user: User):
        return Context.builder(user.idp_userid)\
            .set('firstName', user.firstname)\
            .set('lastName', user.lastname).build()

    def is_on(self, flag: str, user: User = None) -> bool:
        """Assert that the flag is set for this user."""
        client = self._get_client()

        if user:
            flag_user = self._user_as_key(user)
        else:
            flag_user = self._get_anonymous_user()

        return bool(client.variation(flag, flag_user, None))

    def value(self, flag: str, user: User = None) -> bool:
        """Retrieve the value  of the (flag, user) tuple."""
        client = self._get_client()

        if user:
            flag_user = self._user_as_key(user)
        else:
            flag_user = self._get_anonymous_user()

        return client.variation(flag, flag_user, None)
