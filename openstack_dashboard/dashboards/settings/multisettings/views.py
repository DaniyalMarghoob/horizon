# Copyright (C) 2014 Universidad Politecnica de Madrid
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

import logging

from horizon import views

from openstack_dashboard import api
from openstack_dashboard import fiware_api
from openstack_dashboard.dashboards.settings.accountstatus \
    import forms as status_forms
from openstack_dashboard.dashboards.settings.cancelaccount \
    import forms as cancelaccount_forms
from openstack_dashboard.dashboards.settings.password \
    import forms as password_forms
from openstack_dashboard.dashboards.settings.useremail \
    import forms as useremail_forms


LOG = logging.getLogger('idm_logger')

class MultiFormView(views.APIView):
    template_name = 'settings/multisettings/index.html'
    
    def get_context_data(self, **kwargs):
        context = super(MultiFormView, self).get_context_data(**kwargs)

        # Initial data
        user_id = self.request.user.id
        user = fiware_api.keystone.user_get(self.request, user_id)
        initial_email = {
            'email': user.name
        }

        # Current account_type
        # TODO(garcianavalon) find a better solution to this
        user_roles = [a.role['id'] for a in fiware_api.keystone.role_assignments_list(self.request, 
            user=user_id, domain='default')]
        basic_role = fiware_api.keystone.get_basic_role(self.request, use_idm_account=True)
        trial_role = fiware_api.keystone.get_trial_role(self.request, use_idm_account=True)
        community_role = fiware_api.keystone.get_community_role(self.request, use_idm_account=True)
        account_roles = [
            basic_role,
            trial_role,
            community_role,
        ]
        context['account_type'] = next((r.name for r in account_roles 
            if r.id in user_roles), None)
        if context['account_type'] == trial_role.name:
            context['started_at'] = getattr(user, 'trial_started_at', 'start date not available')
        elif context['account_type'] == community_role.name:
            context['started_at'] = getattr(user, 'community_started_at', 'start date not available')

        if context['account_type'] != community_role.name:
            context['show_community_request'] = True

        if context['account_type'] == basic_role.name:
            context['show_trial_request'] = True
        
        #Create forms
        status = status_forms.UpgradeForm(self.request)
        cancel = cancelaccount_forms.BasicCancelForm(self.request)
        password = password_forms.PasswordForm(self.request)
        email = useremail_forms.EmailForm(self.request, initial=initial_email)

        #Actions and titles
        # TODO(garcianavalon) move all of this to each form
        status.action = 'accountstatus/'
        email.action = 'useremail/'
        password.action = "password/"
        cancel.action = "cancelaccount/"
        status.description = 'Account status'
        email.description = ('Change your email')
        password.description = ('Change your password')
        cancel.description = ('Cancel account')

        status.template = 'settings/accountstatus/_status.html'
        email.template = 'settings/multisettings/_collapse_form.html'
        password.template = 'settings/multisettings/_collapse_form.html'
        cancel.template = 'settings/multisettings/_collapse_form.html'

        context['forms'] = [status, password, email, cancel]
        return context
