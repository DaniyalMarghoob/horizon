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

from django import shortcuts
from django.conf import settings
from django.forms import ValidationError  # noqa
from django import http
from django.contrib import auth as django_auth
from django.views.decorators.debug import sensitive_variables  # noqa

from openstack_auth import exceptions as auth_exceptions

from horizon import exceptions
from horizon import forms
from horizon import messages
from horizon.utils import functions as utils
from horizon.utils import validators

from openstack_dashboard import api
from openstack_dashboard import fiware_api

from openstack_dashboard.dashboards.idm_admin.user_accounts \
    import forms as user_accounts_forms


LOG = logging.getLogger('idm_logger')

class UpgradeForm(forms.SelfHandlingForm, user_accounts_forms.UserAccountsLogicMixin):
    action = 'accountstatus/'
    description = 'Account status'
    template = 'settings/multisettings/_status.html'

    def handle(self, request, data):

        try:
            user_id = request.user.id
            role_id = fiware_api.keystone.get_trial_role(request).id
            regions = ['Spain2']
            default_durations = getattr(settings, 'FIWARE_DEFAULT_DURATION', None)
            if default_durations:
                duration = default_durations['trial']
            else:
                duration = 14

            self.update_account(request, user_id, role_id, regions, duration)
            messages.success(request, 'Updated account to Trial succesfully.')

            return shortcuts.redirect('logout')
        except Exception:
            messages.error(request, 'An error ocurred. Please try again later.')


class PasswordForm(forms.SelfHandlingForm):
    action = 'password/'
    description = 'Change your password'
    template = 'settings/multisettings/_collapse_form.html'

    current_password = forms.CharField(
        label=('Current password'),
        widget=forms.PasswordInput(render_value=False))
    new_password = forms.RegexField(
        label=('New password'),
        widget=forms.PasswordInput(render_value=False),
        regex=validators.password_validator(),
        error_messages={'invalid':
                        validators.password_validator_msg()})
    confirm_password = forms.CharField(
        label=('Confirm new password'),
        widget=forms.PasswordInput(render_value=False))
    no_autocomplete = True

    def clean(self):
        '''Check to make sure password fields match.'''
        data = super(forms.Form, self).clean()
        if 'new_password' in data:
            if data['new_password'] != data.get('confirm_password', None):
                raise ValidationError(('Passwords do not match.'))
        return data

    # We have to protect the entire 'data' dict because it contains the
    # oldpassword and newpassword strings.
    @sensitive_variables('data')
    def handle(self, request, data):
        user_is_editable = api.keystone.keystone_can_edit_user()

        if user_is_editable:
            try:
                api.keystone.user_update_own_password(request,
                                                      data['current_password'],
                                                      data['new_password'])
                response = http.HttpResponseRedirect(settings.LOGOUT_URL)
                msg = ('Password changed. Please log in again to continue.')
                LOG.info(msg)
                utils.add_logout_reason(request, response, msg)
                return response
            except Exception:
                exceptions.handle(request,
                                  ('Unable to change password.'))
                return False
        else:
            messages.error(request, ('Changing password is not supported.'))
            return False

class EmailForm(forms.SelfHandlingForm):
    action = 'useremail/'
    description = 'Change your email'
    template = 'settings/multisettings/_collapse_form.html'
    
    email = forms.EmailField(
            label=("Email"),
            required=True)
    password = forms.CharField(
            label=("Current password"),
            widget=forms.PasswordInput(render_value=False),
            required=True)

    # We have to protect the entire "data" dict because it contains the
    # password string.
    @sensitive_variables('data')
    def handle(self, request, data):
        # the user's password to change the email, only to update the password
        user_is_editable = api.keystone.keystone_can_edit_user()
        if user_is_editable:
            try:
                # check if the password is correct
                password = data['password']
                domain = getattr(settings,
                                'OPENSTACK_KEYSTONE_DEFAULT_DOMAIN',
                                'Default')
                default_region = (settings.OPENSTACK_KEYSTONE_URL, "Default Region")
                region = getattr(settings, 'AVAILABLE_REGIONS', [default_region])[0][0]

                name = request.user.name
                result = django_auth.authenticate(request=request,
                                    username=name,
                                    password=password,
                                    user_domain_name=domain,
                                    auth_url=region)

                # now update email
                user_id = request.user.id
                #user = api.keystone.user_get(request, user_id, admin=False)
                
                # if we dont set password to None we get a dict-key error in api/keystone
                api.keystone.user_update(request, user_id, name=data['email'],
                                        password=None)
                
                # redirect user to settings home
                response = shortcuts.redirect('horizon:settings:multisettings:index')
                #response = shortcuts.redirect(request.build_absolute_uri())
                #response = shortcuts.redirect(horizon.get_user_home(request.user))
                msg = ("Email changed succesfully")
                LOG.debug(msg)
                messages.success(request, msg)
                return response

            except auth_exceptions.KeystoneAuthException as exc:
                messages.error(request, ('Invalid password'))
                LOG.error(exc)
                return False
            except Exception as e:
                exceptions.handle(request,
                                  ('Unable to change email.'))
                LOG.error(e)
                return False
        else:
            messages.error(request, ('Changing email is not supported.'))
            LOG.debug("Changing email is not supported")
            return False


class BasicCancelForm(forms.SelfHandlingForm):
    action = "cancelaccount/"
    description = 'Cancel account'
    template = 'settings/multisettings/_collapse_form.html'

    def handle(self, request, data):
        try:
            user = fiware_api.keystone.user_get(request, request.user.id)
            delete_orgs = self._get_orgs_to_delete(request, user)
            delete_apps = self._get_apps_to_delete(request, user)

            
            # NOTE(garcianavalon) here we need to use the idm
            # account to delete all the stuff to avoid problems
            # with user rights, tokens, etc.

            for org_id in delete_orgs:
                fiware_api.keystone.project_delete(request, org_id)

            for app_id in delete_apps:
                fiware_api.keystone.application_delete(request, 
                    app_id, use_idm_account=True)

            # finally delete the user
            fiware_api.keystone.user_delete(request, user.id)

            messages.success(request, ("Account canceled succesfully"))
            return shortcuts.redirect('logout')

        except Exception as e:   
            exceptions.handle(request,
                              ('Unable to cancel account.'))
            LOG.error(e)
            return False

    def _get_orgs_to_delete(self, request, user):
        # all orgs where the user is the only owner
        # and user specific organizations
        delete_orgs = [
            user.default_project_id,
            user.cloud_project_id
        ]
        owner_role = fiware_api.keystone.get_owner_role(request)
        # NOTE(garcianavalon) the organizations the user is owner
        # are already in the request object by the middleware
        for org in request.organizations:
            if org.id in delete_orgs:
                continue

            owners = set([
                a.user['id'] for a 
                in api.keystone.role_assignments_list(
                    request,
                    role=owner_role.id,
                    project=org.id)
                if hasattr(a, 'user')
            ])

            if len(owners) == 1:
                delete_orgs.append(org.id)

        return delete_orgs

    def _get_apps_to_delete(self, request, user):
        # all the apps where the user is the only provider
        delete_apps = []
        provider_role = fiware_api.keystone.get_provider_role(request)

        provided_apps = [
            a.application_id for a
            in fiware_api.keystone.user_role_assignments(request, 
                                                         user=user.id)
            if a.role_id == provider_role.id
        ]

        for app_id in provided_apps:
            providers = set([
                a.user_id for a 
                in fiware_api.keystone.user_role_assignments(
                    request,
                    application=app_id)
                if a.role_id == provider_role.id
            ])

            if len(providers) == 1:
                delete_apps.append(app_id)

        return delete_apps

class ManageTwoFactorForm(forms.SelfHandlingForm):
    action = 'two_factor/'
    description = 'Manage two factor authentication'
    template = 'settings/multisettings/_collapse_form.html'

    def handle(self, request, data):
        try:
            LOG.info('enabled two factor authentication')

            messages.success(request, "success")
            return True

        except Exception as e:   
            exceptions.handle(request, 'error')
            LOG.error(e)
            return False
