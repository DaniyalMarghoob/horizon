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

from django import forms
from django.core import mail
from django.template.loader import render_to_string

from django_summernote.widgets import SummernoteWidget

from horizon import exceptions
from horizon import forms
from horizon import messages

from keystoneclient import exceptions as keystoneclient_exceptions

from openstack_dashboard import api
from openstack_dashboard import fiware_api


LOG = logging.getLogger('idm_logger')
NOTIFICATION_CHOICES = [
    ('all_users', 'Notify all users'),
    ('organization', 'Notify an organization'),
    ('role', 'Notify users by role')
]
ROLE_CHOICES = [ 
    ('trial', 'Trial'),
    ('basic', 'Basic'),
    ('community', 'Community'),
]

class EmailForm(forms.SelfHandlingForm):
    notify = forms.ChoiceField(
        required=True,
        choices=NOTIFICATION_CHOICES)
    organization = forms.CharField(
        label='Organization ID',
        required=False)
    role = forms.ChoiceField(
        widget=forms.RadioSelect,
        label='Role',
        required=False,
        choices=ROLE_CHOICES)
    subject = forms.CharField(
        max_length=50,
        label=("Subject"),
        required=True)
    body = forms.CharField(
        widget=SummernoteWidget(),
        label=("Body"),
        required=True)
    

    # TODO(garcianavalon) as settings
    EMAIL_HTML_TEMPLATE = 'email/base_email.html'
    EMAIL_TEXT_TEMPLATE = 'email/base_email.txt'

    def clean(self):
        cleaned_data = super(EmailForm, self).clean()

        organization_id = cleaned_data.get('organization', None)
        selected_role = cleaned_data.get('role', None)
        notify = cleaned_data.get('notify')

        if notify != 'organization':
            return cleaned_data

        elif notify == 'organization':
            if not organization_id:
                raise forms.ValidationError(
                    'You must specify an organization ID',
                    code='invalid')
            else:
                try:
                    organization = fiware_api.keystone.project_get(
                        self.request, 
                        organization_id)
                    return cleaned_data

                except keystoneclient_exceptions.NotFound:
                    raise forms.ValidationError(
                        'There is no organization with the specified ID',
                        code='invalid')

        return cleaned_data

    def handle(self, request, data):
        # TODO(garcianavalon) better email architecture...
        try:
            recipients = []
            if data['notify'] == 'all_users':
                recipients = [u.name for u
                             in fiware_api.keystone.user_list(request,
                                                       filters={'enabled':True})
                             if '@' in u.name]
            elif data['notify'] == 'organization':
                owner_role = fiware_api.keystone.get_owner_role(request)
                owners = [a.user['id'] for a
                          in api.keystone.role_assignments_list(
                            request,
                            role=owner_role.id,
                            project=data['organization'])
                ]
                for owner_id in owners:
                    owner = fiware_api.keystone.user_get(request, owner_id)
                    if '@' in owner.name:
                        recipients.append(owner.name)

            elif data['notify'] == 'role':
                if data['role'] == 'trial':
                    role = fiware_api.keystone.get_trial_role(self.request).id
                elif data['role'] == 'basic':
                    role = fiware_api.keystone.get_basic_role(self.request).id
                elif data['role'] == 'community':
                    role = fiware_api.keystone.get_community_role(self.request).id

                users = [a.user['id'] for a
                    in api.keystone.role_assignments_list(
                        request,
                        role=role) 
                ]

                for user_id in users:
                    user = fiware_api.keystone.user_get(request, user_id)
                    if '@' in user.name and user.name not in recipients:
                        recipients.append(user.name)

            if not recipients:
                msg = ('The recipients list is empty, no email will be sent.')
                messages.error(request, msg)
                return

            text_content = render_to_string(self.EMAIL_TEXT_TEMPLATE, 
                dictionary={
                    'massive_footer':True,
                    'content': {'text':data['body']},
                })
            
            html_content = render_to_string(self.EMAIL_HTML_TEMPLATE, 
                dictionary={
                    'massive_footer':True,
                    'content': {'html':data['body']},
                })

            connection = mail.get_connection(fail_silently=True)

            msg = mail.EmailMultiAlternatives(
                subject='[FIWARE Lab] ' + data['subject'], 
                body=text_content, 
                from_email='no-reply@account.lab.fi-ware.org', 
                bcc=recipients, 
                connection=connection)
            msg.attach_alternative(html_content, "text/html")
            msg.send()

            messages.success(request, ('Message sent succesfully.'))

        except Exception:
            msg = ('Unable to send message. Please try again later.')
            LOG.warning(msg)
            exceptions.handle(request, msg)